"""
Gradient boosting model for match outcome prediction.

Uses sklearn's HistGradientBoostingClassifier as the primary model because:
  - Native NaN handling (no imputation step needed)
  - Fast training on small datasets (< 10k rows)
  - Competitive accuracy with LightGBM on tabular data this size

If lightgbm is installed, LGBMClassifier is used instead (faster, better
calibrated out-of-the-box). Install with: pip install lightgbm
"""

import json
import logging

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.calibration import CalibratedClassifierCV

from ml.config import RANDOM_SEED, ARTIFACTS_DIR

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


# Sensible XGBoost defaults (pre-tuning). Phase 3 overrides these with the
# Optuna-tuned params persisted at ml/artifacts/best_xgb_params.json.
XGB_DEFAULTS = {
    "eval_metric": "mlogloss",
    "use_label_encoder": False,
    "random_state": RANDOM_SEED,
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 6,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "min_child_weight": 3,
}


def make_best_boosting_pipeline(calibrate: bool = True) -> Pipeline:
    """
    Return the best available boosting pipeline.

    Primary: XGBoost (XGBClassifier). If ml/artifacts/best_xgb_params.json
    exists (written by ml.pipeline.tune_match_model), those tuned params are
    merged over XGB_DEFAULTS. Falls back to HistGradientBoosting when xgboost
    is not installed.
    """
    try:
        from xgboost import XGBClassifier
    except ImportError:
        logger.info("xgboost not installed — falling back to HistGradientBoosting")
        return make_hgb_pipeline(calibrate=calibrate)

    params = dict(XGB_DEFAULTS)
    tuned_path = ARTIFACTS_DIR / "best_xgb_params.json"
    if tuned_path.exists():
        tuned = json.loads(tuned_path.read_text())
        params.update(tuned)
        # Always keep the invariant, reproducibility, and label-encoder flags.
        params.update({
            "eval_metric": "mlogloss",
            "use_label_encoder": False,
            "random_state": RANDOM_SEED,
        })
        logger.info("Using XGBoost classifier (TUNED params from %s)", tuned_path.name)
    else:
        logger.info("Using XGBoost classifier (default params — run "
                    "tune_match_model for tuned params)")

    xgb = XGBClassifier(**params)
    if calibrate:
        clf = CalibratedClassifierCV(xgb, cv=3, method="isotonic")
    else:
        clf = xgb
    return Pipeline([("clf", clf)])
