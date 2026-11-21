"""
01_build_penalty_csv.py — PEN-02 penalty kick dataset (v0).

One row per penalty kick (in-game and shootout) from every international
competition in StatsBomb open data (soccer/statsbomb_open.py COMPETITIONS).
Columns and their timing class (pre-kick vs post-kick) are defined in
docs/PENALTY_LABEL_SPEC.md.

Output:
  data-pipeline/data/static/penalties/penalty_kicks_v0.csv

Events come from the shared gzip cache, so this runs offline after the shot
exporter has fetched them (or fetches whatever is missing).

Usage:
  python data-pipeline/scripts/penalties/01_build_penalty_csv.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "data-pipeline"))

from soccer.importers.fbref_soccerdata_importer import TeamMapper  # noqa: E402
from soccer.statsbomb_open import (  # noqa: E402
    COMPETITIONS, get_events, get_matches, prefetch_events, strip_womens_suffix,
)

logger = logging.getLogger("penalties")
logger.setLevel(logging.INFO)
logger.propagate = False
_h = logging.StreamHandler(sys.stdout)
_h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logger.addHandler(_h)

OUT_PATH = PROJECT_ROOT / "data-pipeline" / "data" / "static" / "penalties" / "penalty_kicks_v0.csv"
TEAM_MAP_PATH = PROJECT_ROOT / "data-pipeline" / "data" / "static" / "team_map_intl.csv"
SOURCE = "statsbomb_open"

# Goal mouth on StatsBomb's pitch (yards). Posts at y=36 and y=44, crossbar
# at 2.67 yd (8 ft). The taker faces +x, so smaller y is the TAKER'S LEFT.
POST_LEFT_Y, POST_RIGHT_Y = 36.0, 44.0
CROSSBAR_Z = 8.0 / 3.0
COL_EDGES = (POST_LEFT_Y + 8.0 / 3.0, POST_LEFT_Y + 16.0 / 3.0)   # 38.67, 41.33
ROW_EDGES = (CROSSBAR_Z / 3.0, 2.0 * CROSSBAR_Z / 3.0)             # 0.89, 1.78

OUTCOME_MAP = {
    "Goal": "goal",
    "Saved": "saved",
    "Saved to Post": "saved",
    "Post": "post",
    "Off T": "off_target",
    "Wayward": "off_target",
    "Blocked": "saved",
}
FOOT_MAP = {"Right Foot": "right", "Left Foot": "left"}

SCHEMA_COLS = [
    # identity / provenance
    "kick_id", "source", "competition_id", "season_id", "competition_gender",
    "tournament_start_date", "match_id", "match_date", "team_id", "opponent_id",
    "taker_id", "taker_name", "keeper_id", "keeper_name",
    # pre-kick context
    "phase", "period", "minute", "taker_foot", "team_score_before", "opp_score_before",
    "game_state", "shootout_kick_number", "shootout_round", "team_kick_number",
    "team_kicked_first", "shootout_pressure",
    # post-kick (labels and descriptors; never features)
    "outcome", "is_goal", "end_y", "end_z", "on_target",
    "placement_col", "placement_row", "placement_zone", "foot_side",
    "keeper_technique", "keeper_set",
]


# ---------------------------------------------------------------------------
# Placement zones (pure functions, tested in ml/tests/test_penalties.py)
# ---------------------------------------------------------------------------

def placement_col(end_y: float | None) -> str | None:
    """Horizontal third of the goal from the taker's view: left / center / right."""
    if end_y is None or pd.isna(end_y):
        return None
    if end_y < COL_EDGES[0]:
        return "left"
    if end_y > COL_EDGES[1]:
        return "right"
    return "center"


def placement_row(end_z: float | None) -> str | None:
    """Vertical third of the goal: low / mid / high. Over the bar counts as high."""
    if end_z is None or pd.isna(end_z):
        return None
    if end_z < ROW_EDGES[0]:
        return "low"
    if end_z < ROW_EDGES[1]:
        return "mid"
    return "high"


def placement_zone(end_y, end_z) -> str | None:
    """3x3 zone id like 'low_left'. Wide or high misses map to their nearest edge zone."""
    c, r = placement_col(end_y), placement_row(end_z)
    if c is None or r is None:
        return None
    return f"{r}_{c}"


def is_on_target(end_y, end_z) -> bool | None:
    if end_y is None or pd.isna(end_y):
        return None
    in_width = POST_LEFT_Y <= end_y <= POST_RIGHT_Y
    in_height = True if end_z is None or pd.isna(end_z) else end_z <= CROSSBAR_Z
    return bool(in_width and in_height)


