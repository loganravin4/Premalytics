"""
Shot-level expected-goals (xG) models.

Two sklearn pipelines, both exposing predict_proba(X) -> [[p_no_goal, p_goal]]:

  1. Logistic baseline  — distance_m + angle_deg only (StandardScaler -> LR).
  2. Gradient-boosted    — distance_m, angle_deg, body_part (one-hot),
                           situation (one-hot), under_pressure (bool->int).
                           Uses XGBoost if installed, else HistGradientBoosting.

Label: is_goal (bool -> int, True=1). All features are known at the moment the
shot is taken (see docs/DATA_CONTRACT_SHOTS.md FORBIDDEN COLUMNS).

Production model: on WC 2018/2022 the **logistic baseline currently
outperforms the calibrated GBM** (eval log loss 0.300 vs 0.329; Brier ~tied),
so the logistic model is what ml/pipeline/predict_shot.py serves. The GBM is
retained as experimental and is expected to overtake the baseline once more
data (Copa América) and/or a real XGBoost backend are added.
"""

import logging

from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.config import RANDOM_SEED

logger = logging.getLogger(__name__)

# Feature groups (see docs/DATA_CONTRACT_SHOTS.md).
LOGISTIC_FEATURES = ["distance_m", "angle_deg"]

GBM_NUMERIC = ["distance_m", "angle_deg", "under_pressure"]
GBM_CATEGORICAL = ["body_part", "situation"]
GBM_FEATURES = GBM_NUMERIC + GBM_CATEGORICAL

# Stable one-hot categories so the encoder is deterministic across train/eval/infer.
BODY_PART_CATEGORIES = ["right_foot", "left_foot", "head"]
SITUATION_CATEGORIES = ["open_play", "set_piece", "counter"]

try:
    from xgboost import XGBClassifier  # type: ignore
    HAVE_XGBOOST = True
except ImportError:
    HAVE_XGBOOST = False


def make_logistic_xg_pipeline() -> Pipeline:
    """Logistic xG baseline on distance + angle only."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)),
    ])


def _make_gbm_estimator():
    """XGBoost if available, else HistGradientBoosting (both handle the same X)."""
    if HAVE_XGBOOST:
        logger.info("shot_xg GBM: using XGBClassifier")
        return XGBClassifier(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            random_state=RANDOM_SEED,
        )
    logger.info("shot_xg GBM: xgboost not installed — using HistGradientBoostingClassifier")
    return HistGradientBoostingClassifier(
        max_iter=300,
        learning_rate=0.05,
        max_depth=4,
        min_samples_leaf=20,
        random_state=RANDOM_SEED,
    )


def make_gbm_xg_pipeline() -> CalibratedClassifierCV:
    """
    GBM xG model: distance + angle + under_pressure (numeric) and one-hot
    body_part + situation. Categories are fixed so encoding is identical at
    train, eval, and single-shot inference time.

    Wrapped in isotonic CalibratedClassifierCV: raw GBM probabilities are
    poorly tuned to the ~8-10% base conversion rate, so calibration is what
    makes the extra features pay off in log loss / Brier. The wrapper still
    exposes predict_proba(), so the interface is unchanged for callers.
    """
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", GBM_NUMERIC),
            ("cat", OneHotEncoder(
                categories=[BODY_PART_CATEGORIES, SITUATION_CATEGORIES],
                handle_unknown="ignore",
            ), GBM_CATEGORICAL),
        ],
    )
    pipe = Pipeline([
        ("prep", preprocessor),
        ("clf", _make_gbm_estimator()),
    ])
    return CalibratedClassifierCV(pipe, method="isotonic", cv=5)
