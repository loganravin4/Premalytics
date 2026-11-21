"""
Shot xG evaluation pipeline (XG-05 / XG-06 / XG-07).

Scores every model from the latest shot run on the eval tournaments (see
SHOT_EVAL_START_DATE). Headline numbers use the men's eval shots; women's eval
shots are reported separately.

Reports, per model: Brier, log loss, ROC AUC. Also:
  - legacy_v1: the pre-XG-05 setup (distance + angle logistic trained on
    WC 2018 only), scored on the same eval shots as the "before" number
  - statsbomb_reference: StatsBomb's own xG on the same shots (a benchmark
    from a richer proprietary model; never a feature)
  - calibration buckets (fixed probability bins with Wilson 95% intervals)
  - per-match totals: summed model xG vs non-penalty goals per team-match
  - mens_only ablation: the production model refit without women's shots

Writes ml/artifacts/{run}/shot_xg_metrics.json and prints a summary.

Usage:
    python -m ml.pipeline.evaluate_shots [--run-id RUN_ID]
"""

import argparse
import json
import logging
import math
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from ml.config import ARTIFACTS_DIR, DATA_DIR, LOG_FORMAT, SHOT_HEADLINE_GENDER
from ml.models.shot_xg import FEATURE_SETS, MODEL_FACTORIES, LOGISTIC_FEATURES, p_goal
from ml.pipeline.train_shots import load_shots, split_shots, conversion_rate

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

MODEL_NAMES = ["logistic_xg", "logistic_full", "gbm_full", "grid_xg"]
CALIBRATION_EDGES = [0.0, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 1.0]
JOIN_COVERAGE_THRESHOLD = 0.90
EPS = 1e-6


def resolve_run_dir(run_id: str | None) -> Path:
    if run_id:
        d = ARTIFACTS_DIR / run_id
        if not d.exists():
            raise FileNotFoundError(f"Run directory not found: {d}")
        return d
    latest = ARTIFACTS_DIR / "latest_shot_run.txt"
    if not latest.exists():
        raise FileNotFoundError("No latest_shot_run.txt — run python -m ml.pipeline.train_shots first.")
    return ARTIFACTS_DIR / latest.read_text().strip()


def metric_block(y: pd.Series, p: np.ndarray) -> dict:
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return {
        "n": int(len(y)),
        "brier_score": round(float(brier_score_loss(y, p)), 5),
        "log_loss": round(float(log_loss(y, p, labels=[0, 1])), 5),
        "roc_auc": round(float(roc_auc_score(y, p)), 4) if y.nunique() > 1 else None,
        "mean_pred": round(float(p.mean()), 4),
        "observed_rate": round(float(y.mean()), 4),
    }


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def calibration_buckets(y: pd.Series, p: np.ndarray, edges=CALIBRATION_EDGES) -> dict:
    """Fixed-bin reliability table plus expected calibration error (ECE)."""
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    bins = []
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi) if hi < 1.0 else (p >= lo) & (p <= hi)
        n = int(mask.sum())
        if n == 0:
            bins.append({"lo": lo, "hi": hi, "n": 0, "mean_pred": None, "observed": None,
                         "goals": 0, "ci95": None})
            continue
        k = int(y[mask].sum())
        mp, obs = float(p[mask].mean()), k / n
        ece += n / len(p) * abs(mp - obs)
        lo_ci, hi_ci = wilson_interval(k, n)
        bins.append({"lo": lo, "hi": hi, "n": n, "mean_pred": round(mp, 4), "observed": round(obs, 4),
                     "goals": k, "ci95": [round(lo_ci, 4), round(hi_ci, 4)]})
    return {"bins": bins, "ece": round(ece, 5)}


def per_match_totals(df: pd.DataFrame, p: np.ndarray) -> dict:
    """Summed xG vs non-penalty goals per team-match (penalties and own goals excluded)."""
    d = df.assign(xg=p)
    g = d.groupby(["match_id", "match_date", "tournament", "competition_gender", "team_id"]).agg(
        xg=("xg", "sum"), goals=("label", "sum"), shots=("label", "size"),
        sb_xg=("sb_xg_benchmark", "sum"),
    ).reset_index().sort_values(["match_date", "match_id", "team_id"])
    err = g["xg"] - g["goals"]
    summary = {
        "n_team_matches": int(len(g)),
        "total_xg": round(float(g["xg"].sum()), 2),
        "total_goals": int(g["goals"].sum()),
        "total_sb_xg": round(float(g["sb_xg"].sum()), 2),
        "mae_per_team_match": round(float(err.abs().mean()), 4),
        "rmse_per_team_match": round(float(np.sqrt((err ** 2).mean())), 4),
        "mean_bias_per_team_match": round(float(err.mean()), 4),
        "pearson_r_xg_goals": round(float(np.corrcoef(g["xg"], g["goals"])[0, 1]), 4),
        "sb_mae_per_team_match": round(float((g["sb_xg"] - g["goals"]).abs().mean()), 4),
    }
    rows = [
        {"match_id": r.match_id, "match_date": r.match_date, "tournament": r.tournament,
         "gender": r.competition_gender, "team_id": r.team_id, "shots": int(r.shots),
         "xg": round(float(r.xg), 3), "goals": int(r.goals), "sb_xg": round(float(r.sb_xg), 3)}
        for r in g.itertuples()
    ]
    return {"summary": summary, "rows": rows}


