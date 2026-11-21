"""
Single-shot xG inference CLI (XG-04).

Two models can answer, both from the latest shot run:

  --model grid (default)  grid_xg: distance, angle, body part, situation.
                          Same model as xg_grid.json, so the API and the
                          frontend xG lab agree for the same inputs.
  --model full            the production model (see production_model.json;
                          logistic_full today) with the full at-release
                          feature set. Freeze-frame inputs you leave out are
                          imputed (training medians), so pass them when known.

Default stdout is exactly {"p_goal", "model", "distance_m", "angle_deg"}:
the Spring backend deserializes it with a strict ObjectMapper, so extra keys
would break it. --verbose adds the inputs used and the timing.

Latency: model load + one prediction is ~5-15 ms in-process (measured with
--verbose; "latency_ms"). Process start and the sklearn import dominate wall
time for a CLI call; the BE-05 inference service removes that by loading once.

Usage:
    python -m ml.pipeline.predict_shot --distance 14.2 --angle 22.5
    python -m ml.pipeline.predict_shot --distance 8 --angle 10 --body-part head --situation set_piece
    python -m ml.pipeline.predict_shot --distance 11 --angle 5 --model full \\
        --n-def-in-cone 1 --gk-dist-to-goal 2.5 --verbose
"""

import argparse
import json
import math
import time
from pathlib import Path

import joblib
import pandas as pd

from ml.config import ARTIFACTS_DIR
from ml.models.shot_xg import (
    ASSIST_CATEGORIES, BODY_PART_CATEGORIES, FEATURE_SETS, SITUATION_CATEGORIES,
    TECHNIQUE_CATEGORIES, add_derived_features, p_goal,
)


def _resolve_run_dir(run_id: str | None) -> Path:
    if run_id:
        return ARTIFACTS_DIR / run_id
    latest = ARTIFACTS_DIR / "latest_shot_run.txt"
    if not latest.exists():
        raise FileNotFoundError("No shot model found. Train first: python -m ml.pipeline.train_shots")
    return ARTIFACTS_DIR / latest.read_text().strip()


def build_row(args) -> dict:
    nan = float("nan")
    ff_given = any(v is not None for v in (args.n_def_in_cone, args.nearest_def,
                                            args.gk_dist_to_goal, args.gk_dist_to_shooter,
                                            args.gk_angle_offset))
    return {
        "distance_m": args.distance,
        "angle_deg": args.angle,
        "body_part": args.body_part,
        "situation": args.situation,
        "technique": args.technique,
        "assist_type": args.assist_type,
        "under_pressure": args.under_pressure,
        "first_time": args.first_time,
        "ff_available": ff_given,
        "is_womens": int(args.womens),
        "n_def_in_cone": nan if args.n_def_in_cone is None else args.n_def_in_cone,
        "nearest_def_m": nan if args.nearest_def is None else args.nearest_def,
        "gk_dist_to_goal_m": nan if args.gk_dist_to_goal is None else args.gk_dist_to_goal,
        "gk_dist_to_shooter_m": nan if args.gk_dist_to_shooter is None else args.gk_dist_to_shooter,
        "gk_angle_offset_deg": nan if args.gk_angle_offset is None else args.gk_angle_offset,
    }


def predict(row: dict, run_dir: Path, which: str = "grid") -> tuple[float, str]:
    """Return (p_goal, model_name) for one shot dict."""
    if which == "grid":
        name = "grid_xg"
    else:
        name = json.loads((run_dir / "production_model.json").read_text())["production_model"]
    model = joblib.load(run_dir / f"{name}.joblib")
    X = add_derived_features(pd.DataFrame([row]))[FEATURE_SETS[name]]
    return float(p_goal(model, X)[0]), name


def main() -> None:
    parser = argparse.ArgumentParser(description="Score a single shot's xG")
    parser.add_argument("--distance", type=float, required=True, help="distance_m from goal center")
    parser.add_argument("--angle", type=float, required=True, help="angle_deg (0=central, 90=byline)")
    parser.add_argument("--body-part", default="right_foot", choices=BODY_PART_CATEGORIES)
    parser.add_argument("--situation", default="open_play", choices=SITUATION_CATEGORIES)
    parser.add_argument("--model", default="grid", choices=["grid", "full"])
    parser.add_argument("--technique", default="normal", choices=TECHNIQUE_CATEGORIES)
    parser.add_argument("--assist-type", default="pass", choices=ASSIST_CATEGORIES)
    parser.add_argument("--under-pressure", action="store_true")
    parser.add_argument("--first-time", action="store_true")
    parser.add_argument("--womens", action="store_true", help="women's match (sets is_womens=1)")
    parser.add_argument("--n-def-in-cone", type=int, default=None)
    parser.add_argument("--nearest-def", type=float, default=None, help="meters")
    parser.add_argument("--gk-dist-to-goal", type=float, default=None, help="meters")
    parser.add_argument("--gk-dist-to-shooter", type=float, default=None, help="meters")
    parser.add_argument("--gk-angle-offset", type=float, default=None, help="degrees")
    parser.add_argument("--run-id", default=None, help="Run dir name (default: latest)")
    parser.add_argument("--verbose", action="store_true", help="add inputs and latency to the output")
    args = parser.parse_args()

    if not (0 <= args.distance <= 120) or not (0 <= args.angle <= 90):
        parser.error("distance must be 0-120 m and angle 0-90 degrees")

    t0 = time.perf_counter()
    row = build_row(args)
    p, name = predict(row, _resolve_run_dir(args.run_id), args.model)
    latency_ms = (time.perf_counter() - t0) * 1000

    out = {
        "p_goal": round(p, 4),
        "model": "shot_xg_grid" if name == "grid_xg" else f"shot_xg_{name}",
        "distance_m": args.distance,
        "angle_deg": args.angle,
    }
    if args.verbose:
        out["inputs"] = {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        out["latency_ms"] = round(latency_ms, 2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
