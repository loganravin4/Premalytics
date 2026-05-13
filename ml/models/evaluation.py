"""
Model evaluation utilities: metrics, calibration, feature importance.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    brier_score_loss,
    classification_report,
    precision_recall_fscore_support,
)
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance

from ml.config import TARGET_CLASSES

logger = logging.getLogger(__name__)


def compute_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    label_order: list[str] = TARGET_CLASSES,
) -> dict:
    """
    Compute all evaluation metrics for a set of predictions.

    Args:
        y_true:      True class labels (e.g., ["H", "D", "A", ...])
        y_pred:      Predicted class labels
        y_proba:     Predicted probabilities shape (n, n_classes)
        label_order: Class ordering for probability columns

    Returns:
        dict with: accuracy, log_loss, brier_H, brier_D, brier_A,
                   classification_report_str
    """
    acc  = accuracy_score(y_true, y_pred)
    # Pass labels explicitly in alphabetical order to match sklearn's default probability ordering
    ll   = log_loss(y_true, y_proba, labels=sorted(label_order))

    # Brier score per class (one-vs-rest)
    brier = {}
    for i, cls in enumerate(label_order):
        y_bin = (np.asarray(y_true) == cls).astype(int)
        brier[f"brier_{cls}"] = brier_score_loss(y_bin, y_proba[:, i])

    report = classification_report(y_true, y_pred, labels=label_order, zero_division=0)

    return {
        "accuracy":   acc,
        "log_loss":   ll,
        **brier,
        "report":     report,
    }


def print_metrics(metrics: dict, model_name: str = "") -> None:
    header = f"=== {model_name} ===" if model_name else "=== Metrics ==="
    print(f"\n{header}")
    print(f"  Accuracy : {metrics['accuracy']:.4f}")
    print(f"  Log loss : {metrics['log_loss']:.4f}")
    for k, v in metrics.items():
        if k.startswith("brier_"):
            print(f"  {k}  : {v:.4f}")
    print("\nClassification report:")
    print(metrics["report"])


def calibration_summary(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    label_order: list[str] = TARGET_CLASSES,
    n_bins: int = 10,
) -> dict[str, tuple]:
    """
    Compute calibration curves for each class.

    Returns dict: {class_label: (fraction_of_positives, mean_predicted_value)}
    """
    results = {}
    for i, cls in enumerate(label_order):
        y_bin = (np.asarray(y_true) == cls).astype(int)
        frac, mean_pred = calibration_curve(y_bin, y_proba[:, i], n_bins=n_bins)
        results[cls] = (frac, mean_pred)
    return results


def per_class_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    label_order: list[str] = TARGET_CLASSES,
    n_bins: int = 10,
) -> dict:
    """
    Structured per-class diagnostics: precision, recall, F1, support,
    and calibration MAE (mean absolute deviation from perfect calibration).

    Returns dict: {class: {precision, recall, f1, support, calibration_mae}}
    """
    prec, rec, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=label_order, zero_division=0
    )
    result = {}
    for i, cls in enumerate(label_order):
        y_bin = (np.asarray(y_true) == cls).astype(int)
        try:
            frac, mean_pred = calibration_curve(y_bin, y_proba[:, i], n_bins=n_bins)
            cal_mae = float(np.mean(np.abs(frac - mean_pred)))
        except ValueError:
            cal_mae = None
        result[cls] = {
            "precision":       float(prec[i]),
            "recall":          float(rec[i]),
            "f1":              float(f1[i]),
            "support":         int(support[i]),
            "calibration_mae": cal_mae,
        }
    return result


def calibration_curves_dict(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    label_order: list[str] = TARGET_CLASSES,
    n_bins: int = 10,
) -> dict:
    """
    Machine-readable calibration curves per class (for downstream plotting).

    Returns {class: {fraction_of_positives: [...], mean_predicted_value: [...]}}
    """
    result = {}
    for i, cls in enumerate(label_order):
        y_bin = (np.asarray(y_true) == cls).astype(int)
        try:
            frac, mean_pred = calibration_curve(y_bin, y_proba[:, i], n_bins=n_bins)
            result[cls] = {
                "fraction_of_positives": frac.tolist(),
                "mean_predicted_value":  mean_pred.tolist(),
            }
        except ValueError:
            result[cls] = {"fraction_of_positives": [], "mean_predicted_value": []}
    return result


def error_slices_by_col(
    error_df: pd.DataFrame,
    slice_col: str,
    n_bins: int = 3,
    bin_labels: list[str] | None = None,
) -> dict:
    """
    Slice error_df by quantile bins of a continuous feature column.

    error_df must contain a boolean 'correct' column.
    Returns {bin_label: {accuracy, n, mean_value}} or {} if column is absent/sparse.
    """
    if slice_col not in error_df.columns:
        return {}
    valid = error_df[error_df[slice_col].notna()].copy()
    if len(valid) < n_bins * 5:
        return {}

    labels = bin_labels if bin_labels and len(bin_labels) == n_bins \
        else (["low", "mid", "high"] if n_bins == 3 else [str(i) for i in range(n_bins)])

    try:
        valid["_bin"] = pd.qcut(valid[slice_col], q=n_bins, labels=labels, duplicates="drop")
    except ValueError:
        return {}

    result = {}
    for label, grp in valid.groupby("_bin", observed=True):
        result[str(label)] = {
            "accuracy":   float(grp["correct"].mean()),
            "n":          int(len(grp)),
            "mean_value": float(grp[slice_col].mean()),
        }
    return result


def permutation_importance_df(
    model_pipeline: Any,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str],
    n_repeats: int = 10,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Compute permutation importance on a held-out set.

    Works with any fitted estimator regardless of internal structure (CalibratedClassifierCV,
    HistGBM, LightGBM, etc.). More informative than training-time importance because it
    measures actual predictive contribution on unseen data.

    Returns a DataFrame sorted by mean_importance descending, with columns:
        feature, mean_importance, std_importance
    """
    result = permutation_importance(
        model_pipeline, X, y,
        n_repeats=n_repeats,
        random_state=random_state,
        scoring="accuracy",
    )
    return (
        pd.DataFrame({
            "feature":          feature_names,
            "mean_importance":  result.importances_mean,
            "std_importance":   result.importances_std,
        })
        .sort_values("mean_importance", ascending=False)
        .reset_index(drop=True)
    )


