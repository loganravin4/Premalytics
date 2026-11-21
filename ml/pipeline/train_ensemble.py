"""
Attach the walk-forward-selected ensemble to a trained match run (ML-04/05).

Fits a Dixon-Coles model on the same training window as the GBM run (matches
before TRAIN_CUTOFF_DATE) and writes `ensemble.json` + `dixon_coles.joblib`
into that run directory. predict.py then serves

    p = calibrate( w * p_gbm + (1 - w) * p_dixon_coles )

instead of the GBM + threshold draw rule. The blend weight and calibration
parameters are NOT fit here: they are read from a backtest's last reported
fold before the cutoff (`fifa_world_cup_2026` post_params), i.e. fit only on
out-of-sample tournament predictions that finished before WC 2026.

Usage:
    python -m ml.pipeline.train_ensemble [--run-id RUN] [--backtest-dir DIR]
                                         [--variant blend_drawbias]
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from ml.config import ARTIFACTS_DIR, LOG_FORMAT, TRAIN_CUTOFF_DATE
from ml.models.dixon_coles import DixonColes
from ml.pipeline import backtest as B
from ml.pipeline.predict import _resolve_run_dir

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

VARIANTS = ("blend", "blend_temp", "blend_drawbias")
PARAMS_FOLD = "fifa_world_cup_2026"


def fit_dixon_coles(features: pd.DataFrame, cutoff: str) -> DixonColes:
    start = pd.Timestamp(cutoff)
    f = features.copy()
    f["match_date"] = pd.to_datetime(f["match_date"])
    tr = f[(f["match_date"] < start)
           & (f["match_date"] >= start - pd.DateOffset(years=B.DC_WINDOW_YEARS))]
    return DixonColes(xi=B.DC_XI, l2=B.DC_L2).fit(
        tr["home_team"], tr["away_team"], tr["goals_for"], tr["goals_against"],
        tr["home_is_neutral_venue"].fillna(0).astype(bool), tr["match_date"],
        ref_date=start, weights=B._weights(tr))


def main() -> None:
    ap = argparse.ArgumentParser(description="Attach GBM + Dixon-Coles ensemble to a run")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--backtest-dir", default=None)
    ap.add_argument("--variant", default="blend_drawbias", choices=VARIANTS)
    args = ap.parse_args()

    run_dir = _resolve_run_dir(args.run_id)
    bdir = Path(args.backtest_dir) if args.backtest_dir else sorted(
        p for p in ARTIFACTS_DIR.glob("backtest_*") if (p / "metrics.json").exists())[-1]
    meta = json.loads((bdir / "metrics.json").read_text())
    params = meta["per_tournament"][PARAMS_FOLD]["post_params"][args.variant]
    logger.info("Ensemble params from %s / %s: %s", bdir.name, PARAMS_FOLD, params)

    features = joblib.load(run_dir / "features.joblib")
    dc = fit_dixon_coles(features, TRAIN_CUTOFF_DATE)
    joblib.dump(dc, run_dir / "dixon_coles.joblib")
    ens = {
        "variant": args.variant,
        "blend_weight_gbm": params["weight_first"],
        "temperature": params.get("temperature", 1.0),
        "draw_bias": params.get("draw_bias", 0.0),
        "dixon_coles": {"xi": B.DC_XI, "l2": B.DC_L2, "window_years": B.DC_WINDOW_YEARS,
                        "train_cutoff": TRAIN_CUTOFF_DATE, "rho": round(float(dc.rho_), 4),
                        "home_adv": round(float(dc.home_adv_), 4), "n_train": dc.n_train_},
        "params_source": {"backtest": bdir.name, "fold": PARAMS_FOLD,
                          "prior_folds": meta["per_tournament"][PARAMS_FOLD]["post_params"]
                          ["prior_folds"]},
    }
    (run_dir / "ensemble.json").write_text(json.dumps(ens, indent=2))
    logger.info("Wrote %s", run_dir / "ensemble.json")
    print(json.dumps(ens, indent=2))


if __name__ == "__main__":
    main()
