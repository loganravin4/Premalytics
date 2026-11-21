"""Train the logistic baseline and the gradient-boosting match model, split chronologically on TRAIN_CUTOFF_DATE.

Usage: python -m ml.pipeline.train
"""

import json
import logging
from datetime import datetime

import joblib
import numpy as np
import pandas as pd

from ml.config import (
    ARTIFACTS_DIR, RANDOM_SEED, TARGET_COL, TARGET_ENCODE,
    COMPETITIONS_TRAIN, TRAIN_CUTOFF_DATE, LOG_FORMAT,
    TOURNAMENT_WEIGHTS,
)
from ml.features.loader import load_raw_matches, validate_data_contract
from ml.features.engineering import build_features, get_feature_columns
from ml.models.baselines import make_logistic_pipeline
from ml.models.gradient_boost import make_best_boosting_pipeline

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

np.random.seed(RANDOM_SEED)


# Listed explicitly rather than trusting get_feature_columns() to return a clean set.
NON_FEATURE_COLS = [
    "home_competition_id", "home_competition_stage", "home_group_name",
    "home_source", "home_source_match_key",
    "away_competition_id", "away_competition_stage", "away_group_name",
    "away_source", "away_source_match_key",
    "match_id", "season_id", "home_team", "away_team", "venue",
    "match_outcome", "match_date",
    "home_sample_weight", "away_sample_weight",
    "home_confederation", "away_confederation",
]

# Fixed so train, eval and future data always get identical dummy columns.
CONFEDERATIONS = ["UEFA", "CONMEBOL", "CONCACAF", "CAF", "AFC", "OFC", "OTHER"]
CONFEDERATION_COLS = ["home_confederation", "away_confederation"]


def _one_hot_confederation(features: pd.DataFrame) -> list[str]:
    # Mutates in place so the dummies reach train_df, eval_df and the features.joblib predict.py reads.
    added: list[str] = []
    for col in CONFEDERATION_COLS:
        if col not in features.columns:
            continue
        cat = pd.Categorical(
            features[col].fillna("OTHER").astype(str), categories=CONFEDERATIONS
        )
        dummies = pd.get_dummies(cat, prefix=col).astype(float)
        for dcol in dummies.columns:
            features[dcol] = dummies[dcol].values
            added.append(dcol)
    return added


def select_feature_columns(features: pd.DataFrame) -> list[str]:
    """Numeric model-feature columns; also one-hot encodes confederation in place."""
    _one_hot_confederation(features)
    candidates = [c for c in get_feature_columns(features) if c not in NON_FEATURE_COLS]
    # Numeric-only backstop so no object column can reach sklearn.
    return [c for c in candidates if pd.api.types.is_numeric_dtype(features[c])]


def build_xy(features: pd.DataFrame, feature_cols: list[str]):
    """Return (X, y, weights)."""
    # NaN here means no prior history or no xG data, i.e. genuinely no information, so 0 is correct.
    X = features[feature_cols].fillna(0.0).astype(float)
    y = features[TARGET_COL].map(TARGET_ENCODE)

    if "home_sample_weight" in features.columns:
        weights = pd.to_numeric(features["home_sample_weight"], errors="coerce")
        weights = weights.fillna(1.0).astype(float)
        if (weights <= 0).all():
            weights = pd.Series(1.0, index=features.index)
    else:
        weights = pd.Series(1.0, index=features.index)

    # TOURNAMENT_WEIGHTS is the single source of truth and overrides the baked home_sample_weight.
    if "home_competition_id" in features.columns:
        weights = (
            features["home_competition_id"].map(TOURNAMENT_WEIGHTS).fillna(1.0).astype(float)
        )

    logger.info(
        f"sample_weight (post-boost): mean={weights.mean():.3f}  "
        f"min={weights.min():.3f}  max={weights.max():.3f}"
    )
    return X, y, weights


def load_wc_features() -> pd.DataFrame:
    raw = load_raw_matches(COMPETITIONS_TRAIN)
    validate_data_contract(raw)
    features = build_features(raw)
    return features.dropna(subset=[TARGET_COL]).reset_index(drop=True)


def split_train_eval(features: pd.DataFrame):
    # Chronological, never shuffled, so eval matches are all after every training match.
    cutoff = pd.Timestamp(TRAIN_CUTOFF_DATE)
    train = features[features["match_date"] < cutoff]
    eval_ = features[features["match_date"] >= cutoff]
    return train, eval_


def main() -> None:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Run ID: {run_id}  ->  {run_dir}")

    features = load_wc_features()
    feature_cols = select_feature_columns(features)
    train_df, eval_df = split_train_eval(features)

    X_train, y_train, w_train = build_xy(train_df, feature_cols)

    logger.info(
        f"n_train={len(X_train)}  n_eval={len(eval_df)}  n_features={len(feature_cols)}"
    )
    logger.info(
        f"sample_weight: mean={w_train.mean():.3f}  "
        f"min={w_train.min():.3f}  max={w_train.max():.3f}"
    )

    models = {
        "logistic_regression": make_logistic_pipeline(),
        "gradient_boosting":   make_best_boosting_pipeline(),
    }
    for name, model in models.items():
        logger.info(f"Training {name}...")
        model.fit(X_train, y_train, clf__sample_weight=w_train.to_numpy())
        model_path = run_dir / f"{name}.joblib"
        joblib.dump(model, model_path)
        logger.info(f"Saved {name} -> {model_path}")

    # evaluate.py and predict.py need the exact column order and the matrix to look up team form.
    (run_dir / "feature_cols.json").write_text(json.dumps(feature_cols, indent=2))
    joblib.dump(features, run_dir / "features.joblib")

    (ARTIFACTS_DIR / "latest_run.txt").write_text(run_id)
    logger.info(f"Training complete. Artifacts in {run_dir}")
    logger.info("Next: python -m ml.pipeline.evaluate")


if __name__ == "__main__":
    main()
