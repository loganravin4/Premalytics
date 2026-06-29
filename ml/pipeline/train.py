"""
WC-06 training pipeline.

Loads FIFA World Cup match data, builds leakage-safe features, splits
chronologically on TRAIN_CUTOFF_DATE (WC 2018 = train, WC 2022 = eval),
and fits a logistic-regression baseline and a gradient-boosting model.

Both fitted models, the pivoted feature matrix, and the feature-column
list are saved under ml/artifacts/{run_timestamp}/. A pointer to the run
is written to ml/artifacts/latest_run.txt.

Usage:
    python -m ml.pipeline.train
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


# Columns that must never be fed to sklearn: string metadata, identifiers,
# the target, the split key, and row weights. Listed explicitly (per WC-06)
# rather than trusting get_feature_columns() to return a clean set. The
# remaining selection also filters to numeric dtypes as a backstop.
NON_FEATURE_COLS = [
    "home_competition_id", "home_competition_stage", "home_group_name",
    "home_source", "home_source_match_key",
    "away_competition_id", "away_competition_stage", "away_group_name",
    "away_source", "away_source_match_key",
    "match_id", "season_id", "home_team", "away_team", "venue",
    "match_outcome", "match_date",
    # Sample weights are row weights, not predictive features.
    "home_sample_weight", "away_sample_weight",
]


def select_feature_columns(features: pd.DataFrame) -> list[str]:
    """
    Numeric model-feature columns only.

    Starts from the home_/away_/diff_ prefixed candidates, drops the known
    metadata columns by name, then keeps only numeric dtypes so no object
    column can ever reach sklearn.
    """
    candidates = [c for c in get_feature_columns(features) if c not in NON_FEATURE_COLS]
    return [c for c in candidates if pd.api.types.is_numeric_dtype(features[c])]


def build_xy(features: pd.DataFrame, feature_cols: list[str]):
    """
    Return (X, y, weights).

    X: numeric feature matrix with every remaining NaN filled to 0. For WC
       data this is correct — NULL xG/shots and no-prior-history rolling
       stats are genuine "no information" cases, not missing measurements.
    y: match_outcome encoded via TARGET_ENCODE (H=2, D=1, A=0).
    weights: per-row training weights from TOURNAMENT_WEIGHTS keyed on
       home_competition_id (Euro/Copa 1.5, WC 1.0, friendly 0.3, etc.).
       TOURNAMENT_WEIGHTS is the single source of truth — the baked
       home_sample_weight column is ignored. Competitions absent from
       TOURNAMENT_WEIGHTS fall back to 1.0.
    """
    X = features[feature_cols].fillna(0.0).astype(float)
    y = features[TARGET_COL].map(TARGET_ENCODE)

    if "home_sample_weight" in features.columns:
        weights = pd.to_numeric(features["home_sample_weight"], errors="coerce")
        # Per-row fallback: any missing weight defaults to 1.0 (never drop a row).
        weights = weights.fillna(1.0).astype(float)
        if (weights <= 0).all():  # degenerate column — treat as unweighted
            weights = pd.Series(1.0, index=features.index)
    else:
        weights = pd.Series(1.0, index=features.index)

    # TOURNAMENT_WEIGHTS is the single source of truth for per-competition
    # training weights: each row's weight is its competition's configured value
    # (Euro/Copa 1.5, WC 1.0, friendly 0.3, ...), overriding the baked
    # home_sample_weight column entirely. home_competition_id is metadata
    # excluded from X but still present here; competitions absent from
    # TOURNAMENT_WEIGHTS fall back to 1.0.
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
    """Load WC data and build the single-row-per-match feature matrix."""
    raw = load_raw_matches(COMPETITIONS_TRAIN)
    validate_data_contract(raw)
    features = build_features(raw)
    return features.dropna(subset=[TARGET_COL]).reset_index(drop=True)


def split_train_eval(features: pd.DataFrame):
    """Chronological split on TRAIN_CUTOFF_DATE (no shuffle)."""
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

    # Both factories already exist in ml/models/ — used as-is. Per-row training
    # weights are routed to each pipeline's final 'clf' step (LogisticRegression
    # and CalibratedClassifierCV both accept sample_weight).
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

    # Persist the feature order and the pivoted matrix so evaluate.py and
    # predict.py reproduce the exact same X / look up team form.
    (run_dir / "feature_cols.json").write_text(json.dumps(feature_cols, indent=2))
    joblib.dump(features, run_dir / "features.joblib")

    (ARTIFACTS_DIR / "latest_run.txt").write_text(run_id)
    logger.info(f"Training complete. Artifacts in {run_dir}")
    logger.info("Next: python -m ml.pipeline.evaluate")


if __name__ == "__main__":
    main()
