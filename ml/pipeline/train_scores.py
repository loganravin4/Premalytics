"""
Score-model training pipeline.

Fits two independent Poisson regressions on the pivoted WC feature matrix:
  home_goals model -> target goals_for   (home team goals)
  away_goals model -> target goals_against (away team goals)

Chronological split on the same TRAIN_CUTOFF_DATE as the match predictor.
If the xG rolling features are entirely null/zero in the training window the
models fall back to goal-average features only.

Artifacts -> ml/artifacts/score_{run_ts}/ :
    home_goals.joblib, away_goals.joblib,
    score_features.joblib      (pivoted matrix, for predict_scores lookups)
    score_feature_cols.json    ({use_xg, features})
and a pointer in ml/artifacts/latest_score_run.txt.

Usage:
    python -m ml.pipeline.train_scores
"""

import json
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import mean_absolute_error

from ml.config import (
    ARTIFACTS_DIR, COMPETITIONS_TRAIN, TRAIN_CUTOFF_DATE, RANDOM_SEED, LOG_FORMAT,
)
from ml.features.loader import load_raw_matches, validate_data_contract
from ml.features.engineering import build_features
from ml.models.score_predictor import (
    make_home_goals_pipeline, make_away_goals_pipeline,
    prepare_score_features, feature_columns, XG_NUMERIC,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)
np.random.seed(RANDOM_SEED)

HOME_TARGET = "goals_for"       # home team goals (home-perspective pivot row)
AWAY_TARGET = "goals_against"   # away team goals


def load_score_features() -> pd.DataFrame:
    """Pivoted single-row match matrix with both goal targets present."""
    raw = load_raw_matches(COMPETITIONS_TRAIN)
    validate_data_contract(raw)
    feats = build_features(raw)
    return feats.dropna(subset=[HOME_TARGET, AWAY_TARGET]).reset_index(drop=True)


def _detect_use_xg(train_df: pd.DataFrame) -> bool:
    """True iff any xG rolling feature is present and non-zero in the train split."""
    xg = train_df.reindex(columns=XG_NUMERIC)
    vals = pd.to_numeric(xg.stack(), errors="coerce") if len(xg.columns) else pd.Series(dtype=float)
    return bool(vals.notna().any() and (vals.fillna(0.0) != 0.0).any())


def main() -> None:
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_DIR / f"score_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    feats = load_score_features()
    cutoff = pd.Timestamp(TRAIN_CUTOFF_DATE)
    train_df = feats[feats["match_date"] < cutoff]
    eval_df = feats[feats["match_date"] >= cutoff]

    use_xg = _detect_use_xg(train_df)
    logger.info("use_xg=%s (xG features %s)", use_xg,
                "active" if use_xg else "all null/zero — goal-average fallback")

    X_train = prepare_score_features(train_df, use_xg)
    y_home = train_df[HOME_TARGET].astype(float)
    y_away = train_df[AWAY_TARGET].astype(float)

    home_model = make_home_goals_pipeline(use_xg)
    away_model = make_away_goals_pipeline(use_xg)
    home_model.fit(X_train, y_home)
    away_model.fit(X_train, y_away)

    mae_home = mae_away = float("nan")
    if len(eval_df):
        X_eval = prepare_score_features(eval_df, use_xg)
        mae_home = float(mean_absolute_error(eval_df[HOME_TARGET], home_model.predict(X_eval)))
        mae_away = float(mean_absolute_error(eval_df[AWAY_TARGET], away_model.predict(X_eval)))

    joblib.dump(home_model, run_dir / "home_goals.joblib")
    joblib.dump(away_model, run_dir / "away_goals.joblib")
    joblib.dump(feats, run_dir / "score_features.joblib")
    (run_dir / "score_feature_cols.json").write_text(json.dumps(
        {"use_xg": use_xg, "features": feature_columns(use_xg)}, indent=2))
    (ARTIFACTS_DIR / "latest_score_run.txt").write_text(run_dir.name)

    logger.info("n_train=%d  n_eval=%d", len(train_df), len(eval_df))
    logger.info("MAE home goals=%.3f  MAE away goals=%.3f", mae_home, mae_away)
    logger.info("Score models saved to %s", run_dir)
    logger.info("Next: python -m ml.pipeline.predict_scores --fixtures ...")


if __name__ == "__main__":
    main()