def foot_side(foot: str | None, col: str | None) -> str | None:
    """
    natural: placed to the taker's non-kicking side (right-footer to the left,
    left-footer to the right), the usual open-body placement.
    across: the opposite side. center: middle third.
    """
    if foot not in ("right", "left") or col is None:
        return None
    if col == "center":
        return "center"
    natural = (foot == "right" and col == "left") or (foot == "left" and col == "right")
    return "natural" if natural else "across"


# ---------------------------------------------------------------------------
# Shootout state
# ---------------------------------------------------------------------------

def shootout_decided(ga: int, ta: int, gb: int, tb: int, rounds: int = 5) -> str | None:
    """
    Winner ('a' / 'b') once a shootout is mathematically decided, else None.
    ga/gb are goals, ta/tb kicks taken. Best of `rounds`, then sudden death
    (decided after equal kicks with unequal goals).
    """
    if ta <= rounds and tb <= rounds:
        if ga > gb + (rounds - tb):
            return "a"
        if gb > ga + (rounds - ta):
            return "b"
        return None
    if ta == tb and ga != gb:
        return "a" if ga > gb else "b"
    return None


def shootout_pressure(ga: int, ta: int, gb: int, tb: int) -> str:
    """
    Pressure on team A's next kick, from the state before it:
      must_score — a miss loses the shootout
      can_win    — a goal wins the shootout
      neutral    — neither
    """
    miss = shootout_decided(ga, ta + 1, gb, tb)
    score = shootout_decided(ga + 1, ta + 1, gb, tb)
    # Sudden death: after A's miss with B still to kick, B scoring decides it,
    # which is not immediate. Only count outcomes decided by this kick alone.
    if miss == "b":
        return "must_score"
    if score == "a":
        return "can_win"
    return "neutral"


def game_state(for_: int, against: int) -> str:
    if for_ > against:
        return "leading"
    if for_ < against:
        return "trailing"
    return "level"


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _keeper_info(shot_ev: dict, event_index: dict) -> dict:
    """Keeper id/name from the freeze frame or related Goal Keeper event, plus the recorded action."""
    info = {"keeper_id": None, "keeper_name": None, "keeper_technique": None, "keeper_set": None}
    for rid in shot_ev.get("related_events", []):
        r = event_index.get(rid)
        if r and r.get("type", {}).get("name") == "Goal Keeper":
            gk = r.get("goalkeeper", {})
            info["keeper_id"] = r.get("player", {}).get("id")
            info["keeper_name"] = r.get("player", {}).get("name")
            tech = gk.get("technique", {}).get("name")
            info["keeper_technique"] = tech.lower() if tech else "none_recorded"
            pos = gk.get("position", {}).get("name")
            info["keeper_set"] = pos.lower() if pos else None
            break
    if info["keeper_id"] is None:
        for p in shot_ev.get("shot", {}).get("freeze_frame", []) or []:
            if not p.get("teammate") and p.get("position", {}).get("name") == "Goalkeeper":
                info["keeper_id"] = p.get("player", {}).get("id")
                info["keeper_name"] = p.get("player", {}).get("name")
                break
    if info["keeper_technique"] is None:
        info["keeper_technique"] = "none_recorded"
    return info


