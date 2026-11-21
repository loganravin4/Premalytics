"""Legacy: download EPL match CSVs from football-data.co.uk and normalize each match into home and away rows."""

import re
import time
import logging
from io import StringIO
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)


SEASON_URLS: Dict[str, str] = {
    "2021-22": "https://www.football-data.co.uk/mmz4281/2122/E0.csv",
    "2022-23": "https://www.football-data.co.uk/mmz4281/2223/E0.csv",
    "2023-24": "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
    "2024-25": "https://www.football-data.co.uk/mmz4281/2425/E0.csv",
    "2025-26": "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
}

SHORT_TO_FULL_SEASON: Dict[str, str] = {
    "2021-22": "2021-2022",
    "2022-23": "2022-2023",
    "2023-24": "2023-2024",
    "2024-25": "2024-2025",
    "2025-26": "2025-2026",
}

TEAM_NAME_MAP: Dict[str, str] = {
    "Arsenal":          "Arsenal",
    "Aston Villa":      "Aston Villa",
    "Bournemouth":      "Bournemouth",
    "Brentford":        "Brentford",
    "Brighton":         "Brighton",
    "Burnley":          "Burnley",
    "Chelsea":          "Chelsea",
    "Crystal Palace":   "Crystal Palace",
    "Everton":          "Everton",
    "Fulham":           "Fulham",
    "Ipswich":          "Ipswich Town",
    "Leeds":            "Leeds United",
    "Leicester":        "Leicester City",
    "Liverpool":        "Liverpool",
    "Luton":            "Luton Town",
    "Man City":         "Manchester City",
    "Man United":       "Manchester Utd",
    "Middlesbrough":    "Middlesbrough",
    "Newcastle":        "Newcastle Utd",
    "Norwich":          "Norwich City",
    "Nott'm Forest":    "Nott'ham Forest",
    "Sheffield United": "Sheffield Utd",
    "Southampton":      "Southampton",
    "Tottenham":        "Tottenham",
    "Watford":          "Watford",
    "West Brom":        "West Brom",
    "West Ham":         "West Ham",
    "Wolves":           "Wolves",
}


def _slugify(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\s]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name


def _normalize_team_name(raw: str) -> str:
    return TEAM_NAME_MAP.get(raw.strip(), raw.strip())


