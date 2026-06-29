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
import numpy as np
import pandas as pd
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

# Competition slugs span friendlies, qualifiers and many tournaments after the
# martj42 expansion. Only report a competition if it has at least this many eval
# rows — below this, accuracy/log_loss are too noisy to be meaningful.
MIN_COMP_EVAL_ROWS = 20

# competition_id is a metadata column; the pivot prefixes it 'home_' (home and
# away rows of a match share the same competition). It is excluded from X by
# select_feature_columns, so we read it back off the eval features for strat:.
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
    """
    Accuracy / log loss per competition_id, for competitions with >= MIN_COMP_EVAL_ROWS
    rows in the eval split.

    The cached (y_pred, y_proba) arrays are positional (X_eval row order, which
    is eval_df's order), so we stratify with a positional competition array read
    off eval_df[COMPETITION_COL]. y_eval is converted to a positional array too.
    """
    if COMPETITION_COL not in eval_df.columns:
        logger.warning(
            "%s absent from eval features — skipping by-competition breakdown.",
            COMPETITION_COL,
        )
        return {}

    comp = eval_df[COMPETITION_COL].to_numpy()
    y_true = np.asarray(y_eval)

    out: dict = {}
    # Sort by descending eval-row count so the most-represented comps lead.
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

    # Same split logic as train.py.
    features = load_wc_features()
    feature_cols = json.loads((run_dir / "feature_cols.json").read_text())
    train_df, eval_df = split_train_eval(features)
    X_eval, y_eval, _ = build_xy(eval_df, feature_cols)

    model_metrics: dict = {}
    predictions: dict = {}   # name -> (y_pred, y_proba) cached for stratification
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
