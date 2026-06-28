"""
WC-06 evaluation pipeline.

Loads the models from the latest training run, rebuilds the identical
chronological eval split (WC 2022), and writes accuracy + log loss per
model to metrics.json in the run directory.

Usage:
    python -m ml.pipeline.evaluate [--run-id RUN_ID]
"""

import argparse
import json
import logging
from datetime import date
from pathlib import Path

import joblib
from sklearn.metrics import accuracy_score, log_loss

from ml.config import ARTIFACTS_DIR, TARGET_ENCODE, LOG_FORMAT
from ml.pipeline.train import (
    load_wc_features, split_train_eval, build_xy,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Encoded class order (sorted) — matches model.classes_ and predict_proba columns.
LABELS = sorted(TARGET_ENCODE.values())  # [0, 1, 2]

MODEL_NAMES = ["logistic_regression", "gradient_boosting"]


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate WC models on the WC 2022 eval split")
    parser.add_argument("--run-id", default=None, help="Run ID to evaluate (default: latest)")
    args = parser.parse_args()

    run_dir = _resolve_run_dir(args.run_id)
    logger.info(f"Evaluating run: {run_dir.name}")

    # Same split logic as train.py.
    features = load_wc_features()
    feature_cols = json.loads((run_dir / "feature_cols.json").read_text())
    train_df, eval_df = split_train_eval(features)
    X_eval, y_eval = build_xy(eval_df, feature_cols)

    model_metrics: dict = {}
    for name in MODEL_NAMES:
        model = joblib.load(run_dir / f"{name}.joblib")
        y_pred  = model.predict(X_eval)
        y_proba = model.predict_proba(X_eval)
        acc = accuracy_score(y_eval, y_pred)
        ll  = log_loss(y_eval, y_proba, labels=LABELS)
        model_metrics[name] = {"accuracy": float(acc), "log_loss": float(ll)}
        logger.info(f"{name}: accuracy={acc:.4f}  log_loss={ll:.4f}")

    metrics = {
        "run_date":   date.today().isoformat(),
        "n_train":    int(len(train_df)),
        "n_eval":     int(len(eval_df)),
        "n_features": len(feature_cols),
        "models":     model_metrics,
    }

    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
