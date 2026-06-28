"""
Shot xG evaluation pipeline (XG-03).

Loads the latest shot run, evaluates both models on the WC 2022 eval split
(Brier score + log loss), and runs a shot->match join coverage check.

Writes ml/artifacts/{shot_run_dir}/shot_metrics.json and prints it.

Usage:
    python -m ml.pipeline.evaluate_shots [--run-id RUN_ID]
"""

import argparse
import json
import logging
from datetime import date
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ml.config import ARTIFACTS_DIR, DATA_DIR, LOG_FORMAT
from ml.models.shot_xg import GBM_FEATURES
from ml.pipeline.train_shots import (
    load_shots, split_shots, conversion_rate, TRAIN_SEASON, EVAL_SEASON,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

MODEL_NAMES = ["logistic_xg", "gbm_xg"]
JOIN_COVERAGE_THRESHOLD = 0.90


def _resolve_run_dir(run_id: str | None) -> Path:
    if run_id:
        d = ARTIFACTS_DIR / run_id
        if not d.exists():
            raise FileNotFoundError(f"Run directory not found: {d}")
        return d
    latest = ARTIFACTS_DIR / "latest_shot_run.txt"
    if not latest.exists():
        raise FileNotFoundError(
            "No latest_shot_run.txt — run python -m ml.pipeline.train_shots first."
        )
    return ARTIFACTS_DIR / latest.read_text().strip()


def _p_goal(model, X):
    """Probability of the positive (goal) class, robust to class ordering."""
    proba = model.predict_proba(X)
    goal_idx = list(model.classes_).index(1)
    return proba[:, goal_idx]


def check_join_coverage(shots: pd.DataFrame) -> float:
    """Fraction of shot rows whose match_id exists in the WC match data."""
    match_ids: set = set()
    for season in (TRAIN_SEASON, EVAL_SEASON):
        mpath = DATA_DIR / "fifa_world_cup" / season / "match_logs_normalized.csv"
        if mpath.exists():
            match_ids.update(pd.read_csv(mpath)["match_id"].astype(str))
        else:
            logger.warning("Match data missing for join check: %s", mpath)

    if not match_ids:
        logger.warning("No match data available — skipping join coverage check")
        return 0.0

    coverage = shots["match_id"].astype(str).isin(match_ids).mean()
    if coverage < JOIN_COVERAGE_THRESHOLD:
        logger.warning("Shot->match join coverage %.1f%% is below %.0f%% threshold",
                       coverage * 100, JOIN_COVERAGE_THRESHOLD * 100)
    else:
        logger.info("Shot->match join coverage: %.1f%%", coverage * 100)
    return float(coverage)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate shot xG models on WC 2022")
    parser.add_argument("--run-id", default=None, help="Run dir name (default: latest)")
    args = parser.parse_args()

    run_dir = _resolve_run_dir(args.run_id)
    logger.info("Evaluating shot run: %s", run_dir.name)

    df = load_shots()
    check_join_coverage(df)

    train_df, eval_df = split_shots(df)
    feature_cols = json.loads((run_dir / "shot_feature_cols.json").read_text())
    y_eval = eval_df["label"]

    model_metrics = {}
    for name in MODEL_NAMES:
        model = joblib.load(run_dir / f"{name}.joblib")
        X_eval = eval_df[feature_cols[name]]
        p_goal = _p_goal(model, X_eval)
        brier = brier_score_loss(y_eval, p_goal)
        ll = log_loss(y_eval, p_goal, labels=[0, 1])
        model_metrics[name] = {"brier_score": float(brier), "log_loss": float(ll)}
        logger.info("%s: brier=%.4f  log_loss=%.4f", name, brier, ll)

    metrics = {
        "run_date": date.today().isoformat(),
        "n_train": int(len(train_df)),
        "n_eval": int(len(eval_df)),
        "n_features": len(GBM_FEATURES),
        "train_conversion": conversion_rate(train_df),
        "eval_conversion": conversion_rate(eval_df),
        "models": model_metrics,
    }

    (run_dir / "shot_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