def paired_bootstrap_diff(df: pd.DataFrame, p_a: np.ndarray, p_b: np.ndarray,
                          n_boot: int = 2000, seed: int = 42) -> dict:
    """
    Match-clustered paired bootstrap of per-shot log loss and Brier
    differences (a - b). Negative means model a is better. Resampling whole
    matches respects the correlation between shots in one game.
    """
    y = df["label"].to_numpy()
    pa = np.clip(p_a, EPS, 1 - EPS)
    pb = np.clip(p_b, EPS, 1 - EPS)
    ll_d = -(y * np.log(pa) + (1 - y) * np.log(1 - pa)) + (y * np.log(pb) + (1 - y) * np.log(1 - pb))
    br_d = (pa - y) ** 2 - (pb - y) ** 2
    codes, _ = pd.factorize(df["match_id"])
    n_m = codes.max() + 1
    ll_sum = np.bincount(codes, ll_d, n_m)
    br_sum = np.bincount(codes, br_d, n_m)
    cnt = np.bincount(codes, minlength=n_m)
    rng = np.random.default_rng(seed)
    ll_bs, br_bs = [], []
    for _ in range(n_boot):
        idx = rng.integers(0, n_m, n_m)
        c = cnt[idx].sum()
        ll_bs.append(ll_sum[idx].sum() / c)
        br_bs.append(br_sum[idx].sum() / c)
    return {
        "log_loss_diff": round(float(ll_d.mean()), 5),
        "log_loss_diff_ci95": [round(float(np.percentile(ll_bs, q)), 5) for q in (2.5, 97.5)],
        "brier_diff": round(float(br_d.mean()), 6),
        "brier_diff_ci95": [round(float(np.percentile(br_bs, q)), 6) for q in (2.5, 97.5)],
        "n_matches": int(n_m), "n_boot": n_boot,
    }


def check_join_coverage(shots: pd.DataFrame) -> float | None:
    """Fraction of WC 2018/2022 shot rows whose match_id exists in the WC match data."""
    wc = shots[shots["competition_id"] == "fifa_world_cup"]
    match_ids: set = set()
    for season in ("2018", "2022"):
        mpath = DATA_DIR / "fifa_world_cup" / season / "match_logs_normalized.csv"
        if mpath.exists():
            match_ids.update(pd.read_csv(mpath)["match_id"].astype(str))
    if not match_ids:
        logger.warning("No WC match data on disk — skipping shot->match join check")
        return None
    wc = wc[wc["season_id"].isin(["2018", "2022"])]
    coverage = float(wc["match_id"].astype(str).isin(match_ids).mean())
    level = logging.WARNING if coverage < JOIN_COVERAGE_THRESHOLD else logging.INFO
    logger.log(level, "Shot->match join coverage (WC 2018/2022): %.1f%%", coverage * 100)
    return coverage


