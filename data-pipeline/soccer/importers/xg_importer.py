"""
=============================================================================
File: soccer/importers/xg_importer.py
Description: Loads and merges xG (expected goals) data from a Kaggle CSV

SOURCE (one-time manual download required):
  Kaggle dataset: "Premier League Matches" by evangower
  URL: https://www.kaggle.com/datasets/evangower/premier-league-matches-19932022

  DOWNLOAD INSTRUCTIONS:
  1. Go to the URL above (free Kaggle account required)
  2. Click the "Download" button (top right of dataset page)
  3. Extract the ZIP file you receive
  4. Find the file named "matches.csv" (or similar — check the dataset files list)
  5. Copy/move it to:
       premalytics/data-pipeline/data/static/xg/understat_epl_xg.csv
  6. That's it — the importer will find it automatically

  WHAT THIS DATASET CONTAINS:
  - EPL matches from 1993 to ~2022 (older seasons + our target 2021-22, 2022-23)
  - Home xG and Away xG per match (from Understat)
  - Match date, home team, away team, home goals, away goals

  FOR SEASONS NOT COVERED (2023-24, 2024-25, 2025-26):
  - xG will remain NULL in the database
  - The ML model handles NULL xG gracefully (it's an optional feature)
  - You can manually supplement later if a more recent dataset becomes available

MERGE STRATEGY:
  This importer doesn't write its own CSV files. Instead, it exposes a
  merge_xg_into_rows() method that takes the list of match rows produced
  by FootballDataImporter and enriches them with xG values by matching on:
    - match_date (YYYY-MM-DD)
    - home_team (normalized)
    - away_team (normalized)
=============================================================================
"""

import logging                          # For structured log output
from pathlib import Path                # Cross-platform file path handling
from typing import Dict, List, Optional # Type hints

import pandas as pd                     # Data manipulation

# Module-level logger tagged with this file's name
logger = logging.getLogger(__name__)

# Default expected location for the Kaggle CSV (relative to this file at runtime)
# Users place the file here after downloading from Kaggle
DEFAULT_XG_CSV = (
    Path(__file__).resolve().parents[2]   # Goes up to data-pipeline/
    / "data"
    / "static"
    / "xg"
    / "understat_epl_xg.csv"
)

# =============================================================================
# TEAM NAME MAP FOR XG SOURCE
# The Kaggle/Understat dataset uses slightly different team name formats.
# We normalize them to match the names from football_data_importer.py.
# Add entries here if you notice mismatches in the merge output.
# =============================================================================
XG_TEAM_NAME_MAP: Dict[str, str] = {
    "Manchester City":      "Manchester City",
    "Manchester United":    "Manchester Utd",
    "Newcastle United":     "Newcastle Utd",
    "Nottingham Forest":    "Nott'ham Forest",
    "Sheffield United":     "Sheffield Utd",
    "Leicester City":       "Leicester City",
    "Leeds United":         "Leeds United",
    "West Ham United":      "West Ham",
    "Wolverhampton Wanderers": "Wolves",
    "Brighton & Hove Albion":  "Brighton",
    "Tottenham Hotspur":    "Tottenham",
    "Luton Town":           "Luton Town",
    "Ipswich Town":         "Ipswich Town",
    # Most other names are identical between the two sources
}


def _normalize_xg_team(raw: str) -> str:
    """
    Normalize a team name from the xG dataset to our internal format.
    Falls back to the original name if not in the map.

    Args:
        raw: Team name string from the Kaggle CSV

    Returns:
        Normalized team name matching football_data_importer.py conventions
    """
    return XG_TEAM_NAME_MAP.get(raw.strip(), raw.strip())   # Return mapped or original


