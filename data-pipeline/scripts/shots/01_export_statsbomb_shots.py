"""
01_export_statsbomb_shots.py — XG-05/XG-06 shot-level ingest.

Pulls non-penalty shot events for every international competition in
StatsBomb open data (see soccer/statsbomb_open.py COMPETITIONS: WC 2018/2022,
Euro 2020/2024, Copa América 2024, AFCON 2023, the historic WC matches, and
the women's World Cups and Euros) and writes them to the shot contract
(docs/DATA_CONTRACT_SHOTS.md).

Every feature column describes the moment the ball is struck: shot location,
body part, technique, first-time flag, pressure, assist type, and the
freeze-frame snapshot (defenders in the shooting cone, nearest defender,
goalkeeper position). Post-shot information (end location, outcome detail,
StatsBomb's own xG) never becomes a feature; StatsBomb xG is kept only as the
`sb_xg_benchmark` metadata column for model comparison.

Events are read through a gzip cache (data-pipeline/data/raw/statsbomb_cache/),
so re-runs are offline.

Output (one CSV per tournament):
  data-pipeline/data/raw/shots/{slug}_shots_{season}.csv
  e.g. wc_shots_2022.csv, euro_shots_2024.csv, wwc_shots_2023.csv

Usage:
  python data-pipeline/scripts/shots/01_export_statsbomb_shots.py [--dry-run] [--only KEY ...]
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "data-pipeline"))

from soccer.importers.fbref_soccerdata_importer import TeamMapper  # noqa: E402
from soccer.statsbomb_open import (  # noqa: E402
    COMPETITIONS, Competition, get_events, get_matches, prefetch_events, strip_womens_suffix,
)

logger = logging.getLogger("statsbomb_shots")
logger.setLevel(logging.INFO)
logger.propagate = False
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logger.addHandler(_h)

OUT_DIR = PROJECT_ROOT / "data-pipeline" / "data" / "raw" / "shots"
TEAM_MAP_PATH = PROJECT_ROOT / "data-pipeline" / "data" / "static" / "team_map_intl.csv"

# StatsBomb 120x80 yard pitch; shots always attack toward x=120.
GOAL_X, GOAL_Y = 120.0, 40.0
POST_LEFT_Y, POST_RIGHT_Y = 36.0, 44.0
YARDS_TO_M = 0.9144

SCHEMA_COLS = [
    "shot_id", "match_id", "competition_id", "season_id", "competition_gender",
    "tournament_start_date", "match_date", "team_id", "player_id", "player_name",
    "position", "period", "minute",
    "shot_x", "shot_y", "distance_m", "angle_deg", "body_part", "technique",
    "situation", "first_time", "under_pressure", "assist_type",
    "ff_available", "n_def_in_cone", "nearest_def_m",
    "gk_dist_to_goal_m", "gk_dist_to_shooter_m", "gk_angle_offset_deg",
    "is_goal", "is_penalty", "sb_xg_benchmark",
]

BODY_PART_MAP = {
    "Right Foot": "right_foot",
    "Left Foot": "left_foot",
    "Head": "head",
    "Other": "other",
}

TECHNIQUE_MAP = {
    "Normal": "normal",
    "Volley": "volley",
    "Half Volley": "half_volley",
    "Lob": "lob",
    "Backheel": "backheel",
    "Diving Header": "diving_header",
    "Overhead Kick": "overhead_kick",
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
# Geometry helpers (all inputs in StatsBomb yards)
# ---------------------------------------------------------------------------

def distance_angle(location: list) -> tuple[float, float]:
    x, y = float(location[0]), float(location[1])
    dx, dy = GOAL_X - x, GOAL_Y - y
    distance_m = math.hypot(dx, dy) * YARDS_TO_M
    angle_deg = math.degrees(math.atan2(abs(dy), dx)) if dx != 0 else 90.0
    return round(distance_m, 2), round(angle_deg, 1)


def _sign(p, a, b) -> float:
    return (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])


def in_shooting_cone(point, shooter) -> bool:
    """True if `point` lies inside the triangle shooter -> left post -> right post."""
    a, b, c = shooter, (GOAL_X, POST_LEFT_Y), (GOAL_X, POST_RIGHT_Y)
    d1, d2, d3 = _sign(point, a, b), _sign(point, b, c), _sign(point, c, a)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def freeze_frame_features(freeze_frame: list | None, shooter: list) -> dict:
    """
    Defender and keeper context from the shot's freeze frame (the positions of
    visible players at the moment of the strike). Missing frame -> NaN features
    and ff_available=False.
    """
    empty = {
        "ff_available": False, "n_def_in_cone": float("nan"), "nearest_def_m": float("nan"),
        "gk_dist_to_goal_m": float("nan"), "gk_dist_to_shooter_m": float("nan"),
        "gk_angle_offset_deg": float("nan"),
    }
    if not freeze_frame:
        return empty

    sx, sy = float(shooter[0]), float(shooter[1])
    opponents = [p for p in freeze_frame if not p.get("teammate", False) and p.get("location")]
    keeper = next((p for p in opponents if p.get("position", {}).get("name") == "Goalkeeper"), None)
    outfield = [p for p in opponents if p is not keeper]

    n_cone = sum(1 for p in outfield if in_shooting_cone(p["location"][:2], (sx, sy)))
    nearest = min(
        (math.hypot(p["location"][0] - sx, p["location"][1] - sy) for p in outfield),
        default=float("nan"),
    )

    feats = dict(empty)
    feats.update({
        "ff_available": True,
        "n_def_in_cone": n_cone,
        "nearest_def_m": round(nearest * YARDS_TO_M, 2) if not math.isnan(nearest) else nearest,
    })
    if keeper is not None:
        kx, ky = float(keeper["location"][0]), float(keeper["location"][1])
        feats["gk_dist_to_goal_m"] = round(math.hypot(GOAL_X - kx, GOAL_Y - ky) * YARDS_TO_M, 2)
        feats["gk_dist_to_shooter_m"] = round(math.hypot(kx - sx, ky - sy) * YARDS_TO_M, 2)
        # Angle between shooter->goal-center and shooter->keeper: 0 = keeper
        # square on the shot line, larger = keeper off the line of the shot.
        a_goal = math.atan2(GOAL_Y - sy, GOAL_X - sx)
        a_gk = math.atan2(ky - sy, kx - sx)
        diff = abs(math.degrees(a_gk - a_goal)) % 360
        feats["gk_angle_offset_deg"] = round(min(diff, 360 - diff), 1)
    return feats


# ---------------------------------------------------------------------------
# Event mapping helpers
# ---------------------------------------------------------------------------

def situation_of(shot: dict, play_pattern: str | None) -> str:
    st = shot.get("type", {}).get("name")
    if st == "Penalty":
        return "penalty"
    pp = play_pattern or ""
    if "Counter" in pp:
        return "counter"
    if st in ("Free Kick", "Corner") or pp in SET_PIECE_PATTERNS:
        return "set_piece"
    return "open_play"


def assist_type_of(shot: dict, event_index: dict) -> str:
    kp_id = shot.get("key_pass_id")
    if not kp_id or kp_id not in event_index:
        return "none"
    passinfo = event_index[kp_id].get("pass", {})
    if passinfo.get("cut_back"):
        return "cut_back"
    if passinfo.get("cross"):
        return "cross"
    if passinfo.get("technique", {}).get("name") == "Through Ball" or passinfo.get("through_ball"):
        return "through_ball"
    return "pass"


def make_match_id(match_date: str, home_code: str, away_code: str) -> str:
    return f"{match_date.replace('-', '')}_{home_code.lower()}_{away_code.lower()}"


def resolve_team(mapper: TeamMapper, name: str, unmapped: set) -> str:
    try:
        return mapper.resolve(strip_womens_suffix(name))
    except KeyError:
        unmapped.add(name)
        return strip_womens_suffix(name)[:3].upper()


def shots_from_match(events: list[dict], ctx: dict, mapper: TeamMapper,
                     unmapped: set, stats: dict) -> list[dict]:
    """Extract contract rows from one match's events. Mutates stats/unmapped."""
    event_index = {e["id"]: e for e in events if "id" in e}
    rows = []

    for ev in events:
        if ev.get("type", {}).get("name") != "Shot":
            continue
        shot = ev.get("shot", {})

        if shot.get("type", {}).get("name") == "Penalty":
            stats["penalties_filtered"] += 1
            continue
        if ev.get("period") == 5:  # shootout kicks are penalties too
            stats["penalties_filtered"] += 1
            continue
        outcome = shot.get("outcome", {}).get("name")
        if not outcome:
            stats["null_outcome"] += 1
            continue
        loc = ev.get("location")
        if not loc or len(loc) < 2:
            stats["no_location"] += 1
            continue

        team_code = resolve_team(mapper, ev.get("team", {}).get("name", ""), unmapped)
        distance_m, angle_deg = distance_angle(loc)
        pos_name = ev.get("position", {}).get("name", "UNK")
        tech = shot.get("technique", {}).get("name")

        row = {
            "shot_id": ev["id"],
            "match_id": ctx["match_id"],
            "competition_id": ctx["competition_id"],
            "season_id": ctx["season_id"],
            "competition_gender": ctx["gender"],
            "tournament_start_date": ctx["tournament_start_date"],
            "match_date": ctx["match_date"],
            "team_id": team_code,
            "player_id": ev.get("player", {}).get("id"),
            "player_name": ev.get("player", {}).get("name"),
            "position": POSITION_MAP.get(pos_name, pos_name),
            "period": ev.get("period"),
            "minute": ev.get("minute"),
            "shot_x": round(float(loc[0]), 2),
            "shot_y": round(float(loc[1]), 2),
            "distance_m": distance_m,
            "angle_deg": angle_deg,
            "body_part": BODY_PART_MAP.get(shot.get("body_part", {}).get("name"), "other"),
            "technique": TECHNIQUE_MAP.get(tech, "normal"),
            "situation": situation_of(shot, ev.get("play_pattern", {}).get("name")),
            "first_time": bool(shot.get("first_time", False)),
            "under_pressure": bool(ev.get("under_pressure", False)),
            "assist_type": assist_type_of(shot, event_index),
            "is_goal": outcome == "Goal",
            "is_penalty": False,
            "sb_xg_benchmark": shot.get("statsbomb_xg"),
        }
        row.update(freeze_frame_features(shot.get("freeze_frame"), loc))
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def export_competition(comp: Competition, mapper: TeamMapper, dry_run: bool) -> None:
    out_path = OUT_DIR / f"{comp.file_slug}_shots_{comp.season_id}.csv"
    matches = get_matches(comp)
    if dry_run:
        logger.info("DRY-RUN %s: %d matches -> would write %s", comp.key, len(matches), out_path)
        return

    tournament_start = min(str(m["match_date"]) for m in matches)
    failed = set(prefetch_events([m["match_id"] for m in matches]))
    rows: list[dict] = []
    unmapped: set = set()
    stats = {"penalties_filtered": 0, "null_outcome": 0, "no_location": 0,
             "matches_failed": len(failed)}

    for m in matches:
        if m["match_id"] in failed:
            continue
        home = m["home_team"]["home_team_name"]
        away = m["away_team"]["away_team_name"]
        ctx = {
            "competition_id": comp.competition_id,
            "season_id": comp.season_id,
            "gender": comp.gender,
            "tournament_start_date": tournament_start,
            "match_date": str(m["match_date"]),
            "match_id": make_match_id(str(m["match_date"]),
                                      resolve_team(mapper, home, unmapped),
                                      resolve_team(mapper, away, unmapped)),
        }
        rows.extend(shots_from_match(get_events(m["match_id"]), ctx, mapper, unmapped, stats))

    if not rows:
        logger.error("FAIL %s — 0 shots extracted (matches_failed=%d)", comp.key, stats["matches_failed"])
        return

    df = pd.DataFrame(rows, columns=SCHEMA_COLS).sort_values(["match_date", "match_id", "period", "minute"])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")

    goals = int(df["is_goal"].sum())
    logger.info("OK   %s — %d matches, %d shots, %d goals (%.1f%%), freeze-frame %.0f%% -> %s",
                comp.key, len(matches), len(df), goals, 100 * goals / len(df),
                100 * df["ff_available"].mean(), out_path.name)
    logger.info("     filtered: %d penalties, %d null-outcome, %d no-location; matches_failed=%d",
                stats["penalties_filtered"], stats["null_outcome"], stats["no_location"],
                stats["matches_failed"])
    if unmapped:
        logger.warning("     unmapped team names (3-letter fallback used): %s", sorted(unmapped))


def main() -> None:
    parser = argparse.ArgumentParser(description="Export StatsBomb international shots to the shot contract")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be written without fetching events")
    parser.add_argument("--only", nargs="*", default=None,
                        help="Competition keys to export, e.g. uefa_euro_2024 (default: all)")
    args = parser.parse_args()

    mapper = TeamMapper.load(TEAM_MAP_PATH)
    for comp in COMPETITIONS:
        if args.only and comp.key not in args.only:
            continue
        try:
            export_competition(comp, mapper, args.dry_run)
        except Exception as e:  # noqa: BLE001
            logger.error("FAIL %s — %s", comp.key, e)


if __name__ == "__main__":
    main()
