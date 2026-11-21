"""FBref international match ingest via soccerdata: cache schedules, then write dual-row match_logs_normalized.csv per tournament year."""

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


COMPETITIONS: Dict[str, Dict[str, Any]] = {
    "fifa_world_cup": {
        "league": "INT-World Cup",
        "seasons": [2018, 2022],
        "default_weight": 1.0,
    },
    "uefa_euro": {
        "league": "INT-European Championship",
        # Euro 2020 was played in 2021 but keeps season_id "2020"
        "seasons": [2020, 2024],
        "default_weight": 1.0,
    },
}

# Not built into soccerdata; WC-01b must confirm each one scrapes before it joins COMPETITIONS
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


# FBref scores use Unicode en dashes, not ASCII hyphens
SCORE_SPLIT_RE = re.compile(r"[\u2013\u2014\-–]+")

# Shootout scores look like "(3) 1–1 (4)"; only the regulation goals count
PENALTY_SCORE_RE = re.compile(
    r"\(\d+\)\s*(\d+)\s*[\u2013\u2014\-–]\s*(\d+)\s*\(\d+\)"
)

GROUP_LETTER_RE = re.compile(r"Group\s+([A-H])\b", re.I)

# Fallback when team_map_intl.csv has no row; CSV aliases override these

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
    """Write league_dict.json and set SOCCERDATA_DIR; soccerdata reads both at import, so call this first."""
    sd_dir = project_root / ".soccerdata"
    config_dir = sd_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    (config_dir / "league_dict.json").write_text(
        json.dumps(CUSTOM_LEAGUES, indent=2), encoding="utf-8"
    )

    os.environ.setdefault("SOCCERDATA_DIR", str(sd_dir))
    return sd_dir


def _parse_score(score: Any) -> Tuple[Optional[int], Optional[int], Optional[float], Optional[float]]:
    """Parse FBref's score into (home_goals, away_goals, home_xg, away_xg); international schedules rarely carry xG."""
    if score is None or (isinstance(score, float) and pd.isna(score)):
        return None, None, None, None

    text = str(score).strip()
    if not text:
        return None, None, None, None

    pen = PENALTY_SCORE_RE.search(text)
    if pen:
        return int(pen.group(1)), int(pen.group(2)), None, None

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

    # Decimal values on some club tables are xG, not goals
    if a != int(a) or b != int(b):
        return None, None, float(a), float(b)
    return int(a), int(b), None, None


def _determine_result(goals_for: Optional[int], goals_against: Optional[int]) -> Optional[str]:
    if goals_for is None or goals_against is None:
        return None
    if goals_for > goals_against:
        return "W"
    if goals_for == goals_against:
        return "D"
    return "L"


def _infer_stage(round_name: Any) -> str:
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
    """Down-weight friendlies and qualifiers for training, per DATA_CONTRACT.md."""
    if stage == "friendly":
        return 0.3
    if stage == "qualifier":
        return 0.5
    return default


@dataclass
class TeamMapper:
    """Resolves FBref display names (e.g. 'Korea Republic') to FIFA codes, with team_map_intl.csv overriding built-ins."""

    alias_to_id: Dict[str, str]

    @classmethod
    def load(cls, csv_path: Path) -> "TeamMapper":
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
        # headless=False gets past FBref bot checks more often
        self.headless = headless
        self.sleep_seconds = sleep_seconds
        self._team_mapper: Optional[TeamMapper] = None

    @property
    def team_mapper(self) -> TeamMapper:
        """Lazy-load team map so import-time does not require CSV on disk."""
        if self._team_mapper is None:
            self._team_mapper = TeamMapper.load(self.team_map_path)
        return self._team_mapper

    def list_competitions(self) -> List[str]:
        return list(COMPETITIONS.keys())

    def _import_soccerdata(self):
        """Deferred so soccerdata loads only after setup_soccerdata_env() writes its league_dict."""
        import soccerdata as sd  # noqa: WPS433

        return sd

    def download(
        self,
        competition_ids: Optional[Iterable[str]] = None,
        *,
        force: bool = False,
    ) -> Dict[str, int]:
        """Step 01: scrape FBref schedules into the .soccerdata cache; returns rows cached per competition."""
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
                df = fb.read_schedule(force_cache=force)
                total = len(df)
                results[comp_id] = total
                logger.info("[OK] %s: %s schedule rows cached", comp_id, total)
            except Exception as e:
                logger.error("[FAIL] %s: %s", comp_id, e)
                results[comp_id] = 0
            time.sleep(self.sleep_seconds)

        return results

    def normalize(
        self,
        competition_ids: Optional[Iterable[str]] = None,
        *,
        force_cache: bool = True,
    ) -> Dict[str, int]:
        """Step 02: write contract CSVs from cached schedules; raises ValueError listing every unmapped team."""
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

            schedule = schedule.reset_index()

            for season_val, season_df in schedule.groupby("season"):
                season_id = str(int(season_val))
                rows: List[Dict[str, Any]] = []

                for _, match in season_df.iterrows():
                    try:
                        pair = self._match_to_rows(
                            match,
                            competition_id=comp_id,
                            season_id=season_id,
                            default_weight=default_weight,
                        )
                        rows.extend(pair)
                    except KeyError as e:
                        # Collect every unmapped name before failing so one run reports them all
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
        home_name = str(match["home_team"]).strip()
        away_name = str(match["away_team"]).strip()
        home_id = self.team_mapper.resolve(home_name)
        away_id = self.team_mapper.resolve(away_name)

        match_date = pd.to_datetime(match["date"], errors="coerce")
        if pd.isna(match_date):
            raise ValueError(f"Invalid date for {home_name} vs {away_name}")
        date_str = match_date.strftime("%Y-%m-%d")
        date_compact = date_str.replace("-", "")

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
            # Reserved for a future read_team_match_stats() merge
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
