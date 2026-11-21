"""
Hyperparameter tuning for the XGBoost match-outcome model (PHASE 3).

Optuna search over XGBClassifier params, scored by mean multi-class log loss
across a 5-fold TimeSeriesSplit (temporal order respected — no shuffling, each
fold validates on a strictly later slice than it trains on).

The search runs on the TRAINING window only (matches before TRAIN_CUTOFF_DATE),
using the same feature matrix and per-competition sample weights as
ml.pipeline.train, so the tuned model transfers cleanly.

Outputs:
    ml/artifacts/best_xgb_params.json   (consumed by make_best_boosting_pipeline)

Usage:
    python -m ml.pipeline.tune_match_model [--n-trials 100]
"""

import argparse
import json
import logging

import numpy as np
import optuna
from sklearn.metrics import log_loss
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBClassifier

from ml.config import ARTIFACTS_DIR, RANDOM_SEED, TARGET_ENCODE, LOG_FORMAT
from ml.pipeline.train import (
    load_wc_features, select_feature_columns, split_train_eval, build_xy,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

LABELS = sorted(TARGET_ENCODE.values())   # [0, 1, 2]
N_SPLITS = 5
BEST_PARAMS_PATH = ARTIFACTS_DIR / "best_xgb_params.json"

# Fixed params that are not searched (kept identical to the production model).
FIXED_PARAMS = {
    "eval_metric": "mlogloss",
    "random_state": RANDOM_SEED,
    "n_jobs": -1,
    "verbosity": 0,
}


def _suggest_params(trial: optuna.Trial) -> dict:
    return {
        "n_estimators":     trial.suggest_int("n_estimators", 100, 1000, step=50),
        "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
        "max_depth":        trial.suggest_int("max_depth", 3, 8),
        "subsample":        trial.suggest_float("subsample", 0.5, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "gamma":            trial.suggest_float("gamma", 0.0, 1.0),
        "reg_alpha":        trial.suggest_float("reg_alpha", 1e-8, 1.0, log=True),
        "reg_lambda":       trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
    }


def make_objective(X, y, w):
    X = X.to_numpy() if hasattr(X, "to_numpy") else np.asarray(X)
    y = np.asarray(y)
    w = np.asarray(w)
    tscv = TimeSeriesSplit(n_splits=N_SPLITS)

    def objective(trial: optuna.Trial) -> float:
        params = {**_suggest_params(trial), **FIXED_PARAMS}
        fold_losses = []
        for tr_idx, va_idx in tscv.split(X):
            model = XGBClassifier(**params)
            model.fit(X[tr_idx], y[tr_idx], sample_weight=w[tr_idx])
            proba = model.predict_proba(X[va_idx])
            fold_losses.append(log_loss(y[va_idx], proba, labels=LABELS))
        return float(np.mean(fold_losses))

    return objective


def _progress(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
    logger.info("trial %3d/%d  log_loss=%.5f  best=%.5f",
                trial.number + 1, study.user_attrs.get("n_trials", 0),
                trial.value if trial.value is not None else float("nan"),
                study.best_value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune XGBoost match model with Optuna")
    parser.add_argument("--n-trials", type=int, default=100)
    args = parser.parse_args()

    logger.info("Loading features and building the training window ...")
    features = load_wc_features()
    feature_cols = select_feature_columns(features)
    train_df, _ = split_train_eval(features)
    X, y, w = build_xy(train_df, feature_cols)
    logger.info("Tuning on %d training rows, %d features, %d-fold TimeSeriesSplit",
                len(X), len(feature_cols), N_SPLITS)

    optuna.logging.set_verbosity(optuna.logging.WARNING)   # suppress verbose logs
    sampler = optuna.samplers.TPESampler(seed=RANDOM_SEED)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.set_user_attr("n_trials", args.n_trials)
    study.optimize(make_objective(X, y, w), n_trials=args.n_trials,
                   callbacks=[_progress])

    logger.info("=" * 60)
    logger.info("Best CV log loss: %.5f", study.best_value)
    logger.info("Best params:")
    for k, v in study.best_params.items():
        logger.info("    %-18s %s", k, v)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    BEST_PARAMS_PATH.write_text(json.dumps(study.best_params, indent=2))
    logger.info("Saved best params -> %s", BEST_PARAMS_PATH)
    logger.info("Next: retrain (make_best_boosting_pipeline now loads these).")

    print(json.dumps({
        "best_cv_log_loss": round(study.best_value, 5),
        "best_params": study.best_params,
    }, indent=2))


if __name__ == "__main__":
    main()