class XGImporter:
    """
    Loads xG (expected goals) data from a Kaggle CSV and merges it into
    match rows produced by FootballDataImporter.

    USAGE:
        xg = XGImporter()                          # Uses default CSV path
        rows_with_xg = xg.merge_xg_into_rows(rows) # Enriches rows in-place
        # Rows now have xg_for and xg_against populated where data is available

    If the CSV file is not found, all xG values remain NULL — the pipeline
    continues working, just without xG features.
    """

    def __init__(self, xg_csv_path: Optional[Path] = None):
        """
        Initialize the XGImporter.

        Args:
            xg_csv_path: Path to the Kaggle xG CSV file.
                         Defaults to data/static/xg/understat_epl_xg.csv
        """
        # Use the provided path or fall back to the default location
        self.xg_csv_path = Path(xg_csv_path) if xg_csv_path else DEFAULT_XG_CSV
        self._xg_lookup: Optional[Dict] = None   # Will hold the lookup dict after loading

    def _load_xg_lookup(self) -> Dict:
        """
        Load the xG CSV and build a lookup dictionary for fast matching.

        The lookup key is a tuple: (match_date, home_team_normalized, away_team_normalized)
        The value is a dict with xg_for and xg_against from each perspective.

        Returns:
            Dict mapping (date, home_team, away_team) → {"home_xg": float, "away_xg": float}

        Returns empty dict if the file is not found (xG is optional).
        """
        if not self.xg_csv_path.exists():
            # File not downloaded yet — warn but don't crash
            logger.warning(
                f"[XG] CSV not found at {self.xg_csv_path}\n"
                f"    xG values will be NULL. To add xG:\n"
                f"    1. Download from https://www.kaggle.com/datasets/evangower/premier-league-matches-19932022\n"
                f"    2. Place 'matches.csv' at: {self.xg_csv_path}"
            )
            return {}   # Return empty dict — everything else continues normally

        logger.info(f"[XG] Loading xG data from {self.xg_csv_path}")
        df = pd.read_csv(self.xg_csv_path)   # Read the CSV into a DataFrame

        # Log what columns we found — helps debug name mismatches
        logger.info(f"[XG] Columns found: {list(df.columns)}")

        # We need to handle different possible column naming conventions
        # The Kaggle dataset may use different column names depending on version
        # Try to detect which naming convention is used
        col_map = self._detect_column_mapping(df)
        if col_map is None:
            logger.error("[XG] Could not identify required columns in xG CSV. xG will be NULL.")
            return {}

        lookup = {}   # Our output lookup dict
        skipped = 0   # Count rows we couldn't process

        for _, row in df.iterrows():
            try:
                # Extract and normalize the values using the detected column map
                date_raw = str(row[col_map["date"]]).strip()
                home_raw = str(row[col_map["home_team"]]).strip()
                away_raw = str(row[col_map["away_team"]]).strip()
                home_xg_raw = row.get(col_map["home_xg"])    # May be NaN
                away_xg_raw = row.get(col_map["away_xg"])    # May be NaN

                # Parse the date to YYYY-MM-DD format
                # Kaggle dataset often uses YYYY-MM-DD already, but handle both
                try:
                    from datetime import datetime
                    if "-" in date_raw and len(date_raw) == 10:
                        date_norm = date_raw    # Already YYYY-MM-DD
                    else:
                        date_norm = datetime.strptime(date_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    skipped += 1
                    continue    # Skip rows with unparseable dates

                # Normalize team names using our mapping
                home_norm = _normalize_xg_team(home_raw)
                away_norm = _normalize_xg_team(away_raw)

                # Convert xG to float safely
                home_xg = float(home_xg_raw) if pd.notna(home_xg_raw) else None
                away_xg = float(away_xg_raw) if pd.notna(away_xg_raw) else None

                # Build the lookup key — same key used by merge_xg_into_rows
                key = (date_norm, home_norm, away_norm)
                lookup[key] = {"home_xg": home_xg, "away_xg": away_xg}

            except Exception as e:
                skipped += 1
                logger.debug(f"[XG] Skipped row due to error: {e}")

        logger.info(f"[XG] Loaded {len(lookup)} xG entries ({skipped} rows skipped)")
        return lookup

    def _detect_column_mapping(self, df: pd.DataFrame) -> Optional[Dict[str, str]]:
        """
        Try to automatically detect which columns in the CSV correspond to
        date, home team, away team, home xG, and away xG.

        Handles multiple known Kaggle dataset column naming conventions.

        Args:
            df: DataFrame loaded from the xG CSV

        Returns:
            Dict mapping our field names → actual CSV column names,
            or None if required columns cannot be found.
        """
        cols = [c.lower() for c in df.columns]    # Lowercase for case-insensitive matching
        orig_cols = list(df.columns)               # Original casing for actual access

        def find_col(*candidates):
            """
            Find the first matching column name from a list of candidates.
            Returns the actual (original-case) column name if found.
            """
            for c in candidates:
                if c.lower() in cols:
                    idx = cols.index(c.lower())
                    return orig_cols[idx]
            return None    # None if no candidate matched

        # Try to find each required column using multiple possible names
        date_col     = find_col("date", "Date", "match_date")
        home_col     = find_col("home", "Home", "home_team", "HomeTeam", "home_team_name")
        away_col     = find_col("away", "Away", "away_team", "AwayTeam", "away_team_name")
        home_xg_col  = find_col("xg", "xG", "home_xg", "HomeXG", "h_xg", "xg_h", "xGH")
        away_xg_col  = find_col("xga", "xGA", "away_xg", "AwayXG", "a_xg", "xg_a", "xGA", "xGHa")

        # All five columns are required — if any is missing, we can't proceed
        if not all([date_col, home_col, away_col, home_xg_col, away_xg_col]):
            logger.warning(
                f"[XG] Column detection failed.\n"
                f"    date={date_col}, home={home_col}, away={away_col}, "
                f"home_xg={home_xg_col}, away_xg={away_xg_col}\n"
                f"    Available columns: {orig_cols}\n"
                f"    Please update XG_COLUMN_OVERRIDES in xg_importer.py if needed."
            )
            return None

        return {
            "date":       date_col,
            "home_team":  home_col,
            "away_team":  away_col,
            "home_xg":    home_xg_col,
            "away_xg":    away_xg_col,
        }

    def merge_xg_into_rows(self, rows: List[Dict]) -> List[Dict]:
        """
        Enrich a list of match rows with xG values from the Kaggle dataset.

        Modifies rows in-place by setting xg_for and xg_against where a match
        is found in the xG lookup. Unmatched rows keep xg_for=None, xg_against=None.

        Matching is done by (match_date, home_team, away_team) — same match_id
        logic used in FootballDataImporter.

        Args:
            rows: List of match row dicts from FootballDataImporter.load_all_seasons()

        Returns:
            The same list with xg_for and xg_against populated where possible.
        """
        # Load the xG lookup on first use (cached after that)
        if self._xg_lookup is None:
            self._xg_lookup = self._load_xg_lookup()

        if not self._xg_lookup:
            logger.warning("[XG] No xG data available — all xG values will be NULL")
            return rows    # Return rows unchanged if no xG data

        matched = 0         # rows that received xG values
        unmatched = 0       # rows where lookup key was not found
        null_xg_filled = 0  # rows where lookup matched but both xG values were None
        skipped_venue = 0   # rows with missing/invalid venue field
        sample_unmatched: list = []  # first few unmatched keys for diagnosis

        for row in rows:
            date = row.get("match_date")
            venue = row.get("venue")
            team = row.get("team_id")
            opponent = row.get("opponent_id")

            if venue not in ("Home", "Away"):
                skipped_venue += 1
                continue

            if venue == "Home":
                key = (date, team, opponent)
                xg_data = self._xg_lookup.get(key)
                if xg_data:
                    row["xg_for"]     = xg_data["home_xg"]
                    row["xg_against"] = xg_data["away_xg"]
                    if xg_data["home_xg"] is None and xg_data["away_xg"] is None:
                        null_xg_filled += 1
                    matched += 1
                else:
                    unmatched += 1
                    if len(sample_unmatched) < 5:
                        sample_unmatched.append(key)
            else:
                key = (date, opponent, team)
                xg_data = self._xg_lookup.get(key)
                if xg_data:
                    row["xg_for"]     = xg_data["away_xg"]
                    row["xg_against"] = xg_data["home_xg"]
                    if xg_data["home_xg"] is None and xg_data["away_xg"] is None:
                        null_xg_filled += 1
                    matched += 1
                else:
                    unmatched += 1
                    if len(sample_unmatched) < 5:
                        sample_unmatched.append(key)

        total = matched + unmatched
        pct = matched / total * 100 if total else 0
        logger.info(
            f"[XG] Merge complete: {matched}/{total} rows enriched ({pct:.0f}%), "
            f"{unmatched} unmatched (NULL xG)"
        )
        if null_xg_filled:
            logger.warning(
                f"[XG] {null_xg_filled} matched rows have NULL home+away xG in the source CSV — "
                f"check for incomplete data in {self.xg_csv_path.name}"
            )
        if skipped_venue:
            logger.warning(f"[XG] {skipped_venue} rows skipped — missing or invalid venue field")
        if unmatched and sample_unmatched:
            logger.warning(
                f"[XG] Unmatched keys (first {len(sample_unmatched)}): {sample_unmatched}\n"
                f"    Fix: add missing team name mappings to XG_TEAM_NAME_MAP in xg_importer.py"
            )
        return rows
