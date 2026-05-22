"""
=============================================================================
Module: fbref_soccerdata_importer
Description: International match ingest via soccerdata → FBref

WHAT THIS MODULE DOES:
  1. Configures soccerdata cache under {project_root}/.soccerdata/
  2. Downloads FBref schedule pages (Chrome + Selenium when cache is cold)
  3. Normalizes each fixture into TWO rows (home + away perspective)
  4. Writes match_logs_normalized.csv per DATA_CONTRACT.md (WC pivot)

OUTPUT PATH (one CSV per tournament year):
  data-pipeline/data/raw/{competition_id}/{season_id}/match_logs_normalized.csv

See also: docs/WC_SOURCES.md, DATA_CONTRACT.md, docs/VENV.md
=============================================================================
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Competition registry
# ---------------------------------------------------------------------------
# Keys are our stable slugs (used in paths and ML config).
# Values map to soccerdata league IDs and which season years to pull.

COMPETITIONS: Dict[str, Dict[str, Any]] = {
    "fifa_world_cup": {
        "league": "INT-World Cup",           # built-in soccerdata ID
        "seasons": [2018, 2022],             # tournament years (single-year)
        "default_weight": 1.0,               # sample_weight for group/knockout
    },
    "uefa_euro": {
        "league": "INT-European Championship",
        "seasons": [2020, 2024],             # Euro 2020 played in 2021; season_id still "2020"
        "default_weight": 1.0,
    },
}

# Extra international comps — not in upstream soccerdata by default.
# Written to .soccerdata/config/league_dict.json before `import soccerdata`.
# WC-01b must verify each comp actually scrapes before adding to COMPETITIONS.
CUSTOM_LEAGUES = {
    "INT-Copa America": {"FBref": "Copa América", "season_code": "single-year"},
    "INT-WCQ UEFA": {"FBref": "UEFA World Cup Qualifiers", "season_code": "single-year"},
    "INT-WCQ CONMEBOL": {"FBref": "CONMEBOL World Cup Qualifiers", "season_code": "single-year"},
    "INT-Nations League": {
        "FBref": "UEFA Nations League",
        "season_start": "Sep",
        "season_end": "Jun",
    },
}

# ---------------------------------------------------------------------------
# Score parsing (FBref uses Unicode en-dashes, not ASCII hyphens)
# ---------------------------------------------------------------------------

# Split "1–1" or "6–2" on any common dash character
SCORE_SPLIT_RE = re.compile(r"[\u2013\u2014\-–]+")

# Knockout games decided on pens: "(3) 1–1 (4)" → regulation goals 1–1 only
PENALTY_SCORE_RE = re.compile(
    r"\(\d+\)\s*(\d+)\s*[\u2013\u2014\-–]\s*(\d+)\s*\(\d+\)"
)

# Optional: "Group G" in round string → group_name column
GROUP_LETTER_RE = re.compile(r"Group\s+([A-H])\b", re.I)

# ---------------------------------------------------------------------------
# Team name → FIFA 3-letter code
# ---------------------------------------------------------------------------
# Fallback when team_map_intl.csv has no row. CSV aliases override these.

DEFAULT_TEAM_CODES: Dict[str, str] = {
    "Argentina": "ARG",
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Brazil": "BRA",
    "Cameroon": "CMR",
    "Canada": "CAN",
    "Chile": "CHI",
    "Colombia": "COL",
    "Costa Rica": "CRC",
    "Croatia": "CRO",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Denmark": "DEN",
    "Ecuador": "ECU",
    "Egypt": "EGY",
    "England": "ENG",
    "France": "FRA",
    "Germany": "GER",
    "Ghana": "GHA",
    "Greece": "GRE",
    "Hungary": "HUN",
    "Iceland": "ISL",
    "IR Iran": "IRN",
    "Iran": "IRN",
    "Italy": "ITA",
    "Japan": "JPN",
    "Korea Republic": "KOR",
    "South Korea": "KOR",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NED",
    "Nigeria": "NGA",
    "Norway": "NOR",
    "Panama": "PAN",
    "Paraguay": "PAR",
    "Peru": "PER",
    "Poland": "POL",
    "Portugal": "POR",
    "Qatar": "QAT",
    "Romania": "ROU",
    "Russia": "RUS",
    "Saudi Arabia": "KSA",
    "Scotland": "SCO",
    "Senegal": "SEN",
    "Serbia": "SRB",
    "Slovakia": "SVK",
    "Slovenia": "SVN",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "SUI",
    "Tunisia": "TUN",
    "Turkey": "TUR",
    "Ukraine": "UKR",
    "United States": "USA",
    "Uruguay": "URU",
    "Wales": "WAL",
    "Albania": "ALB",
    "Georgia": "GEO",
}


def setup_soccerdata_env(project_root: Path) -> Path:
    """
    Prepare soccerdata before the library is imported anywhere in the process.

    soccerdata reads league_dict.json at import time, so this must run first.
    Sets SOCCERDATA_DIR to {project_root}/.soccerdata (gitignored cache).
    """
    sd_dir = project_root / ".soccerdata"
    config_dir = sd_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    # Merge custom international leagues (Copa, qualifiers, etc.)
    (config_dir / "league_dict.json").write_text(
        json.dumps(CUSTOM_LEAGUES, indent=2), encoding="utf-8"
    )

    # Only set if caller has not already pointed elsewhere
    os.environ.setdefault("SOCCERDATA_DIR", str(sd_dir))
    return sd_dir


def _parse_score(score: Any) -> Tuple[Optional[int], Optional[int], Optional[float], Optional[float]]:
    """
    Parse FBref's score column into home/away goals (and optional xG).

    Returns:
        (home_goals, away_goals, home_xg, away_xg)
        xG slots are usually None for international schedules.
    """
    if score is None or (isinstance(score, float) and pd.isna(score)):
        return None, None, None, None

    text = str(score).strip()
    if not text:
        return None, None, None, None

    # Penalty shootout: ignore pen counts in parentheses
    pen = PENALTY_SCORE_RE.search(text)
    if pen:
        return int(pen.group(1)), int(pen.group(2)), None, None

    # Normal full-time score: "2–0", "1–1", etc.
    parts = [p.strip() for p in SCORE_SPLIT_RE.split(text) if p.strip()]
    if len(parts) != 2:
        return None, None, None, None

    def _num(part: str) -> Optional[float]:
        try:
            return float(part)
        except ValueError:
            return None

    a, b = _num(parts[0]), _num(parts[1])
    if a is None or b is None:
        return None, None, None, None

    # Decimal parts on some club tables mean xG, not goals — rare for intl
    if a != int(a) or b != int(b):
        return None, None, float(a), float(b)
    return int(a), int(b), None, None


def _determine_result(goals_for: Optional[int], goals_against: Optional[int]) -> Optional[str]:
    """Map goals to W/D/L from the scoring team's perspective."""
    if goals_for is None or goals_against is None:
        return None
    if goals_for > goals_against:
        return "W"
    if goals_for == goals_against:
        return "D"
    return "L"


