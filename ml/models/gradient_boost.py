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
        # Isotonic over sigmoid: it calibrates multi-class better.
        clf = CalibratedClassifierCV(hgb, cv=3, method="isotonic")
    else:
        clf = hgb

    # No imputer: HistGBM handles NaN natively.
    return Pipeline([("clf", clf)])


def _try_lightgbm(
    n_estimators: int = 300,
    learning_rate: float = 0.05,
    num_leaves: int = 31,
    min_child_samples: int = 20,
    calibrate: bool = True,
) -> Pipeline:
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


# Pre-tuning defaults; Optuna params in ml/artifacts/best_xgb_params.json override them when present.
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
        # A tuned file must never override these.
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
