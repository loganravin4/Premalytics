"""
Shot-level expected-goals (xG) models.

Every pipeline exposes predict_proba(X) -> [[p_no_goal, p_goal]].

  1. logistic_xg   — baseline: distance_m + angle_deg only. Kept because
                     data-pipeline/scripts/06_backfill_xg.py loads it by name.
  2. logistic_full — the full at-release feature set (location, body part,
                     technique, assist type, pressure, first-time, freeze-frame
                     defender/keeper context). Median-imputes freeze-frame gaps
                     (ff_available flags them), scales, one-hots categoricals.
  3. gbm_full      — same features, XGBoost (HistGradientBoosting fallback).
                     Not wrapped in a calibrator: on the validation fold the
                     raw log-loss objective was better calibrated than
                     isotonic (LL 0.2417 vs 0.2422) or sigmoid (0.2465).
  4. grid_xg       — logistic on distance, angle, body part, situation only.
                     Powers xg_grid.json: the frontend xG lab can only vary
                     those inputs, so its grid comes from a model that uses
                     exactly them instead of fixing defender positions.

Label: is_goal. All inputs are known at the moment the shot is taken; see the
FORBIDDEN COLUMNS in docs/DATA_CONTRACT_SHOTS.md. FORBIDDEN_FEATURES below is
the machine-checked version of that list.

Which model is production is decided in ml/pipeline/train_shots.py on a
time-ordered validation tournament and recorded in production_model.json.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.config import RANDOM_SEED

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature sets (see docs/DATA_CONTRACT_SHOTS.md)
# ---------------------------------------------------------------------------
LOGISTIC_FEATURES = ["distance_m", "angle_deg"]

BODY_PART_CATEGORIES = ["right_foot", "left_foot", "head"]
SITUATION_CATEGORIES = ["open_play", "set_piece", "counter"]
TECHNIQUE_CATEGORIES = ["normal", "volley", "half_volley", "lob", "backheel",
                        "diving_header", "overhead_kick"]
ASSIST_CATEGORIES = ["none", "pass", "cross", "through_ball", "cut_back"]

# Freeze-frame columns are NaN when the frame is missing.
FREEZE_FRAME_FEATURES = ["n_def_in_cone", "nearest_def_m", "gk_dist_to_goal_m",
                         "gk_dist_to_shooter_m", "gk_angle_offset_deg"]

FULL_NUMERIC = (
    ["distance_m", "angle_deg", "log_distance", "under_pressure", "first_time",
     "ff_available", "is_womens"]
    + FREEZE_FRAME_FEATURES
)
FULL_CATEGORICAL = ["body_part", "situation", "technique", "assist_type"]
FULL_FEATURES = FULL_NUMERIC + FULL_CATEGORICAL
_FULL_CATS = [BODY_PART_CATEGORIES, SITUATION_CATEGORIES, TECHNIQUE_CATEGORIES, ASSIST_CATEGORIES]

GRID_NUMERIC = ["distance_m", "angle_deg", "log_distance"]
GRID_CATEGORICAL = ["body_part", "situation"]
GRID_FEATURES = GRID_NUMERIC + GRID_CATEGORICAL

# Back-compat names used by older tests / callers.
GBM_NUMERIC = FULL_NUMERIC
GBM_CATEGORICAL = FULL_CATEGORICAL
GBM_FEATURES = FULL_FEATURES

FEATURE_SETS = {
    "logistic_xg": LOGISTIC_FEATURES,
    "logistic_full": FULL_FEATURES,
    "gbm_full": FULL_FEATURES,
    "grid_xg": GRID_FEATURES,
}

# Post-shot or provider-model columns. Never a model input.
FORBIDDEN_FEATURES = {
    "is_goal", "label", "outcome", "shot_outcome", "end_location", "end_x", "end_y", "end_z",
    "statsbomb_xg", "sb_xg_benchmark", "keeper_dive_direction", "rebound_outcome",
    "hit_post", "hit_woodwork", "var_outcome", "goal_disallowed",
    # identifiers: not leakage, but never features
    "shot_id", "match_id", "player_id", "player_name",
}

try:
    from xgboost import XGBClassifier  # type: ignore
    HAVE_XGBOOST = True
except ImportError:
    HAVE_XGBOOST = False


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add model-ready derived columns. Pure function of at-release inputs."""
    out = df.copy()
    out["log_distance"] = np.log1p(out["distance_m"].astype(float))
    for col in ("under_pressure", "first_time", "ff_available"):
        if col in out:
            out[col] = out[col].fillna(False).astype(int)
    if "competition_gender" in out:
        out["is_womens"] = (out["competition_gender"] == "female").astype(int)
    elif "is_womens" not in out:
        out["is_womens"] = 0
    for col in FREEZE_FRAME_FEATURES:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _one_hot(categories):
    return OneHotEncoder(categories=categories, handle_unknown="ignore")