def kicks_from_match(events: list[dict], ctx: dict, team_codes: dict) -> list[dict]:
    """All penalty kicks in one match, with pre-kick context computed from prior events only."""
    events = sorted(events, key=lambda e: e.get("index", 0))
    event_index = {e["id"]: e for e in events if "id" in e}
    teams = list(team_codes)
    goals = {t: 0 for t in teams}            # match score, periods 1-4
    so_goals = {t: 0 for t in teams}         # shootout score
    so_taken = {t: 0 for t in teams}
    so_first = None
    so_number = 0
    rows = []

    for ev in events:
        etype = ev.get("type", {}).get("name")
        team = ev.get("team", {}).get("name")
        period = ev.get("period")

        if etype == "Own Goal For" and period != 5 and team in goals:
            goals[team] += 1
            continue
        if etype != "Shot":
            continue

        shot = ev.get("shot", {})
        is_pen = shot.get("type", {}).get("name") == "Penalty"
        outcome_raw = shot.get("outcome", {}).get("name")
        scored = outcome_raw == "Goal"

        if not is_pen and period != 5:
            if scored and team in goals:
                goals[team] += 1
            continue
        if team not in goals:
            continue

        opp = next(t for t in teams if t != team)
        end = shot.get("end_location") or []
        end_y = float(end[1]) if len(end) > 1 else None
        end_z = float(end[2]) if len(end) > 2 else None
        foot = FOOT_MAP.get(shot.get("body_part", {}).get("name"), "other")
        col = placement_col(end_y)

        row = {
            "kick_id": ev["id"],
            "source": SOURCE,
            **{k: ctx[k] for k in ("competition_id", "season_id", "competition_gender",
                                   "tournament_start_date", "match_id", "match_date")},
            "team_id": team_codes[team],
            "opponent_id": team_codes[opp],
            "taker_id": ev.get("player", {}).get("id"),
            "taker_name": ev.get("player", {}).get("name"),
            "period": period,
            "minute": ev.get("minute"),
            "taker_foot": foot,
            "outcome": OUTCOME_MAP.get(outcome_raw, "other"),
            "is_goal": scored,
            "end_y": end_y,
            "end_z": end_z,
            "on_target": is_on_target(end_y, end_z),
            "placement_col": col,
            "placement_row": placement_row(end_z),
            "placement_zone": placement_zone(end_y, end_z),
            "foot_side": foot_side(foot, col),
        }
        row.update(_keeper_info(ev, event_index))

        if period == 5:
            if so_first is None:
                so_first = team
            so_number += 1
            row.update({
                "phase": "shootout",
                "team_score_before": so_goals[team],
                "opp_score_before": so_goals[opp],
                "game_state": game_state(so_goals[team], so_goals[opp]),
                "shootout_kick_number": so_number,
                "shootout_round": so_taken[team] + 1,
                "team_kick_number": so_taken[team] + 1,
                "team_kicked_first": team == so_first,
                "shootout_pressure": shootout_pressure(
                    so_goals[team], so_taken[team], so_goals[opp], so_taken[opp]),
            })
            so_taken[team] += 1
            so_goals[team] += int(scored)
        else:
            row.update({
                "phase": "in_game",
                "team_score_before": goals[team],
                "opp_score_before": goals[opp],
                "game_state": game_state(goals[team], goals[opp]),
                "shootout_kick_number": None,
                "shootout_round": None,
                "team_kick_number": None,
                "team_kicked_first": None,
                "shootout_pressure": None,
            })
            goals[team] += int(scored)
        rows.append(row)
    return rows


def main() -> None:
    mapper = TeamMapper.load(TEAM_MAP_PATH)
    all_rows: list[dict] = []
    for comp in COMPETITIONS:
        matches = get_matches(comp)
        failed = set(prefetch_events([m["match_id"] for m in matches]))
        start = min(str(m["match_date"]) for m in matches)
        n_before = len(all_rows)
        for m in matches:
            if m["match_id"] in failed:
                logger.warning("skip match %s (events unavailable)", m["match_id"])
                continue
            home = m["home_team"]["home_team_name"]
            away = m["away_team"]["away_team_name"]
            codes = {}
            for name in (home, away):
                try:
                    codes[name] = mapper.resolve(strip_womens_suffix(name))
                except KeyError:
                    codes[name] = strip_womens_suffix(name)[:3].upper()
            ctx = {
                "competition_id": comp.competition_id, "season_id": comp.season_id,
                "competition_gender": comp.gender, "tournament_start_date": start,
                "match_date": str(m["match_date"]),
                "match_id": f"{str(m['match_date']).replace('-', '')}_{codes[home].lower()}_{codes[away].lower()}",
            }
            all_rows.extend(kicks_from_match(get_events(m["match_id"]), ctx, codes))
        added = all_rows[n_before:]
        n_so = sum(r["phase"] == "shootout" for r in added)
        logger.info("%-24s %3d kicks (%3d in-game, %3d shootout)", comp.key, len(added),
                    len(added) - n_so, n_so)

    df = pd.DataFrame(all_rows, columns=SCHEMA_COLS)
    df = df.sort_values(["match_date", "match_id", "period", "minute", "shootout_kick_number"],
                        na_position="first")
    for col in ("shootout_kick_number", "shootout_round", "team_kick_number"):
        df[col] = df[col].astype("Int64")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8")
    logger.info("Wrote %d kicks (%d goals, %.1f%%) -> %s", len(df), int(df["is_goal"].sum()),
                100 * df["is_goal"].mean(), OUT_PATH)


if __name__ == "__main__":
    main()