def _parse_date(date_str: str) -> Optional[str]:
    if pd.isna(date_str) or str(date_str).strip() == "":
        return None
    try:
        return datetime.strptime(str(date_str).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        try:
            # Some rows use DD/MM/YY (two-digit year) format
            return datetime.strptime(str(date_str).strip(), "%d/%m/%y").strftime("%Y-%m-%d")
        except ValueError:
            logger.warning(f"Could not parse date: {date_str!r}")
            return None


def _safe_int(val) -> Optional[int]:
    try:
        if pd.isna(val):
            return None
        # float() first so "2.0"-style strings parse
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _determine_result(goals_for: Optional[int], goals_against: Optional[int]) -> Optional[str]:
    if goals_for is None or goals_against is None:
        return None
    if goals_for > goals_against:
        return "W"
    elif goals_for == goals_against:
        return "D"
    else:
        return "L"


class FootballDataImporter:

    def __init__(self, static_dir: Path):
        self.static_dir = Path(static_dir)
        self.static_dir.mkdir(parents=True, exist_ok=True)

    def list_seasons(self) -> List[str]:
        return list(SEASON_URLS.keys())

    def download_season(self, short_season: str, force: bool = False) -> Path:
        if short_season not in SEASON_URLS:
            raise ValueError(
                f"Unknown season '{short_season}'. "
                f"Valid seasons: {list(SEASON_URLS.keys())}"
            )

        url = SEASON_URLS[short_season]
        dest = self.static_dir / f"{short_season}_E0.csv"

        if dest.exists() and not force:
            logger.info(f"[SKIP] {short_season} already on disk: {dest}")
            return dest

        logger.info(f"[DOWNLOAD] {short_season} from {url}")
        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "premalytics/1.0 (+https://premalytics.app)",
                "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
            },
        )
        response.raise_for_status()

        dest.write_bytes(response.content)
        logger.info(f"[SAVED] {short_season} → {dest} ({dest.stat().st_size} bytes)")
        return dest

    def download_all_seasons(self, force: bool = False) -> Dict[str, Path]:
        results = {}
        for short_season in SEASON_URLS:
            try:
                path = self.download_season(short_season, force=force)
                results[short_season] = path
                time.sleep(1)
            except Exception as e:
                logger.error(f"[ERROR] Failed to download {short_season}: {e}")
        return results

    def download_seasons(self, seasons: List[str], force: bool = False) -> Dict[str, Path]:
        results: Dict[str, Path] = {}
        for short_season in seasons:
            try:
                results[short_season] = self.download_season(short_season, force=force)
                time.sleep(1)
            except Exception as e:
                logger.error(f"[ERROR] Failed to download {short_season}: {e}")
        return results

    def load_season(self, short_season: str) -> List[Dict]:
        csv_path = self.static_dir / f"{short_season}_E0.csv"

        if not csv_path.exists():
            raise FileNotFoundError(
                f"CSV not found for {short_season}. "
                f"Run download_season('{short_season}') first.\n"
                f"Expected path: {csv_path}"
            )

        # football-data.co.uk is latin-1, and partial-season files end in malformed rows
        df = pd.read_csv(csv_path, encoding="latin-1", on_bad_lines="skip")
        logger.info(f"[LOAD] {short_season}: {len(df)} raw rows from {csv_path.name}")

        # Drops the empty trailing rows
        df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam"])

        full_season = SHORT_TO_FULL_SEASON[short_season]
        rows = []

        for _, match in df.iterrows():
            raw_home = str(match.get("HomeTeam", "")).strip()
            raw_away = str(match.get("AwayTeam", "")).strip()
            match_date = _parse_date(match.get("Date"))

            # FTHG/FTAG are full-time home/away goals
            home_goals = _safe_int(match.get("FTHG"))
            away_goals = _safe_int(match.get("FTAG"))

            home_team = _normalize_team_name(raw_home)
            away_team = _normalize_team_name(raw_away)

            if not home_team or not away_team or match_date is None:
                logger.warning(f"Skipping incomplete row: {raw_home} vs {raw_away} on {match.get('Date')}")
                continue

            date_compact = match_date.replace("-", "")
            home_slug = _slugify(home_team)
            away_slug = _slugify(away_team)
            match_id = f"{date_compact}_{home_slug}_{away_slug}"

            def stat(col):
                return _safe_int(match.get(col))

            home_row = {
                "match_id":           match_id,
                "season_id":          full_season,
                "team_id":            home_team,
                "opponent_id":        away_team,
                "match_date":         match_date,
                "venue":              "Home",
                "goals_for":          home_goals,
                "goals_against":      away_goals,
                "result":             _determine_result(home_goals, away_goals),
                "shots_for":          stat("HS"),
                "shots_against":      stat("AS"),
                "shots_on_target_for":     stat("HST"),
                "shots_on_target_against": stat("AST"),
                "corners_for":        stat("HC"),
                "corners_against":    stat("AC"),
                "fouls_for":          stat("HF"),
                "fouls_against":      stat("AF"),
                "yellow_cards":       stat("HY"),
                "red_cards":          stat("HR"),
                # Merged in later by xg_importer
                "xg_for":             None,
                "xg_against":         None,
            }
            rows.append(home_row)

            # The away perspective swaps every home/away stat column
            away_row = {
                "match_id":           match_id,
                "season_id":          full_season,
                "team_id":            away_team,
                "opponent_id":        home_team,
                "match_date":         match_date,
                "venue":              "Away",
                "goals_for":          away_goals,
                "goals_against":      home_goals,
                "result":             _determine_result(away_goals, home_goals),
                "shots_for":          stat("AS"),
                "shots_against":      stat("HS"),
                "shots_on_target_for":     stat("AST"),
                "shots_on_target_against": stat("HST"),
                "corners_for":        stat("AC"),
                "corners_against":    stat("HC"),
                "fouls_for":          stat("AF"),
                "fouls_against":      stat("HF"),
                "yellow_cards":       stat("AY"),
                "red_cards":          stat("AR"),
                "xg_for":             None,
                "xg_against":         None,
            }
            rows.append(away_row)

        logger.info(f"[NORMALIZE] {short_season}: produced {len(rows)} team-match rows from {len(df)} matches")
        return rows

    def load_all_seasons(self) -> List[Dict]:
        all_rows = []
        for short_season in SEASON_URLS:
            try:
                rows = self.load_season(short_season)
                all_rows.extend(rows)
            except FileNotFoundError as e:
                logger.warning(f"[SKIP] {short_season}: {e}")
            except Exception as e:
                logger.error(f"[ERROR] {short_season}: {e}")
        logger.info(f"[TOTAL] Loaded {len(all_rows)} team-match rows across all seasons")
        return all_rows

    def load_seasons(self, seasons: List[str]) -> List[Dict]:
        all_rows: List[Dict] = []
        for short_season in seasons:
            try:
                all_rows.extend(self.load_season(short_season))
            except Exception as e:
                logger.error(f"[ERROR] Failed to load season {short_season}: {e}")
        return all_rows
