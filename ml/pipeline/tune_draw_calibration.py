"""
tune_draw_calibration.py — grid search for the draw-probability calibration.

The gradient boosting match-outcome model underweights the draw when one team
is a heavy favorite. `_apply_draw_calibration` (ml/pipeline/predict.py) moves
alpha * (p_favorite - threshold) of the favorite's mass to the draw.

ML-04: the grid now runs on WALK-FORWARD out-of-sample predictions from
`python -m ml.pipeline.backtest` (every major tournament 2010-2025), never on
WC 2026. The old version tuned on the WC 2026 holdout it was then scored on.

Two views are printed:
  * the grid on all pre-2026 folds pooled (what you would ship), and
  * the nested walk-forward score: each tournament scored with the params
    tuned only on tournaments that finished before it started. If nested
    calibration does not beat "no calibration", keep it off.

Usage:
    python -m ml.pipeline.tune_draw_calibration [--backtest-dir DIR] [--model gbm]
"""

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ml.config import ARTIFACTS_DIR, LOG_FORMAT
from ml.models import metrics as M
from ml.models.calibration import ThresholdDrawCal, apply_threshold_draw_cal

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

EXCLUDED_FOLDS = {"fifa_world_cup_2026"}
OUTCOME_IDX = {"home": M.HOME, "draw": M.DRAW, "away": M.AWAY}


def latest_backtest_dir() -> Path:
    runs = sorted(p for p in ARTIFACTS_DIR.glob("backtest_*") if (p / "predictions.csv").exists())
    if not runs:
        raise FileNotFoundError("No backtest found. Run: python -m ml.pipeline.backtest")
    return runs[-1]


def load_oos(backtest_dir: Path, model: str) -> pd.DataFrame:
    df = pd.read_csv(backtest_dir / "predictions.csv")
    df = df[(df["model"] == model) & ~df["fold"].isin(EXCLUDED_FOLDS)].copy()
    df["match_date"] = pd.to_datetime(df["match_date"])
    df["y"] = df["outcome"].map(OUTCOME_IDX)
    return df


def grid(p: np.ndarray, y: np.ndarray) -> list[dict]:
    rows = []
    for t in ThresholdDrawCal.THRESHOLDS:
        for a in ThresholdDrawCal.ALPHAS:
            q = apply_threshold_draw_cal(p, t, a)
            rows.append({"threshold": t, "alpha": a, "log_loss": M.log_loss(q, y),
                         "rps": M.rps(q, y), "accuracy": M.accuracy(q, y),
                         "draw_recall": M.draw_recall(q, y)})
    return rows


def nested(df: pd.DataFrame) -> dict:
    """Score each fold with params tuned on folds that ended before it began."""
    spans = df.groupby("fold")["match_date"].agg(["min", "max"]).sort_values("min")
    ps, ys, ps0 = [], [], []
    for fold, (start, _) in spans.iterrows():
        prior = spans.index[spans["max"] < start]
        if len(prior) == 0 or bool(df.loc[df["fold"] == fold, "warmup"].iloc[0]):
            continue
        tr = df[df["fold"].isin(prior)]
        te = df[df["fold"] == fold]
        cal = ThresholdDrawCal().fit(tr[["p_home", "p_draw", "p_away"]].to_numpy(),
                                     tr["y"].to_numpy())
        p = te[["p_home", "p_draw", "p_away"]].to_numpy()
        ps.append(cal.transform(p))
        ps0.append(p)
        ys.append(te["y"].to_numpy())
    p, p0, y = np.vstack(ps), np.vstack(ps0), np.concatenate(ys)
    return {"n": len(y), "none": M.score(p0, y), "nested": M.score(p, y)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Tune draw calibration on walk-forward folds")
    ap.add_argument("--backtest-dir", default=None)
    ap.add_argument("--model", default="gbm")
    args = ap.parse_args()

    bdir = Path(args.backtest_dir) if args.backtest_dir else latest_backtest_dir()
    df = load_oos(bdir, args.model)
    logger.info("Using %s (%s): %d OOS matches, %d folds (WC 2026 excluded)",
                bdir.name, args.model, len(df), df["fold"].nunique())

    p = df[["p_home", "p_draw", "p_away"]].to_numpy()
    y = df["y"].to_numpy()
    rows = grid(p, y)
    best = min(rows, key=lambda r: (r["log_loss"], r["rps"]))
    print(f"{'threshold':>9}  {'alpha':>5}  {'log_loss':>8}  {'rps':>7}  {'acc':>6}  {'draw_rec':>8}")
    for r in rows:
        mark = "  <- best" if r is best else ""
        print(f"{r['threshold']:>9.2f}  {r['alpha']:>5.2f}  {r['log_loss']:>8.4f}  "
              f"{r['rps']:>7.4f}  {r['accuracy']:>6.3f}  {r['draw_recall']:>8.3f}{mark}")

    nest = nested(df)
    print(f"\nNested walk-forward over {nest['n']} reported matches:")
    for k in ("none", "nested"):
        m = nest[k]
        print(f"  {k:>6}: log_loss={m['log_loss']:.4f}  rps={m['rps']:.4f}  "
              f"acc={m['accuracy']:.3f}  draw_recall={m['draw_recall']:.3f}")
    logger.info("Pooled best: threshold=%.2f alpha=%.2f (1.01 / 0.0 = off)",
                best["threshold"], best["alpha"])


if __name__ == "__main__":
    main()