def logistic_coefficients(model) -> list[dict]:
    """Standardized coefficients of logistic_full (for the docs)."""
    names = model.named_steps["prep"].get_feature_names_out()
    coefs = model.named_steps["clf"].coef_[0]
    order = np.argsort(-np.abs(coefs))
    return [{"feature": str(names[i]).split("__", 1)[-1], "coef": round(float(coefs[i]), 4)} for i in order]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate shot xG models on the eval tournaments")
    parser.add_argument("--run-id", default=None, help="Run dir name (default: latest)")
    args = parser.parse_args()

    run_dir = resolve_run_dir(args.run_id)
    logger.info("Evaluating shot run: %s", run_dir.name)
    selection = json.loads((run_dir / "production_model.json").read_text())
    prod = selection["production_model"]

    df = load_shots()
    join_coverage = check_join_coverage(df)
    train_df, eval_df = split_shots(df)
    head = eval_df[eval_df["competition_gender"] == SHOT_HEADLINE_GENDER]
    other = eval_df[eval_df["competition_gender"] != SHOT_HEADLINE_GENDER]

    models = {name: joblib.load(run_dir / f"{name}.joblib") for name in MODEL_NAMES}
    preds = {name: p_goal(m, eval_df[FEATURE_SETS[name]]) for name, m in models.items()}
    is_head = (eval_df["competition_gender"] == SHOT_HEADLINE_GENDER).to_numpy()

    model_metrics = {}
    for name, p in preds.items():
        model_metrics[name] = {
            "headline": metric_block(head["label"], p[is_head]),
            "other_gender": metric_block(other["label"], p[~is_head]) if len(other) else None,
            "all_eval": metric_block(eval_df["label"], p),
        }
        logger.info("%-14s headline brier=%.4f log_loss=%.4f auc=%.3f", name,
                    model_metrics[name]["headline"]["brier_score"],
                    model_metrics[name]["headline"]["log_loss"],
                    model_metrics[name]["headline"]["roc_auc"])

    # "Before": the shipped v1 setup — distance+angle logistic fit on WC 2018 only.
    wc18 = train_df[train_df["tournament"] == "fifa_world_cup_2018"]
    legacy = MODEL_FACTORIES["logistic_xg"]().fit(wc18[LOGISTIC_FEATURES], wc18["label"])
    legacy_p = p_goal(legacy, head[LOGISTIC_FEATURES])
    sb_p = head["sb_xg_benchmark"].to_numpy()

    # Ablation: production model without women's training shots.
    mens_train = train_df[train_df["competition_gender"] == SHOT_HEADLINE_GENDER]
    prod_feats = FEATURE_SETS[prod]
    ablation = MODEL_FACTORIES[prod]().fit(mens_train[prod_feats], mens_train["label"])
    ablation_p = p_goal(ablation, head[prod_feats])

    prod_head_p = preds[prod][is_head]
    metrics = {
        "run_id": run_dir.name,
        "run_date": date.today().isoformat(),
        "production_model": prod,
        "model_selection": selection,
        "headline_gender": SHOT_HEADLINE_GENDER,
        "n_train": int(len(train_df)),
        "n_train_by_gender": {k: int(v) for k, v in train_df["competition_gender"].value_counts().items()},
        "n_eval": int(len(eval_df)),
        "n_eval_headline": int(len(head)),
        "eval_tournaments": sorted(eval_df["tournament"].unique()),
        "train_conversion": round(conversion_rate(train_df), 4),
        "eval_conversion": round(conversion_rate(eval_df), 4),
        "n_features": {k: len(v) for k, v in FEATURE_SETS.items()},
        "models": model_metrics,
        "legacy_v1_wc2018_distance_angle": metric_block(head["label"], legacy_p),
        "statsbomb_reference": metric_block(head["label"], sb_p),
        "paired_bootstrap_headline": {
            "gbm_full_minus_logistic_full": paired_bootstrap_diff(
                head, preds["gbm_full"][is_head], preds["logistic_full"][is_head]),
            "logistic_full_minus_legacy_v1": paired_bootstrap_diff(
                head, preds["logistic_full"][is_head], legacy_p),
        },
        "ablation_mens_only_training": {
            "model": prod, "n_train": int(len(mens_train)),
            "headline": metric_block(head["label"], ablation_p),
        },
        "calibration": {
            "model": prod,
            "headline": calibration_buckets(head["label"], prod_head_p),
            "all_eval": calibration_buckets(eval_df["label"], preds[prod]),
        },
        "per_match": {"model": prod, **per_match_totals(eval_df, preds[prod])},
        "join_coverage_wc": join_coverage,
    }
    if prod.startswith("logistic"):
        metrics["logistic_full_coefficients"] = logistic_coefficients(models["logistic_full"])

    out = run_dir / "shot_xg_metrics.json"
    out.write_text(json.dumps(metrics, indent=2))
    summary = {k: metrics[k] for k in ("production_model", "n_train", "n_eval_headline")}
    summary["headline"] = {n: model_metrics[n]["headline"] for n in MODEL_NAMES}
    summary["legacy_v1"] = metrics["legacy_v1_wc2018_distance_angle"]
    summary["statsbomb_reference"] = metrics["statsbomb_reference"]
    summary["ablation_mens_only"] = metrics["ablation_mens_only_training"]["headline"]
    summary["paired_bootstrap"] = metrics["paired_bootstrap_headline"]
    summary["calibration_ece"] = metrics["calibration"]["headline"]["ece"]
    summary["per_match"] = metrics["per_match"]["summary"]
    print(json.dumps(summary, indent=2))
    logger.info("Wrote %s", out)


if __name__ == "__main__":
    main()
