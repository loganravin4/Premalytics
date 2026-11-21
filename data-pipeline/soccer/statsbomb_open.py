"""StatsBomb open-data access shared by the shot and penalty exporters; events are cached as gzip so each match downloads once."""

from __future__ import annotations

import gzip
import json
import logging
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("statsbomb_open")

RAW_BASE = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
MATCHES_URL = RAW_BASE + "/matches/{comp}/{season}.json"
EVENTS_URL = RAW_BASE + "/events/{mid}.json"

PIPELINE_DIR = Path(__file__).resolve().parents[1]
CACHE_DIR = PIPELINE_DIR / "data" / "raw" / "statsbomb_cache"


@dataclass(frozen=True)
class Competition:
    sb_competition: int
    sb_season: int
    competition_id: str
    season_id: str
    file_slug: str
    gender: str

    @property
    def key(self) -> str:
        return f"{self.competition_id}_{self.season_id}"


COMPETITIONS: list[Competition] = [
    Competition(43, 3, "fifa_world_cup", "2018", "wc", "male"),
    Competition(55, 43, "uefa_euro", "2020", "euro", "male"),
    Competition(43, 106, "fifa_world_cup", "2022", "wc", "male"),
    Competition(1267, 107, "afcon", "2023", "afcon", "male"),
    Competition(55, 282, "uefa_euro", "2024", "euro", "male"),
    Competition(223, 282, "copa_america", "2024", "copa", "male"),
    # Historic World Cups: only a handful of matches each, mostly finals
    Competition(43, 269, "fifa_world_cup", "1958", "wc", "male"),
    Competition(43, 270, "fifa_world_cup", "1962", "wc", "male"),
    Competition(43, 272, "fifa_world_cup", "1970", "wc", "male"),
    Competition(43, 51, "fifa_world_cup", "1974", "wc", "male"),
    Competition(43, 54, "fifa_world_cup", "1986", "wc", "male"),
    Competition(43, 55, "fifa_world_cup", "1990", "wc", "male"),
    Competition(72, 30, "womens_world_cup", "2019", "wwc", "female"),
    Competition(53, 106, "womens_euro", "2022", "weuro", "female"),
    Competition(72, 107, "womens_world_cup", "2023", "wwc", "female"),
    Competition(53, 315, "womens_euro", "2025", "weuro", "female"),
]


def fetch_json(url: str, retries: int = 4, sleep: float = 2.0):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "statsbomb-open-reader/1.0"})
            with urllib.request.urlopen(req, timeout=90) as resp:
                return json.loads(resp.read())
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.debug("fetch attempt %d failed for %s: %s", attempt, url, e)
            time.sleep(sleep * attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {last_err}")


def _cached(path: Path, url: str):
    if path.exists():
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    data = fetch_json(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(path)
    return data


def get_matches(comp: Competition) -> list[dict]:
    path = CACHE_DIR / "matches" / f"{comp.sb_competition}_{comp.sb_season}.json.gz"
    return _cached(path, MATCHES_URL.format(comp=comp.sb_competition, season=comp.sb_season))


def get_events(match_id: int) -> list[dict]:
    path = CACHE_DIR / "events" / f"{match_id}.json.gz"
    return _cached(path, EVENTS_URL.format(mid=match_id))


def prefetch_events(match_ids: list[int], workers: int = 8) -> list[int]:
    """Download events for many matches in parallel and return the ids that failed."""
    failed: list[int] = []

    def _one(mid: int):
        try:
            get_events(mid)
        except Exception as e:  # noqa: BLE001
            logger.warning("events %s failed: %s", mid, e)
            failed.append(mid)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(_one, match_ids))
    return failed


# StatsBomb spellings the shared team map does not cover.
SB_TEAM_ALIASES = {
    "Cape Verde Islands": "Cape Verde",
    "Congo DR": "DR Congo",
    "China PR": "China",
}


def strip_womens_suffix(team_name: str) -> str:
    """Strip women's-team markers ('England Women's', 'WNT Finland') so the name maps to a FIFA code."""
    name = team_name.strip()
    if name.startswith("WNT "):
        name = name[4:]
    for suffix in (" Women's", " Women", " WNT", " W"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return SB_TEAM_ALIASES.get(name, name)
