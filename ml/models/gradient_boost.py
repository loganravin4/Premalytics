"""
Gradient boosting model for match outcome prediction.

Uses sklearn's HistGradientBoostingClassifier as the primary model because:
  - Native NaN handling (no imputation step needed)
  - Fast training on small datasets (< 10k rows)
  - Competitive accuracy with LightGBM on tabular data this size

If lightgbm is installed, LGBMClassifier is used instead (faster, better
calibrated out-of-the-box). Install with: pip install lightgbm
"""

import logging

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

from ml.config import RANDOM_SEED

try:
    from lightgbm import LGBMClassifier
except ImportError:  # optional dependency
    LGBMClassifier = None

logger = logging.getLogger(__name__)


def make_hgb_pipeline(
    max_iter: int = 300,
    learning_rate: float = 0.05,
    max_depth: int = 4,
    min_samples_leaf: int = 20,
    calibrate: bool = True,
) -> Pipeline:
    """
    HistGradientBoostingClassifier with optional Platt scaling calibration.

    Hyperparameters are set conservatively to avoid overfitting on ~1,500 training
    rows (two seasons × ~760 rows/season). Use walk-forward CV to tune.

    Args:
        calibrate: Wrap in CalibratedClassifierCV for better probability estimates.
    """
    hgb = HistGradientBoostingClassifier(
        max_iter=max_iter,
        learning_rate=learning_rate,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        random_state=RANDOM_SEED,
        class_weight="balanced",
        early_stopping=False,
    )

    if calibrate:
        # Isotonic calibration — better than sigmoid for multi-class
        clf = CalibratedClassifierCV(hgb, cv=3, method="isotonic")
    else:
        clf = hgb

    # HistGBM handles NaN natively, so no imputer step needed
    return Pipeline([("clf", clf)])


def _try_lightgbm(
    n_estimators: int = 300,
    learning_rate: float = 0.05,
    num_leaves: int = 31,
    min_child_samples: int = 20,
    calibrate: bool = True,
) -> Pipeline:
    """
    LightGBM classifier if the package is installed; falls back to HGB otherwise.
    """
    try:
        if LGBMClassifier is None:
            raise ImportError
        lgbm = LGBMClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            num_leaves=num_leaves,
            min_child_samples=min_child_samples,
            random_state=RANDOM_SEED,
            class_weight="balanced",
            verbose=-1,
        )
        if calibrate:
            clf = CalibratedClassifierCV(lgbm, cv=3, method="isotonic")
        else:
            clf = lgbm
        logger.info("Using LightGBM classifier")
        return Pipeline([("clf", clf)])
    except ImportError:
        logger.info("lightgbm not installed — falling back to HistGradientBoosting")
        return make_hgb_pipeline(calibrate=calibrate)


def make_best_boosting_pipeline(calibrate: bool = True) -> Pipeline:
    """Return the best available boosting pipeline (LightGBM > HistGBM)."""
    return _try_lightgbm(calibrate=calibrate)