def feature_importance_df(model_pipeline: Any, feature_names: list[str]) -> pd.DataFrame:
    """
    Extract feature importance from a fitted pipeline.

    For CalibratedClassifierCV, averages importances across all calibration
    folds (not just fold 0) for a more stable estimate.
    Handles HistGBM, LightGBM, and LogisticRegression (uses coef_ magnitude).
    Returns a DataFrame sorted by importance descending.
    """
    clf = model_pipeline
    # Unwrap pipeline steps
    if hasattr(clf, "named_steps"):
        clf = clf.named_steps.get("clf", clf)

    # Unwrap CalibratedClassifierCV — average importances across all folds
    if hasattr(clf, "calibrated_classifiers_"):
        imps = []
        for cc in clf.calibrated_classifiers_:
            est = cc.estimator
            if hasattr(est, "feature_importances_"):
                imps.append(est.feature_importances_)
            elif hasattr(est, "coef_"):
                imps.append(np.abs(est.coef_).mean(axis=0))
        if not imps:
            logger.warning("Calibrated estimators expose no importances")
            return pd.DataFrame()
        imp = np.mean(imps, axis=0)
    elif hasattr(clf, "feature_importances_"):
        imp = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        imp = np.abs(clf.coef_).mean(axis=0)
    else:
        logger.warning("Model does not expose feature importances")
        return pd.DataFrame()

    if len(imp) != len(feature_names):
        logger.warning(
            f"Importance length {len(imp)} != feature names {len(feature_names)}"
        )
        return pd.DataFrame()

    return (
        pd.DataFrame({"feature": feature_names, "importance": imp})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )
