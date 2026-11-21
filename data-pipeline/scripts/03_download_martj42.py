"""Cache the CC0 martj42/international_results CSVs under data/raw/martj42/ for 04_normalize_martj42.py."""

from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

import pandas as pd
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = PIPELINE_DIR.parent

RAW_BASE = "https://raw.githubusercontent.com/martj42/international_results/master"
OUT_DIR = PIPELINE_DIR / "data" / "raw" / "martj42"

FILES = ["results.csv", "shootouts.csv", "goalscorers.csv"]

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
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:  # pragma: no cover
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
