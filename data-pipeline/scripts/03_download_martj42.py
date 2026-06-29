"""
03_download_martj42.py — cache the martj42/international_results dataset.

Downloads the three CSVs from the martj42/international_results GitHub repo
(CC0 / public domain) into a dedicated raw source directory. This dataset is
a *supplement* to the FBref competition-split files: it carries ~10,000+
post-1990 international results that 04_normalize_martj42.py turns into a
single contract CSV.

Source: https://github.com/martj42/international_results
License: CC0 (public domain — no attribution required)

Files (downloaded from the master branch raw URLs):
    results.csv      — date, home_team, away_team, home_score, away_score,
                       tournament, city, country, neutral
    shootouts.csv    — date, home_team, away_team, winner, first_shooter
    goalscorers.csv  — date, home_team, away_team, team, scorer, own_goal, penalty

Output:
    data-pipeline/data/raw/martj42/results.csv
    data-pipeline/data/raw/martj42/shootouts.csv
    data-pipeline/data/raw/martj42/goalscorers.csv

Usage:
    python data-pipeline/scripts/03_download_martj42.py [--force]
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

import pandas as pd
import requests

SCRIPT_DIR = Path(__file__).resolve().parent          # .../data-pipeline/scripts/
PIPELINE_DIR = SCRIPT_DIR.parent                      # .../data-pipeline/
PROJECT_ROOT = PIPELINE_DIR.parent                    # .../premalytics/

RAW_BASE = "https://raw.githubusercontent.com/martj42/international_results/master"
OUT_DIR = PIPELINE_DIR / "data" / "raw" / "martj42"

FILES = ["results.csv", "shootouts.csv", "goalscorers.csv"]

# Polite, explicit UA — GitHub raw is fine with defaults, but be a good citizen.
HEADERS = {"User-Agent": "premalytics-data-pipeline (martj42 ingest)"}
REQUEST_TIMEOUT = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _download(filename: str, dest: Path, force: bool) -> bytes | None:
    """
    Fetch one CSV unless it is already cached. Returns the file's bytes (read
    from cache or freshly downloaded) so the caller can log row/date stats.
    """
    url = f"{RAW_BASE}/{filename}"
    if dest.exists() and not force:
        logger.info("CACHED  %s — already on disk (use --force to re-download)", dest.name)
        return dest.read_bytes()

    logger.info("GET     %s", url)
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    logger.info("SAVED   %s (%d bytes)", dest, len(resp.content))
    return resp.content


def _log_stats(filename: str, content: bytes) -> None:
    """Log row count, and (for results.csv) the date range."""
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:  # pragma: no cover — corrupt download
        logger.warning("Could not parse %s for stats: %s", filename, e)
        return

    if filename == "results.csv" and "date" in df.columns:
        dates = pd.to_datetime(df["date"], errors="coerce").dropna()
        date_range = f"{dates.min().date()} to {dates.max().date()}" if len(dates) else "n/a"
        logger.info("  %s: %d rows, date range %s", filename, len(df), date_range)
    else:
        logger.info("  %s: %d rows", filename, len(df))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download + cache the martj42/international_results CSVs"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download every file even if it is already cached",
    )
    args = parser.parse_args()

    logger.info("martj42/international_results ingest (CC0)")
    logger.info("Output dir: %s", OUT_DIR)

    failures = 0
    for filename in FILES:
        dest = OUT_DIR / filename
        try:
            content = _download(filename, dest, force=args.force)
            if content is not None:
                _log_stats(filename, content)
        except Exception as e:
            logger.error("FAIL    %s — %s: %s", filename, type(e).__name__, e)
            failures += 1

    logger.info("=" * 60)
    if failures:
        logger.error("Download finished with %d failure(s)", failures)
        sys.exit(1)
    logger.info("All %d files present in %s", len(FILES), OUT_DIR)
    logger.info("Next: python data-pipeline/scripts/04_normalize_martj42.py")


if __name__ == "__main__":
    main()
