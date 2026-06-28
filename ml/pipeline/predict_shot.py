"""
Single-shot xG inference CLI (XG-04).

Loads the production xG model — the **logistic** baseline, which currently
outperforms the GBM on WC 2018/2022 (log loss 0.300 vs 0.329) — from the
latest shot run and scores one shot described on the command line.

The logistic model uses only distance and angle, so this CLI takes just
--distance and --angle. (body_part / situation / under_pressure were
dropped: the production model does not use them. Re-add them if the GBM
becomes the production model — see ml/models/shot_xg.py.)

Usage:
    python -m ml.pipeline.predict_shot --distance 14.2 --angle 22.5

Output (stdout JSON):
    {"p_goal": 0.10, "model": "shot_xg_logistic",
     "distance_m": 14.2, "angle_deg": 22.5}
"""

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from ml.config import ARTIFACTS_DIR
from ml.models.shot_xg import LOGISTIC_FEATURES


def _resolve_run_dir(run_id: str | None) -> Path:
    if run_id:
        return ARTIFACTS_DIR / run_id
    latest = ARTIFACTS_DIR / "latest_shot_run.txt"
    if not latest.exists():
        raise FileNotFoundError(
            "No shot model found. Train first: python -m ml.pipeline.train_shots"
        )
    return ARTIFACTS_DIR / latest.read_text().strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a single shot's xG (logistic model)")
    parser.add_argument("--distance", type=float, required=True, help="distance_m from goal centre")
    parser.add_argument("--angle", type=float, required=True, help="angle_deg (0=central, 90=wide)")
    parser.add_argument("--run-id", default=None, help="Run dir name (default: latest)")
    args = parser.parse_args()

    run_dir = _resolve_run_dir(args.run_id)
    model = joblib.load(run_dir / "logistic_xg.joblib")

    X = pd.DataFrame([{
        "distance_m": args.distance,
        "angle_deg": args.angle,
    }], columns=LOGISTIC_FEATURES)

    goal_idx = list(model.classes_).index(1)
    p_goal = float(model.predict_proba(X)[0][goal_idx])

    print(json.dumps({
        "p_goal": round(p_goal, 4),
        "model": "shot_xg_logistic",
        "distance_m": args.distance,
        "angle_deg": args.angle,
    }, indent=2))


if __name__ == "__main__":
    main()