def make_logistic_xg_pipeline() -> Pipeline:
    """Logistic xG baseline on distance + angle only."""
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_SEED)),
    ])


def make_logistic_full_pipeline(C: float = 1.0) -> Pipeline:
    """Logistic on the full at-release feature set."""
    prep = ColumnTransformer([
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), FULL_NUMERIC),
        ("cat", _one_hot(_FULL_CATS), FULL_CATEGORICAL),
    ])
    return Pipeline([
        ("prep", prep),
        ("clf", LogisticRegression(C=C, max_iter=3000, random_state=RANDOM_SEED)),
    ])


def make_grid_xg_pipeline() -> Pipeline:
    """Logistic on distance, angle, body part, situation (the xG-lab inputs)."""
    prep = ColumnTransformer([
        ("num", StandardScaler(), GRID_NUMERIC),
        ("cat", _one_hot([BODY_PART_CATEGORIES, SITUATION_CATEGORIES]), GRID_CATEGORICAL),
    ])
    return Pipeline([
        ("prep", prep),
        ("clf", LogisticRegression(max_iter=2000, random_state=RANDOM_SEED)),
    ])


def _make_gbm_estimator():
    """XGBoost if available, else HistGradientBoosting. Both accept NaN."""
    if HAVE_XGBOOST:
        return XGBClassifier(
            n_estimators=400,
            learning_rate=0.03,
            max_depth=3,
            min_child_weight=10,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=5.0,
            eval_metric="logloss",
            random_state=RANDOM_SEED,
            n_jobs=4,
        )
    logger.info("shot_xg GBM: xgboost not installed — using HistGradientBoostingClassifier")
    return HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.03, max_depth=3, min_samples_leaf=40,
        l2_regularization=5.0, random_state=RANDOM_SEED,
    )


def make_gbm_full_pipeline() -> Pipeline:
    """
    GBM on the full feature set. Numerics pass through untouched (NaN is
    handled natively); categoricals are one-hot with fixed categories so
    train, eval, and single-shot inference encode identically.
    """
    prep = ColumnTransformer([
        ("num", "passthrough", FULL_NUMERIC),
        ("cat", _one_hot(_FULL_CATS), FULL_CATEGORICAL),
    ], sparse_threshold=0)
    return Pipeline([("prep", prep), ("clf", _make_gbm_estimator())])


# Old name kept for callers that still import it.
make_gbm_xg_pipeline = make_gbm_full_pipeline

MODEL_FACTORIES = {
    "logistic_xg": make_logistic_xg_pipeline,
    "logistic_full": make_logistic_full_pipeline,
    "gbm_full": make_gbm_full_pipeline,
    "grid_xg": make_grid_xg_pipeline,
}


def p_goal(model, X: pd.DataFrame) -> np.ndarray:
    """Probability of the goal class, robust to class ordering."""
    proba = model.predict_proba(X)
    return proba[:, list(model.classes_).index(1)]
