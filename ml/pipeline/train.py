"""
Training pipeline entry point.

Usage:
    python -m ml.pipeline.train

Runs:
  1. Load all match data from CSVs
  2. Build leakage-free features
  3. Walk-forward cross-validation over seasons
  4. Train final models on train+validation data
  5. Save artifacts to ml/artifacts/
"""

import json
import logging
import pickle
from datetime import datetime

import numpy as np
import pandas as pd

from ml.config import (
    ARTIFACTS_DIR, RANDOM_SEED, SEASONS_TRAIN, SEASONS_VALID,
    TARGET_COL, TARGET_CLASSES, LOG_FORMAT,
)
from ml.features.loader import load_raw_matches, validate_data_contract
from ml.features.engineering import build_features, get_feature_columns
from ml.models.baselines import NaiveBaseline, make_logistic_pipeline
from ml.models.gradient_boost import make_best_boosting_pipeline
from ml.models.evaluation import compute_metrics, print_metrics, feature_importance_df


def _clone_model(name: str):
    """Return a fresh unfitted model instance by name."""
    if name == "naive_baseline":
        return NaiveBaseline()
    if name == "logistic_baseline":
        return make_logistic_pipeline()
    if name == "gradient_boost":
        return make_best_boosting_pipeline()
    raise ValueError(f"Unknown model name: {name}")

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

np.random.seed(RANDOM_SEED)


# ---------------------------------------------------------------------------
# Walk-forward cross-validation
# ---------------------------------------------------------------------------

