"""
Download and normalize EPL match CSVs from football-data.co.uk.

One source match becomes two rows (home/away perspective) for `pl_data.matches`.
"""

import re                        # For regex-based string cleaning
import time                      # For rate-limiting between download requests
import logging                   # For structured log messages
from io import StringIO          # For treating downloaded text as a file object
from pathlib import Path         # For cross-platform file path handling
from datetime import datetime    # For parsing match dates
from typing import Dict, List, Optional  # Type hints

import pandas as pd              # Main data manipulation library
import requests                  # HTTP library for downloading CSVs

# Set up a logger for this module specifically
# When scripts import this, they'll see log messages tagged "football_data_importer"
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
    """
    Convert a team name to a filesystem-safe slug.
    """
    name = name.lower()                        # Lowercase everything
    name = re.sub(r"[^a-z0-9\s]", "", name)   # Remove non-alphanumeric chars (apostrophes, dots)
    name = re.sub(r"\s+", "_", name.strip())  # Replace whitespace with underscores
    return name


def _normalize_team_name(raw: str) -> str:
    """
    Map a football-data.co.uk team name to our internal canonical name.
    Falls back to the original name if not found in the map.
    """
    return TEAM_NAME_MAP.get(raw.strip(), raw.strip())  # Return mapped name or original


