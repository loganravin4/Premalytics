"""Backfill WC 2018/2022 match xG, which FBref leaves NULL, by summing the logistic shot model's p_goal over StatsBomb shots.

Usage: python data-pipeline/scripts/06_backfill_xg.py [--force]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = PIPELINE_DIR.parent

SHOT_DIR = PIPELINE_DIR / "data" / "raw" / "shots"
WC_DIR = PIPELINE_DIR / "data" / "raw" / "fifa_world_cup"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
LATEST_SHOT_RUN = ARTIFACTS_DIR / "latest_shot_run.txt"

LOGISTIC_FEATURES = ["distance_m", "angle_deg"]

SEASONS = ["2018", "2022"]
COMPETITION_ID = "fifa_world_cup"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _resolve_shot_model() -> joblib:
    if not LATEST_SHOT_RUN.exists():
        logger.error("Missing %s — train the shot model first "
                     "(python -m ml.pipeline.train_shots).", LATEST_SHOT_RUN)
        sys.exit(1)
    run_dir = ARTIFACTS_DIR / LATEST_SHOT_RUN.read_text().strip()
    model_path = run_dir / "logistic_xg.joblib"
    if not model_path.exists():
        logger.error("Shot model not found: %s", model_path)
        sys.exit(1)
    logger.info("Loaded shot model: %s", model_path)
    return joblib.load(model_path)


def _team_xg_for_season(model, season: str) -> tuple[dict, set]:
    shot_csv = SHOT_DIR / f"wc_shots_{season}.csv"
    if not shot_csv.exists():
        logger.error("Shot data not found: %s", shot_csv)
        sys.exit(1)

    shots = pd.read_csv(shot_csv)
    # A penalty's ~0.75 xG would inflate match xG for teams that earn them
    shots = shots[shots["is_penalty"] != True]
    # is_penalty may have round-tripped through the CSV as the string "True"
    shots = shots[shots["is_penalty"].astype(str).str.lower() != "true"]

    goal_idx = list(model.classes_).index(1)
    shots["p_goal"] = model.predict_proba(shots[LOGISTIC_FEATURES])[:, goal_idx]

    team_xg = shots.groupby(["match_id", "team_id"])["p_goal"].sum().to_dict()
    match_ids = set(shots["match_id"].unique())
    logger.info("  %s: %d shots over %d matches scored (mean p_goal=%.3f)",
                season, len(shots), len(match_ids), shots["p_goal"].mean())
    return team_xg, match_ids


def backfill_season(model, season: str, force: bool = False) -> None:
    csv_path = WC_DIR / season / "match_logs_normalized.csv"
    if not csv_path.exists():
        logger.warning("Normalized CSV missing, skipping: %s", csv_path)
        return

    team_xg, shot_match_ids = _team_xg_for_season(model, season)
    df = pd.read_csv(csv_path)

    # Needed after changing the aggregation, e.g. excluding penalties
    if force:
        df["xg_for"] = None
        df["xg_against"] = None

    null_mask = df["xg_for"].isna()
    covered = df["match_id"].isin(shot_match_ids)
    target = null_mask & covered

    updated_matches: set = set()
    for idx in df.index[target]:
        mid = df.at[idx, "match_id"]
        tid = df.at[idx, "team_id"]
        opp = df.at[idx, "opponent_id"]
        df.at[idx, "xg_for"] = round(float(team_xg.get((mid, tid), 0.0)), 3)
        df.at[idx, "xg_against"] = round(float(team_xg.get((mid, opp), 0.0)), 3)
        updated_matches.add(mid)

    df.to_csv(csv_path, index=False)

    n_updated_rows = int(target.sum())
    avg_xg = float(df.loc[target, "xg_for"].mean()) if n_updated_rows else 0.0
    logger.info(
        "UPDATED %s/%s: %d matches, %d team-rows, avg xG/team-match=%.2f -> %s",
        COMPETITION_ID, season, len(updated_matches), n_updated_rows,
        avg_xg, csv_path.relative_to(PROJECT_ROOT).as_posix(),
    )
    skipped = int((null_mask & ~covered).sum())
    if skipped:
        logger.info("  %d NULL rows left untouched (no shot coverage)", skipped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill match xG from StatsBomb shot aggregates"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Clear existing xg_for/xg_against on WC 2018/2022 rows and refill "
             "(use after changing the aggregation).",
    )
    args = parser.parse_args()

    logger.info("Backfilling match xG from StatsBomb shot aggregates%s",
                " (--force: clearing existing xG first)" if args.force else "")
    model = _resolve_shot_model()
    for season in SEASONS:
        backfill_season(model, season, force=args.force)
    logger.info("=" * 60)
    logger.info("Done. Re-run training to pick up the new xG features:")
    logger.info("  python -m ml.pipeline.train")


if __name__ == "__main__":
    main()