def _infer_stage(round_name: Any) -> str:
    """
    Map FBref 'round' text to contract competition_stage values.

    Examples: "Group stage" → group, "Quarter-finals" → knockout, "Final" → final
    """
    if round_name is None or (isinstance(round_name, float) and pd.isna(round_name)):
        return "knockout"
    r = str(round_name).strip().lower()
    if "group" in r:
        return "group"
    if r == "final":
        return "final"
    if "friendly" in r:
        return "friendly"
    if "qualif" in r:
        return "qualifier"
    return "knockout"


def _infer_group_name(round_name: Any) -> Optional[str]:
    """Extract group letter (A–H) when present in round text; else NULL."""
    if round_name is None or (isinstance(round_name, float) and pd.isna(round_name)):
        return None
    m = GROUP_LETTER_RE.search(str(round_name))
    return m.group(1).upper() if m else None


def _is_neutral(venue: Any) -> bool:
    """Most WC/Euro games list '(Neutral Site)' in the venue column."""
    if venue is None or (isinstance(venue, float) and pd.isna(venue)):
        return True
    return "neutral" in str(venue).lower()


def _sample_weight(stage: str, default: float) -> float:
    """
    Down-weight friendlies and qualifiers for training (see DATA_CONTRACT.md).

    Tournament knockout/group rows use the competition default (usually 1.0).
    """
    if stage == "friendly":
        return 0.3
    if stage == "qualifier":
        return 0.5
    return default