def _walk_forward_cv(df_features: pd.DataFrame, feature_cols: list[str]) -> list[dict]:
    """
    Walk-forward evaluation: for each season after the first, train on all
    prior seasons and evaluate on the current season.

    Returns a list of metric dicts, one per fold.
    """
    seasons = sorted(df_features["season_id"].unique())
    folds = []

    for i in range(1, len(seasons)):
        train_seasons = seasons[:i]
        eval_season   = seasons[i]

        train_df = df_features[df_features["season_id"].isin(train_seasons)]
        eval_df  = df_features[df_features["season_id"] == eval_season]

        X_train = train_df[feature_cols].values
        y_train = train_df[TARGET_COL].values
        X_eval  = eval_df[feature_cols].values
        y_eval  = eval_df[TARGET_COL].values

        if len(X_train) == 0 or len(X_eval) == 0:
            continue

        model = make_best_boosting_pipeline()
        model.fit(X_train, y_train)

        y_pred  = model.predict(X_eval)
        y_proba = model.predict_proba(X_eval)

        # Ensure probability columns are in TARGET_CLASSES order
        model_classes = model.classes_ if hasattr(model, "classes_") else TARGET_CLASSES
        proba_df = pd.DataFrame(y_proba, columns=model_classes)
        proba_ordered = proba_df.reindex(columns=TARGET_CLASSES, fill_value=0).values

        metrics = compute_metrics(y_eval, y_pred, proba_ordered)
        metrics["fold_train"] = str(train_seasons)
        metrics["fold_eval"]  = eval_season
        metrics.pop("report", None)

        folds.append(metrics)
        logger.info(
            f"CV fold  train={train_seasons} → eval={eval_season}: "
            f"acc={metrics['accuracy']:.3f}  ll={metrics['log_loss']:.3f}"
        )

    return folds


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Run ID: {run_id}  →  {run_dir}")

    # ------------------------------------------------------------------
    # 1. Load data (train + validation; holdout NOT touched here)
    # ------------------------------------------------------------------
    seasons_for_training = SEASONS_TRAIN + SEASONS_VALID
    logger.info(f"Loading match data for seasons: {seasons_for_training}")
    raw = load_raw_matches(seasons=seasons_for_training)
    validate_data_contract(raw)

    # ------------------------------------------------------------------
    # 2. Feature engineering
    # ------------------------------------------------------------------
    logger.info("Building features (this includes head-to-head computation)...")
    df = build_features(raw, include_h2h=True)

    feature_cols = get_feature_columns(df)
    logger.info(f"Feature count: {len(feature_cols)}")

    # Drop rows where target is null (shouldn't happen after validation)
    df = df.dropna(subset=[TARGET_COL])

    # Save feature list
    (run_dir / "feature_cols.json").write_text(json.dumps(feature_cols, indent=2))

    # ------------------------------------------------------------------
    # 3. Walk-forward cross-validation
    # ------------------------------------------------------------------
    logger.info("Running walk-forward cross-validation...")
    cv_folds = _walk_forward_cv(df, feature_cols)

    if cv_folds:
        avg_acc = np.mean([f["accuracy"] for f in cv_folds])
        avg_ll  = np.mean([f["log_loss"]  for f in cv_folds])
        logger.info(f"CV summary: mean_acc={avg_acc:.4f}  mean_log_loss={avg_ll:.4f}")
        (run_dir / "cv_results.json").write_text(json.dumps(cv_folds, indent=2))

    # ------------------------------------------------------------------
    # 4. Train all models on full training data (train + valid)
    # ------------------------------------------------------------------
    train_mask = df["season_id"].isin(SEASONS_TRAIN)
    valid_mask = df["season_id"].isin(SEASONS_VALID)

    X_train = df[train_mask][feature_cols].values
    y_train = df[train_mask][TARGET_COL].values
    X_valid = df[valid_mask][feature_cols].values
    y_valid = df[valid_mask][TARGET_COL].values

    # Full train+valid data for the artifact that will be used on holdout
    X_tv = df[feature_cols].values
    y_tv = df[TARGET_COL].values

    all_metrics = {}

    model_names = ["naive_baseline", "logistic_baseline", "gradient_boost"]

    trained = {}
    for name in model_names:
        logger.info(f"Training {name}...")

        # Honest validation: train on SEASONS_TRAIN only, evaluate on SEASONS_VALID
        if len(X_valid) > 0:
            val_model = _clone_model(name)
            val_model.fit(X_train, y_train)
            y_pred  = val_model.predict(X_valid)
            y_proba = val_model.predict_proba(X_valid)
            classes = list(getattr(val_model, "classes_", TARGET_CLASSES))
            proba_df = pd.DataFrame(y_proba, columns=classes)
            proba_ordered = proba_df.reindex(columns=TARGET_CLASSES, fill_value=0).values
            m = compute_metrics(y_valid, y_pred, proba_ordered)
            all_metrics[name] = m
            print_metrics(m, model_name=f"{name} [val: train->valid]")

        # Final artifact: train on all non-holdout data (train + valid)
        final_model = _clone_model(name)
        final_model.fit(X_tv, y_tv)
        trained[name] = final_model

    # ------------------------------------------------------------------
    # 5. Save artifacts
    # ------------------------------------------------------------------
    for name, model in trained.items():
        model_path = run_dir / f"{name}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        logger.info(f"Saved {name} → {model_path}")

    # Feature importance for gradient_boost
    gb = trained["gradient_boost"]
    fi_df = feature_importance_df(gb, feature_cols)
    if not fi_df.empty:
        fi_path = run_dir / "feature_importance.csv"
        fi_df.to_csv(fi_path, index=False)
        logger.info(f"Top 10 features:\n{fi_df.head(10).to_string(index=False)}")

    # Metrics summary
    metrics_path = run_dir / "validation_metrics.json"
    # Remove non-serializable report strings
    for m in all_metrics.values():
        m.pop("report", None)
    metrics_path.write_text(json.dumps(all_metrics, indent=2))

    # Run metadata
    meta = {
        "run_id":           run_id,
        "seasons_trained":  seasons_for_training,
        "n_train_rows":     int(len(X_train)),
        "n_valid_rows":     int(len(X_valid)),
        "feature_count":    len(feature_cols),
        "cv_mean_accuracy": float(np.mean([f["accuracy"] for f in cv_folds])) if cv_folds else None,
        "cv_mean_log_loss": float(np.mean([f["log_loss"]  for f in cv_folds])) if cv_folds else None,
        "random_seed":      RANDOM_SEED,
    }
    (run_dir / "run_meta.json").write_text(json.dumps(meta, indent=2))

    # Write pointer to latest run
    (ARTIFACTS_DIR / "latest_run.txt").write_text(run_id)

    logger.info(f"\nTraining complete. Artifacts saved to: {run_dir}")
    logger.info("Next step: python -m ml.pipeline.evaluate")


if __name__ == "__main__":
    main()
