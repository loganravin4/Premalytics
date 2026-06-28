"""
01_export_statsbomb_shots.py — XG-02 shot-level ingest.

Pulls shot events for the FIFA World Cup 2018 and 2022 from StatsBomb open
data and writes them to the shot contract (docs/DATA_CONTRACT_SHOTS.md).

Data access:
  1. If `statsbombpy` is installed, use it (sb.matches / sb.events).
  2. Otherwise fall back to the public StatsBomb open-data GitHub raw JSON
     (no auth required): https://github.com/statsbomb/open-data

StatsBomb identifiers:
  competition 43 = FIFA World Cup; season 3 = 2018, season 106 = 2022.

Output (one CSV per tournament):
  data-pipeline/data/raw/shots/wc_shots_2018.csv
  data-pipeline/data/raw/shots/wc_shots_2022.csv

Usage:
  python data-pipeline/scripts/shots/01_export_statsbomb_shots.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "data-pipeline"))

from soccer.importers.fbref_soccerdata_importer import TeamMapper  # noqa: E402

logger = logging.getLogger("statsbomb_shots")
logger.setLevel(logging.INFO)
logger.propagate = False
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logger.addHandler(_h)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SB_COMPETITION = 43  # FIFA World Cup
SEASONS = {
    "2018": 3,
    "2022": 106,
}
COMPETITION_ID = "fifa_world_cup"

RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
MATCHES_URL = RAW_BASE + "/matches/{comp}/{season}.json"
EVENTS_URL = RAW_BASE + "/events/{mid}.json"

OUT_DIR = PROJECT_ROOT / "data-pipeline" / "data" / "raw" / "shots"
TEAM_MAP_PATH = PROJECT_ROOT / "data-pipeline" / "data" / "static" / "team_map_intl.csv"

# Goal centre on StatsBomb's 120x80 yard pitch.
GOAL_X, GOAL_Y = 120.0, 40.0
YARDS_TO_M = 0.9144

SCHEMA_COLS = [
    "shot_id", "match_id", "competition_id", "season_id", "match_date",
    "team_id", "player_id", "player_name", "position", "minute",
    "distance_m", "angle_deg", "body_part", "situation",
    "is_goal", "is_penalty", "under_pressure", "assist_type",
]

BODY_PART_MAP = {
    "Right Foot": "right_foot",
    "Left Foot": "left_foot",
    "Head": "head",
    "Other": "other",
}

POSITION_MAP = {
    "Goalkeeper": "GK",
    "Right Back": "RB", "Left Back": "LB",
    "Right Center Back": "CB", "Center Back": "CB", "Left Center Back": "CB",
    "Right Wing Back": "RWB", "Left Wing Back": "LWB",
    "Right Defensive Midfield": "CDM", "Center Defensive Midfield": "CDM",
    "Left Defensive Midfield": "CDM",
    "Right Midfield": "RM", "Left Midfield": "LM",
    "Right Center Midfield": "CM", "Center Midfield": "CM",
    "Left Center Midfield": "CM",
    "Right Wing": "RW", "Left Wing": "LW",
    "Right Attacking Midfield": "CAM", "Center Attacking Midfield": "CAM",
    "Left Attacking Midfield": "CAM",
    "Right Center Forward": "ST", "Center Forward": "ST",
    "Left Center Forward": "ST", "Secondary Striker": "ST",
}

# Set-piece play patterns. Throw-in / goal-kick / keeper-distribution
# possessions are open play, so only corner and free-kick origins count.
SET_PIECE_PATTERNS = {"From Corner", "From Free Kick"}

# ---------------------------------------------------------------------------
# Data access layer (statsbombpy if available, else GitHub raw JSON)
# ---------------------------------------------------------------------------
try:
    from statsbombpy import sb  # type: ignore
    HAVE_STATSBOMBPY = True
except ImportError:
    HAVE_STATSBOMBPY = False


def _fetch_json(url: str, retries: int = 3, sleep: float = 2.0):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "premalytics-xg/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.debug("fetch attempt %d failed for %s: %s", attempt, url, e)
            time.sleep(sleep)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def get_matches(season_sb: int) -> list[dict]:
    """Return [{match_id, match_date, home, away}] for a StatsBomb season."""
    if HAVE_STATSBOMBPY:
        df = sb.matches(competition_id=SB_COMPETITION, season_id=season_sb)
        return [
            {"match_id": r.match_id, "match_date": r.match_date,
             "home": r.home_team, "away": r.away_team}
            for r in df.itertuples()
        ]
    data = _fetch_json(MATCHES_URL.format(comp=SB_COMPETITION, season=season_sb))
    return [
        {"match_id": m["match_id"], "match_date": m["match_date"],
         "home": m["home_team"]["home_team_name"],
         "away": m["away_team"]["away_team_name"]}
        for m in data
    ]


def get_events(match_id: int) -> list[dict]:
    """Return the raw event dicts for a match (same shape on both paths)."""
    if HAVE_STATSBOMBPY:
        return list(sb.events(match_id=match_id, fmt="dict").values())
    return _fetch_json(EVENTS_URL.format(mid=match_id))


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

def _distance_angle(location: list) -> tuple[float, float]:
    x, y = float(location[0]), float(location[1])
    dx, dy = GOAL_X - x, GOAL_Y - y
    distance_m = math.hypot(dx, dy) * YARDS_TO_M
    angle_deg = math.degrees(math.atan2(abs(dy), dx)) if dx != 0 else 90.0
    return round(distance_m, 2), round(angle_deg, 1)


def _situation(shot: dict, play_pattern: str | None) -> str:
    st = shot.get("type", {}).get("name")
    if st == "Penalty":
        return "penalty"
    pp = play_pattern or ""
    if "Counter" in pp:
        return "counter"
    if st in ("Free Kick", "Corner") or pp in SET_PIECE_PATTERNS:
        return "set_piece"
    return "open_play"


def _assist_type(shot: dict, event_index: dict) -> str:
    kp_id = shot.get("key_pass_id")
    if not kp_id or kp_id not in event_index:
        return "none"
    passinfo = event_index[kp_id].get("pass", {})
    if passinfo.get("cross"):
        return "cross"
    if passinfo.get("technique", {}).get("name") == "Through Ball":
        return "through_ball"
    return "pass"


def _match_id(match_date: str, home_code: str, away_code: str) -> str:
    return f"{match_date.replace('-', '')}_{home_code.lower()}_{away_code.lower()}"


def shots_from_match(events: list[dict], ctx: dict, mapper: TeamMapper,
                     unmapped: set, stats: dict) -> list[dict]:
    """Extract contract rows from one match's events. Mutates stats/unmapped."""
    event_index = {e["id"]: e for e in events if "id" in e}
    rows = []

    for ev in events:
        if ev.get("type", {}).get("name") != "Shot":
            continue
        shot = ev.get("shot", {})

        # --- filters ---
        if shot.get("type", {}).get("name") == "Penalty":
            stats["penalties_filtered"] += 1
            continue
        outcome = shot.get("outcome", {}).get("name")
        if not outcome:  # is_goal would be null
            stats["null_outcome"] += 1
            continue
        loc = ev.get("location")
        if not loc or len(loc) < 2:
            stats["no_location"] += 1
            continue

        team_name = ev.get("team", {}).get("name", "")
        try:
            team_code = mapper.resolve(team_name)
        except KeyError:
            unmapped.add(team_name)
            continue

        distance_m, angle_deg = _distance_angle(loc)
        body_part = BODY_PART_MAP.get(shot.get("body_part", {}).get("name"), "other")
        situation = _situation(shot, ev.get("play_pattern", {}).get("name"))
        position = POSITION_MAP.get(
            ev.get("position", {}).get("name"),
            ev.get("position", {}).get("name", "UNK"),
        )

        rows.append({
            "shot_id": ev["id"],
            "match_id": ctx["match_id"],
            "competition_id": COMPETITION_ID,
            "season_id": ctx["season_id"],
            "match_date": ctx["match_date"],
            "team_id": team_code,
            "player_id": ev.get("player", {}).get("id"),
            "player_name": ev.get("player", {}).get("name"),
            "position": position,
            "minute": ev.get("minute"),
            "distance_m": distance_m,
            "angle_deg": angle_deg,
            "body_part": body_part,
            "situation": situation,
            "is_goal": outcome == "Goal",
            "is_penalty": False,  # penalties are filtered out above
            "under_pressure": bool(ev.get("under_pressure", False)),
            "assist_type": _assist_type(shot, event_index),
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Export StatsBomb WC shots to the shot contract")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be fetched/written without fetching events or writing")
    args = parser.parse_args()

    logger.info("statsbombpy %s", "available" if HAVE_STATSBOMBPY else "NOT installed — using GitHub raw JSON")
    mapper = TeamMapper.load(TEAM_MAP_PATH)

    for season_id, season_sb in SEASONS.items():
        out_path = OUT_DIR / f"wc_shots_{season_id}.csv"
        try:
            matches = get_matches(season_sb)
        except Exception as e:  # noqa: BLE001
            logger.error("FAIL %s/%s — could not fetch matches index: %s",
                         COMPETITION_ID, season_id, e)
            continue

        if args.dry_run:
            logger.info("DRY-RUN %s (sb season %s): %d matches -> would write %s",
                        season_id, season_sb, len(matches), out_path)
            continue

        logger.info("Fetching %s (sb season %s): %d matches ...", season_id, season_sb, len(matches))
        rows: list[dict] = []
        unmapped: set = set()
        stats = {"penalties_filtered": 0, "null_outcome": 0, "no_location": 0, "matches_failed": 0}

        for i, m in enumerate(matches, 1):
            try:
                home_code = mapper.resolve(m["home"])
                away_code = mapper.resolve(m["away"])
            except KeyError as e:
                unmapped.add(str(e).strip("'\""))
                home_code = str(m["home"])[:3].upper()
                away_code = str(m["away"])[:3].upper()

            ctx = {
                "season_id": season_id,
                "match_date": str(m["match_date"]),
                "match_id": _match_id(str(m["match_date"]), home_code, away_code),
            }
            try:
                events = get_events(m["match_id"])
            except Exception as e:  # noqa: BLE001
                stats["matches_failed"] += 1
                logger.warning("  match %s (%s vs %s) failed: %s",
                               m["match_id"], m["home"], m["away"], e)
                continue

            rows.extend(shots_from_match(events, ctx, mapper, unmapped, stats))
            if i % 16 == 0:
                logger.info("  ...%d/%d matches processed (%d shots so far)", i, len(matches), len(rows))

        if not rows:
            logger.error("FAIL %s — 0 shots extracted (matches_failed=%d)",
                         season_id, stats["matches_failed"])
            continue

        df = pd.DataFrame(rows, columns=SCHEMA_COLS).sort_values(["match_date", "match_id", "minute"])
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False, encoding="utf-8")

        goals = int(df["is_goal"].sum())
        total = len(df)
        conv = goals / total if total else 0.0
        logger.info("OK   %s/%s — %d shots, %d goals, conversion=%.1f%% -> %s",
                    COMPETITION_ID, season_id, total, goals, conv * 100, out_path)
        logger.info("     filtered: %d penalties, %d null-outcome, %d no-location; "
                    "matches_failed=%d", stats["penalties_filtered"], stats["null_outcome"],
                    stats["no_location"], stats["matches_failed"])
        if unmapped:
            logger.warning("     unmapped team names (fallback slug used): %s", sorted(unmapped))


if __name__ == "__main__":
    main()