@dataclass
class TeamMapper:
    """
    Resolve FBref display names (e.g. 'Korea Republic') to FIFA codes (e.g. 'KOR').

    Loads team_map_intl.csv on top of DEFAULT_TEAM_CODES.
    """

    alias_to_id: Dict[str, str]

    @classmethod
    def load(cls, csv_path: Path) -> "TeamMapper":
        """Build lookup: start with built-ins, then overlay CSV aliases."""
        mapping = dict(DEFAULT_TEAM_CODES)
        if csv_path.exists():
            df = pd.read_csv(csv_path)
            for _, row in df.iterrows():
                alias = str(row["alias"]).strip()
                code = str(row["team_id"]).strip().upper()
                if alias and code:
                    mapping[alias] = code
        return cls(mapping)

    def resolve(self, name: str) -> str:
        """Return FIFA code or raise KeyError so caller can collect unmapped names."""
        key = name.strip()
        if key in self.alias_to_id:
            return self.alias_to_id[key]
        raise KeyError(key)


class FBrefInternationalImporter:
    """
    Main entry point for WC-03 ingest.

    Typical usage:
        importer = FBrefInternationalImporter(project_root)
        importer.download()      # step 01 — populate .soccerdata cache
        importer.normalize()     # step 02 — write match_logs_normalized.csv
    """

    def __init__(
        self,
        project_root: Path,
        *,
        team_map_path: Optional[Path] = None,
        raw_dir: Optional[Path] = None,
        headless: bool = False,
        sleep_seconds: float = 5.0,
    ):
        self.project_root = Path(project_root)
        # Side effect: writes league_dict.json and sets SOCCERDATA_DIR
        self.sd_dir = setup_soccerdata_env(self.project_root)
        self.team_map_path = team_map_path or (
            self.project_root / "data-pipeline" / "data" / "static" / "team_map_intl.csv"
        )
        self.raw_dir = raw_dir or (self.project_root / "data-pipeline" / "data" / "raw")
        # headless=False is often more reliable against FBref bot checks (WC-01b)
        self.headless = headless
        # Polite delay between competitions when scraping live
        self.sleep_seconds = sleep_seconds
        self._team_mapper: Optional[TeamMapper] = None

    @property
    def team_mapper(self) -> TeamMapper:
        """Lazy-load team map so import-time does not require CSV on disk."""
        if self._team_mapper is None:
            self._team_mapper = TeamMapper.load(self.team_map_path)
        return self._team_mapper

    def list_competitions(self) -> List[str]:
        """Return competition_id slugs configured in COMPETITIONS."""
        return list(COMPETITIONS.keys())

    def _import_soccerdata(self):
        """
        Deferred import: soccerdata must load AFTER setup_soccerdata_env().

        Importing at module top level would read the wrong league_dict path.
        """
        import soccerdata as sd  # noqa: WPS433

        return sd

    def download(
        self,
        competition_ids: Optional[Iterable[str]] = None,
        *,
        force: bool = False,
    ) -> Dict[str, int]:
        """
        Step 01: hit FBref (via Selenium) and cache schedule HTML under .soccerdata/.

        Args:
            competition_ids: Subset of COMPETITIONS keys, or None for all.
            force: Pass through to read_schedule(force_cache=True) for current seasons.

        Returns:
            Dict mapping competition_id → number of schedule rows cached.
        """
        sd = self._import_soccerdata()
        targets = self._resolve_competitions(competition_ids)
        results: Dict[str, int] = {}

        for comp_id, cfg in targets.items():
            league = cfg["league"]
            seasons = cfg["seasons"]
            total = 0
            logger.info("Downloading %s (%s) seasons=%s", comp_id, league, seasons)
            try:
                fb = sd.FBref(leagues=league, seasons=seasons, headless=self.headless)
                # Triggers scrape on cache miss; stores HTML in .soccerdata/data/FBref/
                df = fb.read_schedule(force_cache=force)
                total = len(df)
                results[comp_id] = total
                logger.info("[OK] %s: %s schedule rows cached", comp_id, total)
            except Exception as e:
                logger.error("[FAIL] %s: %s", comp_id, e)
                results[comp_id] = 0
            # Be polite to FBref when downloading multiple comps
            time.sleep(self.sleep_seconds)

        return results

    def normalize(
        self,
        competition_ids: Optional[Iterable[str]] = None,
        *,
        force_cache: bool = True,
    ) -> Dict[str, int]:
        """
        Step 02: read cached schedules and write contract CSVs.

        Args:
            force_cache: Prefer disk cache (True = do not re-scrape current season).

        Returns:
            Dict mapping output file path → row count written.

        Raises:
            ValueError: if any team name cannot be mapped to a FIFA code.
        """
        sd = self._import_soccerdata()
        targets = self._resolve_competitions(competition_ids)
        written: Dict[str, int] = {}
        unmapped: set[str] = set()

        for comp_id, cfg in targets.items():
            league = cfg["league"]
            seasons = cfg["seasons"]
            default_weight = cfg.get("default_weight", 1.0)

            try:
                fb = sd.FBref(leagues=league, seasons=seasons, headless=self.headless)
                schedule = fb.read_schedule(force_cache=force_cache)
            except Exception as e:
                logger.error("Failed to read schedule for %s: %s", comp_id, e)
                continue

            if schedule.empty:
                logger.warning("No schedule rows for %s", comp_id)
                continue

            # Multi-index (league, season, game) → flat columns for iteration
            schedule = schedule.reset_index()

            # One output file per tournament year (season_id = "2018", "2022", …)
            for season_val, season_df in schedule.groupby("season"):
                season_id = str(int(season_val))
                rows: List[Dict[str, Any]] = []

                for _, match in season_df.iterrows():
                    try:
                        # Each match → 2 rows (home perspective + away perspective)
                        pair = self._match_to_rows(
                            match,
                            competition_id=comp_id,
                            season_id=season_id,
                            default_weight=default_weight,
                        )
                        rows.extend(pair)
                    except KeyError as e:
                        # Collect all unmapped names before failing (better error message)
                        unmapped.add(str(e).strip("'\""))
                    except Exception as e:
                        logger.warning(
                            "Skipping match %s vs %s: %s",
                            match.get("home_team"),
                            match.get("away_team"),
                            e,
                        )

                if not rows:
                    logger.warning("No normalized rows for %s/%s", comp_id, season_id)
                    continue

                out_dir = self.raw_dir / comp_id / season_id
                out_dir.mkdir(parents=True, exist_ok=True)
                out_path = out_dir / "match_logs_normalized.csv"
                out_df = pd.DataFrame(rows).sort_values(["match_date", "match_id", "team_id"])
                out_df.to_csv(out_path, index=False, encoding="utf-8")
                written[str(out_path)] = len(rows)
                logger.info("Wrote %s (%s rows)", out_path, len(rows))

        if unmapped:
            logger.error(
                "Unmapped team names (%s). Add aliases to %s",
                sorted(unmapped),
                self.team_map_path,
            )
            raise ValueError(f"Unmapped teams: {sorted(unmapped)}")

        return written

    def _resolve_competitions(
        self, competition_ids: Optional[Iterable[str]]
    ) -> Dict[str, Dict[str, Any]]:
        """Validate CLI --competition values against COMPETITIONS registry."""
        if competition_ids is None:
            return dict(COMPETITIONS)
        out = {}
        for cid in competition_ids:
            if cid not in COMPETITIONS:
                raise ValueError(f"Unknown competition_id {cid!r}. Valid: {list(COMPETITIONS)}")
            out[cid] = COMPETITIONS[cid]
        return out

    def _match_to_rows(
        self,
        match: pd.Series,
        *,
        competition_id: str,
        season_id: str,
        default_weight: float,
    ) -> List[Dict[str, Any]]:
        """
        Convert one FBref schedule row into two contract rows (dual-row format).

        match_id format: {yyyymmdd}_{home_fifa}_{away_fifa} (lowercase codes).
        """
        home_name = str(match["home_team"]).strip()
        away_name = str(match["away_team"]).strip()
        home_id = self.team_mapper.resolve(home_name)
        away_id = self.team_mapper.resolve(away_name)

        match_date = pd.to_datetime(match["date"], errors="coerce")
        if pd.isna(match_date):
            raise ValueError(f"Invalid date for {home_name} vs {away_name}")
        date_str = match_date.strftime("%Y-%m-%d")
        date_compact = date_str.replace("-", "")

        # Stable ID: date + designated home/away FIFA codes (see DATA_CONTRACT.md)
        match_id = f"{date_compact}_{home_id.lower()}_{away_id.lower()}"

        home_goals, away_goals, home_xg, away_xg = _parse_score(match.get("score"))
        if home_goals is None or away_goals is None:
            raise ValueError(f"Missing score for {home_name} vs {away_name}: {match.get('score')!r}")

        stage = _infer_stage(match.get("round"))
        group_name = _infer_group_name(match.get("round"))
        neutral = _is_neutral(match.get("venue"))
        weight = _sample_weight(stage, default_weight)

        matchday = match.get("week")
        if pd.isna(matchday):
            matchday = None
        else:
            matchday = int(matchday)

        source_key = match.get("game_id")
        if pd.isna(source_key):
            source_key = None

        # Shared columns — identical on both rows except team-specific fields below
        base = {
            "match_id": match_id,
            "competition_id": competition_id,
            "season_id": season_id,
            "competition_stage": stage,
            "group_name": group_name,
            "matchday": matchday,
            "match_date": date_str,
            "is_neutral_venue": neutral,
            "sample_weight": weight,
            "source": "fbref",
            "source_match_key": source_key,
            # Shot/xG detail columns reserved for future read_team_match_stats() merge
            "xg_for": None,
            "xg_against": None,
            "shots_for": None,
            "shots_against": None,
            "shots_on_target_for": None,
            "shots_on_target_against": None,
            "corners_for": None,
            "corners_against": None,
            "fouls_for": None,
            "fouls_against": None,
            "yellow_cards": None,
            "red_cards": None,
        }

        if home_xg is not None and away_xg is not None:
            base_home_xg, base_away_xg = home_xg, away_xg
        else:
            base_home_xg, base_away_xg = None, None

        # Row 1: home team perspective (venue = Home)
        home_row = {
            **base,
            "team_id": home_id,
            "opponent_id": away_id,
            "venue": "Home",
            "goals_for": home_goals,
            "goals_against": away_goals,
            "result": _determine_result(home_goals, away_goals),
            "xg_for": base_home_xg,
            "xg_against": base_away_xg,
        }
        # Row 2: away team perspective (goals swapped)
        away_row = {
            **base,
            "team_id": away_id,
            "opponent_id": home_id,
            "venue": "Away",
            "goals_for": away_goals,
            "goals_against": home_goals,
            "result": _determine_result(away_goals, home_goals),
            "xg_for": base_away_xg,
            "xg_against": base_home_xg,
        }
        return [home_row, away_row]
