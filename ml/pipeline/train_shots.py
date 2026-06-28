"""
Shot xG training pipeline (XG-03).

Loads WC 2018 + WC 2022 shot data, applies contract filters (drop
body_part=="other" and any is_penalty==True), splits time-based
(2018=train, 2022=eval), and fits the logistic baseline and GBM xG models.

Artifacts -> ml/artifacts/shot_xg_{run_ts}/ :
    logistic_xg.joblib, gbm_xg.joblib, shot_feature_cols.json
and a pointer in ml/artifacts/latest_shot_run.txt.

Usage:
    python -m ml.pipeline.train_shots
"""

import json
import logging
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from ml.config import ARTIFACTS_DIR, DATA_DIR, RANDOM_SEED, LOG_FORMAT
from ml.models.shot_xg import (
    make_logistic_xg_pipeline, make_gbm_xg_pipeline,
    LOGISTIC_FEATURES, GBM_FEATURES,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)
np.random.seed(RANDOM_SEED)

SHOT_DIR = DATA_DIR / "shots"
TRAIN_SEASON = "2018"
EVAL_SEASON = "2022"
LABEL_COL = "is_goal"


def load_shots() -> pd.DataFrame:
    """
    Load both shot CSVs, apply contract filters, and normalise dtypes.

    Filters: drop body_part=="other" (outside the xG feature enum) and any
    is_penalty==True row (penalties are excluded from xG training).
    """
    frames = []
    for season in (TRAIN_SEASON, EVAL_SEASON):
        path = SHOT_DIR / f"wc_shots_{season}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Shot data not found: {path}. Regenerate with "
                f"python data-pipeline/scripts/shots/01_export_statsbomb_shots.py"
            )
        frames.append(pd.read_csv(path))

    df = pd.concat(frames, ignore_index=True)
    df["season_id"] = df["season_id"].astype(str)

    df = df[df["body_part"] != "other"]
    df = df[~df["is_penalty"].astype(bool)]

    df["under_pressure"] = df["under_pressure"].astype(int)
    df["label"] = df[LABEL_COL].astype(int)
    return df.reset_index(drop=True)


def split_shots(df: pd.DataFrame):
    """Time-based split: WC 2018 = train, WC 2022 = eval."""
    train = df[df["season_id"] == TRAIN_SEASON]
    eval_ = df[df["season_id"] == EVAL_SEASON]
    return train, eval_


def conversion_rate(df: pd.DataFrame) -> float:
    return float(df["label"].mean()) if len(df) else 0.0


def main() -> None:
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_DIR / f"shot_xg_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    df = load_shots()
    train_df, eval_df = split_shots(df)
    y_train = train_df["label"]

    logger.info(
        "n_train=%d  n_eval=%d  n_features=%d (gbm) / %d (logistic)  "
        "train_conversion=%.3f  eval_conversion=%.3f",
        len(train_df), len(eval_df), len(GBM_FEATURES), len(LOGISTIC_FEATURES),
        conversion_rate(train_df), conversion_rate(eval_df),
    )

    models = {
        "logistic_xg": (make_logistic_xg_pipeline(), LOGISTIC_FEATURES),
        "gbm_xg":      (make_gbm_xg_pipeline(),      GBM_FEATURES),
    }
    for name, (pipe, feats) in models.items():
        logger.info("Training %s on %s ...", name, feats)
        pipe.fit(train_df[feats], y_train)
        joblib.dump(pipe, run_dir / f"{name}.joblib")
        logger.info("Saved %s -> %s", name, run_dir / f"{name}.joblib")

    (run_dir / "shot_feature_cols.json").write_text(json.dumps({
        "logistic_xg": LOGISTIC_FEATURES,
        "gbm_xg": GBM_FEATURES,
    }, indent=2))
    (ARTIFACTS_DIR / "latest_shot_run.txt").write_text(run_dir.name)

    logger.info("Shot xG training complete. Artifacts in %s", run_dir)
    logger.info("Next: python -m ml.pipeline.evaluate_shots")


if __name__ == "__main__":
    main()
