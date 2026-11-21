"""
tune_draw_calibration.py — grid search for draw-probability calibration.

The gradient boosting match-outcome model systematically underweights draw
probability when one team is a heavy favorite (a known issue with ELO-based
features). This script grid-searches the threshold/alpha params of
`_apply_draw_calibration` (ml/pipeline/predict.py) over the WC 2026 holdout
to find the combination that best corrects for it.

Input:
    data-pipeline/data/evaluation/wc2026/20260722_004013/predictions_scored.csv
    (raw p_home_win / p_draw / p_away_win + actual_outcome, one row per match)

Usage:
    python -m ml.pipeline.tune_draw_calibration
"""

import logging
import math
from pathlib import Path

import pandas as pd

from ml.config import LOG_FORMAT
from ml.pipeline.predict import _apply_draw_calibration

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCORED_CSV = (
    PROJECT_ROOT / "data-pipeline" / "data" / "evaluation" / "wc2026"
    / "20260722_004013" / "predictions_scored.csv"
)

THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75]
ALPHAS = [0.30, 0.40, 0.50, 0.60, 0.70]

OUTCOME_COL = {"home": "p_home_win", "draw": "p_draw", "away": "p_away_win"}


def _calibrated_metrics(df: pd.DataFrame, threshold: float, alpha: float) -> dict:
    """Apply calibration to every row and score accuracy + log loss."""
    correct = 0
    eps = 1e-15
    total_ll = 0.0

    for r in df.itertuples():
        p_home, p_draw, p_away = _apply_draw_calibration(
            float(r.p_home_win), float(r.p_draw), float(r.p_away_win),
            threshold, alpha,
        )
        trip = {"home": p_home, "draw": p_draw, "away": p_away}
        pred_outcome = max(trip, key=trip.get)
        if pred_outcome == r.actual_outcome:
            correct += 1
        p_actual = trip[r.actual_outcome]
        total_ll += -math.log(max(p_actual, eps))

    n = len(df)
    return {
        "threshold": threshold,
        "alpha": alpha,
        "accuracy": correct / n,
        "log_loss": total_ll / n,
        "correct": correct,
        "total": n,
    }


def run_grid_search(df: pd.DataFrame) -> tuple[list[dict], dict]:
    """Return (all grid results, best result) sorted by log loss then accuracy."""
    results = [
        _calibrated_metrics(df, threshold, alpha)
        for threshold in THRESHOLDS
        for alpha in ALPHAS
    ]
    best = min(results, key=lambda r: (r["log_loss"], -r["accuracy"]))
    return results, best


def print_grid(results: list[dict], best: dict) -> None:
    header = f"{'threshold':>9}  {'alpha':>5}  {'accuracy':>8}  {'log_loss':>8}"
    print(header)
    print("-" * len(header))
    for r in results:
        marker = "  <- best" if r is best else ""
        print(f"{r['threshold']:>9.2f}  {r['alpha']:>5.2f}  "
              f"{r['accuracy']:>8.4f}  {r['log_loss']:>8.4f}{marker}")


def main() -> None:
    if not SCORED_CSV.exists():
        raise FileNotFoundError(f"Scored predictions not found: {SCORED_CSV}")
    df = pd.read_csv(SCORED_CSV)

    baseline = _calibrated_metrics(df, threshold=1.01, alpha=0.0)  # no-op calibration
    logger.info("Baseline (no calibration): accuracy=%.4f log_loss=%.4f",
                baseline["accuracy"], baseline["log_loss"])

    results, best = run_grid_search(df)
    print_grid(results, best)
    logger.info(
        "Best combination: threshold=%.2f alpha=%.2f -> accuracy=%.4f log_loss=%.4f",
        best["threshold"], best["alpha"], best["accuracy"], best["log_loss"],
    )


if __name__ == "__main__":
    main()
