"""Fetch per-team possession, shots on target, and pass accuracy from API-Football into data/raw/api_football/.

Usage: python data-pipeline/scripts/07_fetch_possession_stats.py [--dry-run] [--base-url URL] [--leagues ...] [--seasons ...]
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
import os

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = PIPELINE_DIR.parent
OUT_ROOT = PIPELINE_DIR / "data" / "raw" / "api_football"

DEFAULT_BASE_URL = "https://v3.api-football.com"

LEAGUES = {
    "fifa_world_cup": 1,
    "uefa_euro": 4,
    "copa_america": 9,
    "uefa_nations_league": 5,
}
SEASONS = [2018, 2020, 2022, 2024]

REQUEST_TIMEOUT = 30
# Free tier allows 10 req/min; tighter spacing bursts past it and gets 429'd
FIXTURE_SLEEP_S = 6.5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ApiError(RuntimeError):
    pass


def _get(base_url: str, headers: dict, path: str, params: dict | None = None) -> dict:
    url = f"{base_url}{path}"
    resp = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
    if resp.status_code != 200:
        raise ApiError(f"HTTP {resp.status_code} for {path} — {resp.text[:200]}")
    data = resp.json()
    # Errors arrive inside a 200 response, in the "errors" field
    errors = data.get("errors")
    if errors:
        raise ApiError(f"API errors for {path}: {errors}")
    return data


def _stat_value(stats: list[dict], stat_type: str):
    for s in stats:
        if s.get("type") == stat_type:
            return s.get("value")
    return None


def _pct_to_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except ValueError:
        return None


def verify_and_resolve(base_url: str, headers: dict) -> None:
    logger.info("Verifying API key via GET /status ...")
    status = _get(base_url, headers, "/status")
    resp = status.get("response", {})
    account = resp.get("account", {})
    subscription = resp.get("subscription", {})
    requests_info = resp.get("requests", {})
    logger.info("  Account: %s %s (%s)",
                account.get("firstname", "?"), account.get("lastname", ""),
                account.get("email", "?"))
    logger.info("  Subscription: plan=%s active=%s end=%s",
                subscription.get("plan"), subscription.get("active"),
                subscription.get("end"))
    logger.info("  Requests today: %s / %s",
                requests_info.get("current"), requests_info.get("limit_day"))

    logger.info("Resolving %d league ids ...", len(LEAGUES))
    for comp_id, league_id in LEAGUES.items():
        data = _get(base_url, headers, "/leagues", {"id": league_id})
        rows = data.get("response", [])
        if not rows:
            logger.warning("  [%s] league id=%d -> NO MATCH", comp_id, league_id)
            continue
        league = rows[0].get("league", {})
        country = rows[0].get("country", {})
        seasons = [s.get("year") for s in rows[0].get("seasons", [])]
        avail = [y for y in SEASONS if y in seasons]
        logger.info("  [%s] id=%d -> %s (%s); target seasons available: %s",
                    comp_id, league_id, league.get("name"), country.get("name"), avail)
    logger.info("Dry-run OK — key valid and leagues resolved. "
                "Re-run without --dry-run to fetch and cache stats.")


def fetch_competition(base_url: str, headers: dict, comp_id: str,
                      league_id: int, season: int) -> None:
    out_dir = OUT_ROOT / comp_id / str(season)
    out_csv = out_dir / "possession_stats.csv"
    if out_csv.exists():
        logger.info("[%s/%d] CACHED — %s exists, skipping", comp_id, season,
                    out_csv.name)
        return

    try:
        fixtures_data = _get(base_url, headers, "/fixtures",
                             {"league": league_id, "season": season})
    except ApiError as e:
        logger.warning("[%s/%d] fixtures fetch failed: %s", comp_id, season, e)
        return

    fixtures = fixtures_data.get("response", [])
    logger.info("[%s/%d] %d fixtures returned", comp_id, season, len(fixtures))
    if not fixtures:
        return

    rows: list[dict] = []
    with_stats = 0
    for fx in fixtures:
        fid = fx.get("fixture", {}).get("id")
        match_date = (fx.get("fixture", {}).get("date") or "")[:10]
        home_name = fx.get("teams", {}).get("home", {}).get("name")
        away_name = fx.get("teams", {}).get("away", {}).get("name")

        try:
            stats_data = _get(base_url, headers, "/fixtures/statistics",
                              {"fixture": fid})
        except ApiError as e:
            logger.warning("  fixture %s stats failed: %s", fid, e)
            time.sleep(FIXTURE_SLEEP_S)
            continue
        time.sleep(FIXTURE_SLEEP_S)

        team_stats = stats_data.get("response", [])
        if team_stats:
            with_stats += 1
        for entry in team_stats:
            team_name = entry.get("team", {}).get("name")
            stats = entry.get("statistics", [])
            rows.append({
                "match_date": match_date,
                "home_team_name": home_name,
                "away_team_name": away_name,
                "team_name": team_name,
                "possession_pct": _pct_to_float(_stat_value(stats, "Ball Possession")),
                "shots_on_target": _stat_value(stats, "Shots on Goal"),
                "passes_accuracy": _pct_to_float(_stat_value(stats, "Passes %")),
            })

    if not rows:
        logger.info("[%s/%d] no per-team stats available — nothing written",
                    comp_id, season)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "match_date", "home_team_name", "away_team_name", "team_name",
            "possession_pct", "shots_on_target", "passes_accuracy",
        ])
        writer.writeheader()
        writer.writerows(rows)
    logger.info("[%s/%d] fixtures fetched=%d, with stats=%d, rows=%d -> %s",
                comp_id, season, len(fixtures), with_stats, len(rows),
                out_csv.relative_to(PROJECT_ROOT).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch API-Football possession stats")
    parser.add_argument("--dry-run", action="store_true",
                        help="Verify key + resolve league ids; fetch nothing.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help=f"API base URL (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--leagues", default=None,
                        help="Comma-separated competition_ids to limit the fetch "
                             "(default: all). Useful for staying within the free "
                             "tier's 100 req/day cap.")
    parser.add_argument("--seasons", default=None,
                        help="Comma-separated seasons to limit the fetch (default: all).")
    args = parser.parse_args()

    leagues = ({c: LEAGUES[c] for c in args.leagues.split(",") if c in LEAGUES}
               if args.leagues else dict(LEAGUES))
    seasons = ([int(s) for s in args.seasons.split(",")]
               if args.seasons else list(SEASONS))

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("API_FOOTBALL_KEY")
    if not api_key:
        logger.error("API_FOOTBALL_KEY not found in .env — cannot continue.")
        sys.exit(1)
    headers = {"x-apisports-key": api_key}

    logger.info("API-Football possession fetch (base=%s, dry_run=%s)",
                args.base_url, args.dry_run)

    try:
        if args.dry_run:
            verify_and_resolve(args.base_url, headers)
            return
        for comp_id, league_id in leagues.items():
            for season in seasons:
                fetch_competition(args.base_url, headers, comp_id, league_id, season)
    except ApiError as e:
        logger.error("API-Football request failed: %s", e)
        logger.error("Stopping — not guessing at stats. Check key / plan / host.")
        sys.exit(1)
    except requests.RequestException as e:
        logger.error("Network error reaching %s: %s", args.base_url, e)
        logger.error("Stopping — host unreachable. Try --base-url "
                     "https://v3.football.api-sports.io")
        sys.exit(1)


if __name__ == "__main__":
    main()
