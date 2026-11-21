"""Export the grid_xg model's precomputed xG grids (distance/angle and pitch) for the frontend xG lab.

Usage: python -m ml.pipeline.export_xg_grid [--run-id RUN_ID]
"""

import argparse
import json
import logging
import math
from datetime import date

import joblib
import numpy as np
import pandas as pd

from ml.config import EXPORTS_DIR, LOG_FORMAT
from ml.models.shot_xg import (
    BODY_PART_CATEGORIES, FEATURE_SETS, SITUATION_CATEGORIES, add_derived_features, p_goal,
)
from ml.pipeline.evaluate_shots import resolve_run_dir
from ml.pipeline.train_shots import load_shots, split_shots

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
YARDS_TO_M = 0.9144
GOAL_X, GOAL_Y = 120.0, 40.0
DISTANCES_M = list(range(1, 41))
ANGLES_DEG = list(range(0, 90, 5))
# 2-yard cell centers over the attacking half, in StatsBomb yards.
PITCH_X = list(range(61, 120, 2))
PITCH_Y = list(range(1, 80, 2))


def on_pitch(distance_m: float, angle_deg: float) -> bool:
    d_yd = distance_m / YARDS_TO_M
    dx = d_yd * math.cos(math.radians(angle_deg))
    dy = d_yd * math.sin(math.radians(angle_deg))
    return dy <= GOAL_Y and dx <= GOAL_X


def pitch_to_polar(x: float, y: float) -> tuple[float, float]:
    dx, dy = GOAL_X - x, GOAL_Y - y
    dist = math.hypot(dx, dy) * YARDS_TO_M
    ang = math.degrees(math.atan2(abs(dy), dx)) if dx != 0 else 90.0
    return dist, ang


def _score(model, feats, rows: list[dict]) -> np.ndarray:
    X = add_derived_features(pd.DataFrame(rows).assign(is_womens=0))
    return p_goal(model, X[feats])


def distance_angle_grid(model, feats) -> dict:
    values: dict = {}
    for bp in BODY_PART_CATEGORIES:
        values[bp] = {}
        for sit in SITUATION_CATEGORIES:
            rows = [{"distance_m": float(d), "angle_deg": float(a), "body_part": bp, "situation": sit}
                    for d in DISTANCES_M for a in ANGLES_DEG]
            p = _score(model, feats, rows).reshape(len(DISTANCES_M), len(ANGLES_DEG))
            values[bp][sit] = [
                [round(float(p[i, j]), 4) if on_pitch(d, a) else None for j, a in enumerate(ANGLES_DEG)]
                for i, d in enumerate(DISTANCES_M)
            ]
    return values


def training_support(train: pd.DataFrame) -> list[list[int]]:
    """Training shots per (distance, angle) cell, so the UI can fade unsupported cells."""
    d_idx = np.clip(np.round(train["distance_m"]).astype(int) - 1, 0, len(DISTANCES_M) - 1)
    a_idx = np.clip(np.round(train["angle_deg"] / 5).astype(int), 0, len(ANGLES_DEG) - 1)
    counts = np.zeros((len(DISTANCES_M), len(ANGLES_DEG)), dtype=int)
    np.add.at(counts, (d_idx.to_numpy(), a_idx.to_numpy()), 1)
    return counts.tolist()


def pitch_grid(model, feats) -> dict:
    cells = [(x, y, *pitch_to_polar(x, y)) for x in PITCH_X for y in PITCH_Y]
    values: dict = {}
    for bp in BODY_PART_CATEGORIES:
        values[bp] = {}
        for sit in SITUATION_CATEGORIES:
            rows = [{"distance_m": d, "angle_deg": a, "body_part": bp, "situation": sit}
                    for _, _, d, a in cells]
            p = _score(model, feats, rows).reshape(len(PITCH_X), len(PITCH_Y))
            values[bp][sit] = [[round(float(v), 4) for v in row] for row in p]
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Export xg_grid.json for the frontend xG lab")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    run_dir = resolve_run_dir(args.run_id)
    model = joblib.load(run_dir / "grid_xg.joblib")
    feats = FEATURE_SETS["grid_xg"]
    train, _ = split_shots(load_shots())

    metrics_path = run_dir / "shot_xg_metrics.json"
    grid_metrics = None
    production = None
    if metrics_path.exists():
        m = json.loads(metrics_path.read_text())
        grid_metrics = m["models"]["grid_xg"]["headline"]
        production = {"model": m["production_model"],
                      "headline": m["models"][m["production_model"]]["headline"]}

    grid = {
        "schema_version": SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "run_id": run_dir.name,
        "model": "grid_xg",
        "label": "Model estimate, not official xG",
        "description": ("Probability a non-penalty shot is scored, from a logistic model on distance, "
                        "angle, body part and situation, trained on international tournament shots "
                        "(StatsBomb open data). Men's matches. Ignores defender and keeper positions."),
        "inputs": {"body_part": BODY_PART_CATEGORIES, "situation": SITUATION_CATEGORIES},
        "distance_angle": {
            "distance_m": DISTANCES_M,
            "angle_deg": ANGLES_DEG,
            "index_order": "values[body_part][situation][distance_index][angle_index]",
            "values": distance_angle_grid(model, feats),
            "n_train_shots": training_support(train),
        },
        "pitch": {
            "coordinate_system": "StatsBomb yards: 120 x 80 pitch, attacking toward x=120, goal center (120, 40)",
            "cell_size_yd": 2,
            "x": PITCH_X,
            "y": PITCH_Y,
            "index_order": "values[body_part][situation][x_index][y_index]",
            "values": pitch_grid(model, feats),
        },
        "metrics": {"grid_xg_eval": grid_metrics, "production_model_eval": production},
    }

    payload = json.dumps(grid, separators=(",", ":"))
    (run_dir / "xg_grid.json").write_text(payload)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORTS_DIR / "xg_grid.json").write_text(payload)
    logger.info("Wrote xg_grid.json (%.0f KB) to %s and %s", len(payload) / 1024, run_dir, EXPORTS_DIR)


if __name__ == "__main__":
    main()