def _parse_date(date_str: str) -> Optional[str]:
    """
    Parse a date string from football-data.co.uk into YYYY-MM-DD format.
    The source uses DD/MM/YYYY format (e.g. "13/08/2023").
    """
    if pd.isna(date_str) or str(date_str).strip() == "":   # Handle missing values
        return None
    try:
        # Try the standard DD/MM/YYYY format first
        return datetime.strptime(str(date_str).strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        try:
            # Some rows use DD/MM/YY (two-digit year) format
            return datetime.strptime(str(date_str).strip(), "%d/%m/%y").strftime("%Y-%m-%d")
        except ValueError:
            logger.warning(f"Could not parse date: {date_str!r}")  # Log bad dates
            return None                                               # Return None if all fail


def _safe_int(val) -> Optional[int]:
    """
    Safely convert a value to integer, returning None if not possible.
    Handles NaN, empty strings, and non-numeric values gracefully.
    """
    try:
        if pd.isna(val):           # Check for pandas NaN/None
            return None
        return int(float(val))     # float() first handles "2.0"-style strings
    except (ValueError, TypeError):
        return None                # Return None for anything unparseable


def _determine_result(goals_for: Optional[int], goals_against: Optional[int]) -> Optional[str]:
    """
    Determine match result ('W', 'D', 'L') from goals scored and conceded.
    """
    if goals_for is None or goals_against is None:   # Can't determine without both values
        return None
    if goals_for > goals_against:
        return "W"    # This team scored more → win
    elif goals_for == goals_against:
        return "D"    # Equal goals → draw
    else:
        return "L"    # Conceded more → loss


class FootballDataImporter:
    """
    Downloads and normalizes Premier League match data from football-data.co.uk.
    """

    def __init__(self, static_dir: Path):
        """
        Initialize the importer.
        """
        self.static_dir = Path(static_dir)           # Store the directory path
        self.static_dir.mkdir(parents=True, exist_ok=True)  # Create dirs if missing

    def list_seasons(self) -> List[str]:
        return list(SEASON_URLS.keys())

    def download_season(self, short_season: str, force: bool = False) -> Path:
        """
        Download the CSV for one season from football-data.co.uk.
        """
        if short_season not in SEASON_URLS:
            # Guard against typos in the season key
            raise ValueError(
                f"Unknown season '{short_season}'. "
                f"Valid seasons: {list(SEASON_URLS.keys())}"
            )

        url = SEASON_URLS[short_season]                          # Get the download URL
        dest = self.static_dir / f"{short_season}_E0.csv"       # Local file path

        if dest.exists() and not force:
            # File already downloaded — skip to save bandwidth and time
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
        response.raise_for_status()                # Raise an exception for HTTP 4xx/5xx errors

        # Write the raw CSV bytes to disk
        dest.write_bytes(response.content)
        logger.info(f"[SAVED] {short_season} → {dest} ({dest.stat().st_size} bytes)")
        return dest

    def download_all_seasons(self, force: bool = False) -> Dict[str, Path]:
        """
        Download CSVs for all seasons defined in SEASON_URLS.
        """
        results = {}                                          # Collect paths per season
        for short_season in SEASON_URLS:
            try:
                path = self.download_season(short_season, force=force)
                results[short_season] = path
                time.sleep(1)   # 1-second delay between requests — be polite to the server
            except Exception as e:
                logger.error(f"[ERROR] Failed to download {short_season}: {e}")
                # Don't raise — continue downloading other seasons
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
        """
        Load and normalize match data for one season from the local CSV file.

        Each physical match becomes TWO rows (one per team) to match our DB schema
        where every match is stored from each team's perspective separately.
        """
        csv_path = self.static_dir / f"{short_season}_E0.csv"

        if not csv_path.exists():
            # CSV needs to be downloaded first — guide the user
            raise FileNotFoundError(
                f"CSV not found for {short_season}. "
                f"Run download_season('{short_season}') first.\n"
                f"Expected path: {csv_path}"
            )

        # Read the CSV — football-data.co.uk uses latin-1 encoding (not UTF-8)
        # We use on_bad_lines='skip' to ignore malformed rows at end of partial-season files
        df = pd.read_csv(csv_path, encoding="latin-1", on_bad_lines="skip")
        logger.info(f"[LOAD] {short_season}: {len(df)} raw rows from {csv_path.name}")

        # Drop rows with no date or no teams — these are empty trailing rows
        df = df.dropna(subset=["Date", "HomeTeam", "AwayTeam"])

        full_season = SHORT_TO_FULL_SEASON[short_season]   # Convert "2023-24" → "2023-2024"
        rows = []                                           # Accumulate normalized rows here

        for _, match in df.iterrows():
            # Extract raw values from the CSV row
            raw_home = str(match.get("HomeTeam", "")).strip()   # Home team name
            raw_away = str(match.get("AwayTeam", "")).strip()   # Away team name
            match_date = _parse_date(match.get("Date"))          # Parsed date string

            # Goals (FTHG = Full Time Home Goals, FTAG = Full Time Away Goals)
            home_goals = _safe_int(match.get("FTHG"))
            away_goals = _safe_int(match.get("FTAG"))

            # Normalize team names using our mapping dictionary
            home_team = _normalize_team_name(raw_home)
            away_team = _normalize_team_name(raw_away)

            # Skip if essential data is missing
            if not home_team or not away_team or match_date is None:
                logger.warning(f"Skipping incomplete row: {raw_home} vs {raw_away} on {match.get('Date')}")
                continue

            # Build a unique match_id from date + teams
            date_compact = match_date.replace("-", "")          # "2023-08-13" → "20230813"
            home_slug = _slugify(home_team)                      # "Manchester City" → "manchester_city"
            away_slug = _slugify(away_team)
            match_id = f"{date_compact}_{home_slug}_{away_slug}"  # Unique per match

            # Helper to extract a stat safely by column name
            def stat(col):
                """Get an integer stat from the current row, or None if missing."""
                return _safe_int(match.get(col))

            # ---------------------------------------------------------------
            # ROW 1: Home team's perspective
            # team_id = home team, venue = "Home"
            # goals_for = home goals, goals_against = away goals
            # ---------------------------------------------------------------
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
                # Shots (HS = Home Shots, AS = Away Shots)
                "shots_for":          stat("HS"),
                "shots_against":      stat("AS"),
                # Shots on target (HST = Home Shots on Target)
                "shots_on_target_for":     stat("HST"),
                "shots_on_target_against": stat("AST"),
                # Corners (HC = Home Corners)
                "corners_for":        stat("HC"),
                "corners_against":    stat("AC"),
                # Fouls (HF = Home Fouls)
                "fouls_for":          stat("HF"),
                "fouls_against":      stat("AF"),
                # Cards (HY = Home Yellows, HR = Home Reds)
                "yellow_cards":       stat("HY"),
                "red_cards":          stat("HR"),
                # xG will be merged in separately by xg_importer
                "xg_for":             None,
                "xg_against":         None,
            }
            rows.append(home_row)

            # ---------------------------------------------------------------
            # ROW 2: Away team's perspective
            # team_id = away team, venue = "Away"
            # goals_for = away goals, goals_against = home goals
            # Note: shots/corners/fouls are SWAPPED vs home row
            # ---------------------------------------------------------------
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
                "shots_for":          stat("AS"),             # Away's shots = home's against
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
        """
        Load and normalize all available seasons from disk.
        """
        all_rows = []
        for short_season in SEASON_URLS:
            try:
                rows = self.load_season(short_season)
                all_rows.extend(rows)                        # Add this season's rows to the total
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
