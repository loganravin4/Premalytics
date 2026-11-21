"""Legacy EPL xG merge from a manually downloaded Kaggle/Understat CSV; the international pipeline doesn't use it."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_XG_CSV = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "static"
    / "xg"
    / "understat_epl_xg.csv"
)

# Kaggle/Understat names differ from football-data.co.uk's; add entries when the merge misses
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
}


def _normalize_xg_team(raw: str) -> str:
    return XG_TEAM_NAME_MAP.get(raw.strip(), raw.strip())


class XGImporter:
    """Merges Kaggle xG into FootballDataImporter rows; a missing CSV leaves xG NULL instead of failing."""

    def __init__(self, xg_csv_path: Optional[Path] = None):
        self.xg_csv_path = Path(xg_csv_path) if xg_csv_path else DEFAULT_XG_CSV
        self._xg_lookup: Optional[Dict] = None

    def _load_xg_lookup(self) -> Dict:
        if not self.xg_csv_path.exists():
            logger.warning(
                f"[XG] CSV not found at {self.xg_csv_path}\n"
                f"    xG values will be NULL. To add xG:\n"
                f"    1. Download from https://www.kaggle.com/datasets/evangower/premier-league-matches-19932022\n"
                f"    2. Place 'matches.csv' at: {self.xg_csv_path}"
            )
            return {}

        logger.info(f"[XG] Loading xG data from {self.xg_csv_path}")
        df = pd.read_csv(self.xg_csv_path)

        logger.info(f"[XG] Columns found: {list(df.columns)}")

        # Column names vary across versions of the Kaggle dataset
        col_map = self._detect_column_mapping(df)
        if col_map is None:
            logger.error("[XG] Could not identify required columns in xG CSV. xG will be NULL.")
            return {}

        lookup = {}
        skipped = 0

        for _, row in df.iterrows():
            try:
                date_raw = str(row[col_map["date"]]).strip()
                home_raw = str(row[col_map["home_team"]]).strip()
                away_raw = str(row[col_map["away_team"]]).strip()
                home_xg_raw = row.get(col_map["home_xg"])
                away_xg_raw = row.get(col_map["away_xg"])

                # Some dataset versions use DD/MM/YYYY
                try:
                    from datetime import datetime
                    if "-" in date_raw and len(date_raw) == 10:
                        date_norm = date_raw
                    else:
                        date_norm = datetime.strptime(date_raw, "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    skipped += 1
                    continue

                home_norm = _normalize_xg_team(home_raw)
                away_norm = _normalize_xg_team(away_raw)

                home_xg = float(home_xg_raw) if pd.notna(home_xg_raw) else None
                away_xg = float(away_xg_raw) if pd.notna(away_xg_raw) else None

                key = (date_norm, home_norm, away_norm)
                lookup[key] = {"home_xg": home_xg, "away_xg": away_xg}

            except Exception as e:
                skipped += 1
                logger.debug(f"[XG] Skipped row due to error: {e}")

        logger.info(f"[XG] Loaded {len(lookup)} xG entries ({skipped} rows skipped)")
        return lookup

    def _detect_column_mapping(self, df: pd.DataFrame) -> Optional[Dict[str, str]]:
        cols = [c.lower() for c in df.columns]
        orig_cols = list(df.columns)

        def find_col(*candidates):
            for c in candidates:
                if c.lower() in cols:
                    idx = cols.index(c.lower())
                    return orig_cols[idx]
            return None

        date_col     = find_col("date", "Date", "match_date")
        home_col     = find_col("home", "Home", "home_team", "HomeTeam", "home_team_name")
        away_col     = find_col("away", "Away", "away_team", "AwayTeam", "away_team_name")
        home_xg_col  = find_col("xg", "xG", "home_xg", "HomeXG", "h_xg", "xg_h", "xGH")
        away_xg_col  = find_col("xga", "xGA", "away_xg", "AwayXG", "a_xg", "xg_a", "xGA", "xGHa")

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
        if self._xg_lookup is None:
            self._xg_lookup = self._load_xg_lookup()

        if not self._xg_lookup:
            logger.warning("[XG] No xG data available — all xG values will be NULL")
            return rows

        matched = 0
        unmatched = 0
        null_xg_filled = 0
        skipped_venue = 0
        sample_unmatched: list = []

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
