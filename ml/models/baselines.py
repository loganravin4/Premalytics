"""
Baseline models for EPL match outcome prediction.

  1. NaiveBaseline:       Outputs constant class priors from training data.
  2. LogisticBaseline:    Multinomial logistic regression with imputation + scaling.

Both implement the same interface as sklearn estimators so they can be
dropped into the same evaluation loop.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from ml.config import TARGET_CLASSES, RANDOM_SEED

logger = logging.getLogger(__name__)


class NaiveBaseline(BaseEstimator, ClassifierMixin):
    """
    Predicts the training-set class distribution for every test sample.

    This is the floor every other model must beat.
    """

    def __init__(self):
        self.class_priors_ = None
        self.classes_ = None

    def fit(self, X, y):
        y = np.asarray(y)
        self.classes_, counts = np.unique(y, return_counts=True)
        self.class_priors_ = counts / counts.sum()
        logger.info(
            f"NaiveBaseline priors: "
            + ", ".join(f"{c}={p:.3f}" for c, p in zip(self.classes_, self.class_priors_))
        )
        return self

    def predict(self, X):
        # Always predict the most frequent class
        majority = self.classes_[np.argmax(self.class_priors_)]
        return np.full(len(X), majority)

    def predict_proba(self, X):
        n = len(X)
        proba = np.tile(self.class_priors_, (n, 1))
        return proba


def make_logistic_pipeline(C: float = 1.0, max_iter: int = 2000) -> Pipeline:
    """
    Multinomial logistic regression with NaN imputation and feature scaling.

    Uses median imputation for missing values (common for early-season rolling
    features and NULL xG). StandardScaler ensures convergence.
    """
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
        ("clf",     LogisticRegression(
            solver="lbfgs",
            C=C,
            max_iter=max_iter,
            random_state=RANDOM_SEED,
            class_weight="balanced",
        )),
    ])
