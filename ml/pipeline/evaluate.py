"""
Holdout evaluation entry point.

Usage:
    python -m ml.pipeline.evaluate [--run-id RUN_ID]

Evaluates the trained models from a given run against the holdout season
(2024-2025). Run this ONCE after all training decisions are finalized.

Artifacts produced per run:
    holdout_metrics.json  — scalar metrics for all models (backward-compatible)
    eval_report.json      — full structured report: per-class diagnostics,
                            calibration curves, error slices, top features
"""

import argparse
import json
import logging
import pickle
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from ml.config import (
    ARTIFACTS_DIR, SEASONS_TRAIN, SEASONS_VALID, SEASONS_TEST,
    TARGET_COL, TARGET_CLASSES, LOG_FORMAT,
)
from ml.features.loader import load_raw_matches, validate_data_contract
from ml.features.engineering import build_features, get_feature_columns
from ml.models.evaluation import (
    compute_metrics,
    print_metrics,
    calibration_summary,
    per_class_metrics,
    calibration_curves_dict,
    error_slices_by_col,
    feature_importance_df,
    permutation_importance_df,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def _load_run_dir(run_id: str | None) -> Path:
    if run_id:
        d = ARTIFACTS_DIR / run_id
        if not d.exists():
            raise FileNotFoundError(f"Run directory not found: {d}")
        return d

    latest_file = ARTIFACTS_DIR / "latest_run.txt"
    if not latest_file.exists():
        raise FileNotFoundError(
            "No run_id provided and no latest_run.txt found. "
            "Run python -m ml.pipeline.train first."
        )
    run_id = latest_file.read_text().strip()
    return ARTIFACTS_DIR / run_id


def _build_error_slices(error_df: pd.DataFrame) -> dict:
    """
    Produce error slices for a gradient_boost prediction DataFrame.
    Slices: by calendar month, by home team form (last 10), by away team form (last 10).
    """
    slices: dict = {}

    # By calendar month
    if "match_date" in error_df.columns:
        error_df = error_df.copy()
        error_df["_month"] = error_df["match_date"].dt.month
        by_month = {}
        for month, grp in error_df.groupby("_month"):
            by_month[str(int(month))] = {
                "accuracy": float(grp["correct"].mean()),
                "n":        int(len(grp)),
            }
        slices["by_month"] = by_month

    # By home team recent form (proxy for home team quality)
    slices["by_home_form"] = error_slices_by_col(
        error_df, "home_form_pts_10", n_bins=3, bin_labels=["low", "mid", "high"]
    )

    # By away team recent form (proxy for opponent quality)
    slices["by_away_form"] = error_slices_by_col(
        error_df, "away_form_pts_10", n_bins=3, bin_labels=["low", "mid", "high"]
    )

    return slices


def _format_summary_lines(report: dict) -> list[str]:
    """Return human-readable bullet lines summarising the eval report."""
    lines = []
    best = report["best_model"]
    bm = report["models"][best]
    lines.append(
        f"Best model: {best} | accuracy={bm['accuracy']:.3f} | log_loss={bm['log_loss']:.3f}"
    )

    # Per-class highlights for best model
    if "per_class" in bm:
        for cls in TARGET_CLASSES:
            pc = bm["per_class"].get(cls, {})
            cal = pc.get("calibration_mae")
            cal_str = f"{cal:.3f}" if cal is not None else "n/a"
            lines.append(
                f"  {cls}: precision={pc.get('precision', 0):.3f}  "
                f"recall={pc.get('recall', 0):.3f}  "
                f"f1={pc.get('f1', 0):.3f}  "
                f"support={pc.get('support', 0)}  "
                f"cal_mae={cal_str}"
            )

    # Flag weak draw recall (common failure mode)
    draw_recall = bm.get("per_class", {}).get("D", {}).get("recall", None)
    if draw_recall is not None and draw_recall < 0.30:
        lines.append(
            f"  WARNING: draw recall={draw_recall:.3f} — model systematically under-predicts draws"
        )

    # Error slices highlight
    slices = bm.get("error_slices", {})
    by_month = slices.get("by_month", {})
    if by_month:
        worst_month = min(by_month, key=lambda m: by_month[m]["accuracy"])
        best_month  = max(by_month, key=lambda m: by_month[m]["accuracy"])
        lines.append(
            f"  Monthly range: best=month {best_month} ({by_month[best_month]['accuracy']:.3f})  "
            f"worst=month {worst_month} ({by_month[worst_month]['accuracy']:.3f})"
        )

    by_home = slices.get("by_home_form", {})
    if by_home:
        lines.append(
            "  Home form accuracy: "
            + "  ".join(f"{k}={v['accuracy']:.3f}(n={v['n']})" for k, v in sorted(by_home.items()))
        )

    by_away = slices.get("by_away_form", {})
    if by_away:
        lines.append(
            "  Away form accuracy: "
            + "  ".join(f"{k}={v['accuracy']:.3f}(n={v['n']})" for k, v in sorted(by_away.items()))
        )

    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate trained models on holdout season")
    parser.add_argument("--run-id", default=None, help="Run ID to evaluate (default: latest)")
    args = parser.parse_args()

    run_dir = _load_run_dir(args.run_id)
    logger.info(f"Evaluating run: {run_dir.name}")

    # ------------------------------------------------------------------
    # 1. Load holdout data (2024-2025)
    # ------------------------------------------------------------------
    logger.info(f"Loading holdout data: {SEASONS_TEST}")
    raw_holdout = load_raw_matches(seasons=SEASONS_TEST)
    validate_data_contract(raw_holdout)

    # Rolling features for holdout require full match history
    all_seasons = SEASONS_TRAIN + SEASONS_VALID + SEASONS_TEST
    raw_all = load_raw_matches(seasons=all_seasons)
    df_all  = build_features(raw_all, include_h2h=True)

    df_holdout = df_all[df_all["season_id"].isin(SEASONS_TEST)].copy()
    df_holdout = df_holdout.dropna(subset=[TARGET_COL])

    feat_path = run_dir / "feature_cols.json"
    if feat_path.exists():
        feature_cols = json.loads(feat_path.read_text())
    else:
        feature_cols = get_feature_columns(df_holdout)

    feature_cols = [c for c in feature_cols if c in df_holdout.columns]

    X_test = df_holdout[feature_cols].values
    y_test  = df_holdout[TARGET_COL].values

    logger.info(f"Holdout size: {len(X_test)} matches, {len(feature_cols)} features")

    # ------------------------------------------------------------------
    # 2. Load trained models and evaluate
    # ------------------------------------------------------------------
    model_files = sorted(run_dir.glob("*.pkl"))
    if not model_files:
        raise FileNotFoundError(f"No .pkl model files found in {run_dir}")

    holdout_metrics: dict = {}
    report_models:   dict = {}

    for model_path in model_files:
        name = model_path.stem
        with open(model_path, "rb") as f:
            model = pickle.load(f)

        y_pred  = model.predict(X_test)
        y_proba = model.predict_proba(X_test)

        classes = getattr(model, "classes_", TARGET_CLASSES)
        proba_df = pd.DataFrame(y_proba, columns=classes)
        proba_ordered = proba_df.reindex(columns=TARGET_CLASSES, fill_value=0).values

        m = compute_metrics(y_test, y_pred, proba_ordered)
        holdout_metrics[name] = {k: v for k, v in m.items() if k != "report"}

        print_metrics(m, model_name=f"{name} [HOLDOUT]")

        # Calibration MAE (printed + saved)
        cal = calibration_summary(y_test, proba_ordered)
        print(f"\nCalibration (mean absolute error from diagonal):")
        for cls, (frac, pred) in cal.items():
            mae = np.mean(np.abs(frac - pred))
            print(f"  {cls}: calibration MAE = {mae:.4f}")
            holdout_metrics[name][f"cal_mae_{cls}"] = float(mae)

        # Structured per-class diagnostics
        pc = per_class_metrics(y_test, y_pred, proba_ordered)
        cal_curves = calibration_curves_dict(y_test, proba_ordered)

        report_models[name] = {
            **{k: v for k, v in m.items() if k != "report"},
            "per_class":         pc,
            "calibration_curves": cal_curves,
        }

    # ------------------------------------------------------------------
    # 3. Feature importance (gradient_boost only)
    # Try native importances first; fall back to permutation importance.
    # Permutation importance on the holdout set is preferred for HistGBM
    # (which exposes no native feature_importances_) and is also more
    # informative since it measures contribution on unseen data.
    # ------------------------------------------------------------------
    gb_path = run_dir / "gradient_boost.pkl"
    if gb_path.exists():
        with open(gb_path, "rb") as f:
            gb = pickle.load(f)
        fi_df = feature_importance_df(gb, feature_cols)
        if fi_df.empty:
            logger.info("Native importances unavailable — computing permutation importance on holdout")
            fi_df = permutation_importance_df(gb, X_test, y_test, feature_cols)
            fi_col = "mean_importance"
            fi_label = "permutation importance (holdout, accuracy drop)"
        else:
            fi_col = "importance"
            fi_label = "native importance (averaged across calibration folds)"

        if not fi_df.empty:
            print(f"\nTop 20 features by {fi_label}:")
            print(fi_df.head(20).to_string(index=False))
            report_models["gradient_boost"]["top_features"] = (
                fi_df.head(30).to_dict(orient="records")
            )
            report_models["gradient_boost"]["importance_method"] = fi_label

    # ------------------------------------------------------------------
    # 4. Error analysis (gradient_boost)
    # ------------------------------------------------------------------
    if gb_path.exists():
        y_pred_gb = gb.predict(X_test)

        error_df = df_holdout.copy()
        error_df["predicted"] = y_pred_gb
        error_df["correct"]   = (error_df["predicted"] == error_df[TARGET_COL])

        print("\n--- Error Analysis: gradient_boost ---")
        print(f"Overall accuracy: {error_df['correct'].mean():.3f}")

        print("\nAccuracy by true outcome:")
        for cls in TARGET_CLASSES:
            mask = error_df[TARGET_COL] == cls
            acc  = error_df[mask]["correct"].mean()
            n    = mask.sum()
            print(f"  {cls}: {acc:.3f}  (n={n})")

        print("\nAccuracy by month (holdout):")
        error_df["month"] = error_df["match_date"].dt.month
        for month, grp in error_df.groupby("month"):
            print(f"  Month {month:02d}: {grp['correct'].mean():.3f}  (n={len(grp)})")

        # Home/away form slicing
        slices = _build_error_slices(error_df)
        if slices.get("by_home_form"):
            print("\nAccuracy by home team form (last 10):")
            for label, s in sorted(slices["by_home_form"].items()):
                print(f"  {label}: {s['accuracy']:.3f}  (n={s['n']}  mean_pts={s['mean_value']:.2f})")
        if slices.get("by_away_form"):
            print("\nAccuracy by away team form (last 10):")
            for label, s in sorted(slices["by_away_form"].items()):
                print(f"  {label}: {s['accuracy']:.3f}  (n={s['n']}  mean_pts={s['mean_value']:.2f})")

        report_models["gradient_boost"]["error_slices"] = slices

    # ------------------------------------------------------------------
    # 5. Save holdout_metrics.json (backward-compatible)
    # ------------------------------------------------------------------
    out_path = run_dir / "holdout_metrics.json"
    out_path.write_text(json.dumps(holdout_metrics, indent=2))
    logger.info(f"Holdout metrics saved to: {out_path}")

    # ------------------------------------------------------------------
    # 6. Save eval_report.json (full structured report)
    # ------------------------------------------------------------------
    best_model = max(holdout_metrics, key=lambda k: holdout_metrics[k]["accuracy"])

    eval_report = {
        "run_id":            run_dir.name,
        "eval_date":         date.today().isoformat(),
        "holdout_seasons":   SEASONS_TEST,
        "n_holdout_matches": int(len(X_test)),
        "models":            report_models,
        "best_model":        best_model,
    }
    summary_lines = _format_summary_lines(eval_report)
    eval_report["summary_lines"] = summary_lines

    report_path = run_dir / "eval_report.json"
    report_path.write_text(json.dumps(eval_report, indent=2))
    logger.info(f"Eval report saved to: {report_path}")

    # ------------------------------------------------------------------
    # 7. Human-readable summary
    # ------------------------------------------------------------------
    best_acc = holdout_metrics[best_model]["accuracy"]
    best_ll  = holdout_metrics[best_model]["log_loss"]

    print(f"\n{'='*60}")
    print(f"HOLDOUT EVALUATION COMPLETE")
    print(f"Best model : {best_model}")
    print(f"Accuracy   : {best_acc:.4f}")
    print(f"Log loss   : {best_ll:.4f}")
    print(f"\nKey diagnostics:")
    for line in summary_lines[1:]:  # skip first (already shown above)
        print(line)
    print(f"{'='*60}")

    print("""
NEXT IMPROVEMENTS (prioritized by expected lift):
  1. Add ELO rating features (season-adaptive team strength proxy)
  2. Incorporate manager/squad changes (may require manual data)
  3. Tune HGB hyperparameters via Optuna on the walk-forward CV
  4. Add player availability aggregate (key players injured/suspended)
  5. Improve xG coverage for 2023-24+ (FBRef data already available in raw/)
  6. Ensemble: blend logistic + HGB probabilities
  7. Separate draw classifier (draws are notoriously hard to predict)
""")


if __name__ == "__main__":
    main()
