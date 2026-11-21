"""Evaluate the latest training run's models on the WC 2022 eval split and write metrics.json.

Usage: python -m ml.pipeline.evaluate [--run-id RUN_ID]
"""

import argparse
import json
import logging
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss

from ml.config import ARTIFACTS_DIR, TARGET_ENCODE, LOG_FORMAT
from ml.pipeline.train import (
    load_wc_features, split_train_eval, build_xy, select_feature_columns,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Sorted to match model.classes_, i.e. the predict_proba column order.
LABELS = sorted(TARGET_ENCODE.values())

MODEL_NAMES = ["logistic_regression", "gradient_boosting"]

# Below this many eval rows, per-competition accuracy and log loss are too noisy to report.
MIN_COMP_EVAL_ROWS = 20

# Not a model feature, so it is read back off eval_df; the pivot gives it a home_ prefix.
COMPETITION_COL = "home_competition_id"


def _resolve_run_dir(run_id: str | None) -> Path:
    if run_id:
        d = ARTIFACTS_DIR / run_id
        if not d.exists():
            raise FileNotFoundError(f"Run directory not found: {d}")
        return d
    latest = ARTIFACTS_DIR / "latest_run.txt"
    if not latest.exists():
        raise FileNotFoundError(
            "No latest_run.txt found — run python -m ml.pipeline.train first."
        )
    return ARTIFACTS_DIR / latest.read_text().strip()


def _metrics_by_competition(eval_df, y_eval, predictions: dict) -> dict:
    if COMPETITION_COL not in eval_df.columns:
        logger.warning(
            "%s absent from eval features — skipping by-competition breakdown.",
            COMPETITION_COL,
        )
        return {}

    # Cached predictions are positional (eval_df row order), so mask with positional arrays.
    comp = eval_df[COMPETITION_COL].to_numpy()
    y_true = np.asarray(y_eval)

    out: dict = {}
    comp_ids, counts = np.unique(comp[pd.notna(comp)], return_counts=True)
    for comp_id in comp_ids[np.argsort(-counts)]:
        mask = comp == comp_id
        n_rows = int(mask.sum())
        if n_rows < MIN_COMP_EVAL_ROWS:
            continue

        entry = {"n_rows": n_rows}
        for name, (y_pred, y_proba) in predictions.items():
            acc = accuracy_score(y_true[mask], np.asarray(y_pred)[mask])
            ll  = log_loss(y_true[mask], np.asarray(y_proba)[mask], labels=LABELS)
            entry[name] = {"accuracy": float(acc), "log_loss": float(ll)}
        out[str(comp_id)] = entry
        logger.info(
            "  [%s] n=%d  gb_acc=%.4f  lr_acc=%.4f",
            comp_id, n_rows,
            entry.get("gradient_boosting", {}).get("accuracy", float("nan")),
            entry.get("logistic_regression", {}).get("accuracy", float("nan")),
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate WC models on the WC 2022 eval split")
    parser.add_argument("--run-id", default=None, help="Run ID to evaluate (default: latest)")
    args = parser.parse_args()

    run_dir = _resolve_run_dir(args.run_id)
    logger.info(f"Evaluating run: {run_dir.name}")

    features = load_wc_features()
    # Adds the confederation one-hot columns in place so the saved feature_cols.json indexes cleanly.
    select_feature_columns(features)
    feature_cols = json.loads((run_dir / "feature_cols.json").read_text())
    train_df, eval_df = split_train_eval(features)
    X_eval, y_eval, _ = build_xy(eval_df, feature_cols)

    model_metrics: dict = {}
    predictions: dict = {}
    for name in MODEL_NAMES:
        model = joblib.load(run_dir / f"{name}.joblib")
        y_pred  = model.predict(X_eval)
        y_proba = model.predict_proba(X_eval)
        predictions[name] = (y_pred, y_proba)
        acc = accuracy_score(y_eval, y_pred)
        ll  = log_loss(y_eval, y_proba, labels=LABELS)
        model_metrics[name] = {"accuracy": float(acc), "log_loss": float(ll)}
        logger.info(f"{name}: accuracy={acc:.4f}  log_loss={ll:.4f}")

    by_competition = _metrics_by_competition(eval_df, y_eval, predictions)

    metrics = {
        "run_date":   date.today().isoformat(),
        "n_train":    int(len(train_df)),
        "n_eval":     int(len(eval_df)),
        "n_features": len(feature_cols),
        "models":     model_metrics,
        "eval_by_competition": by_competition,
    }

    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
