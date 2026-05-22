"""
=============================================================================
PREMALYTICS PIPELINE — STEP 1: DOWNLOAD INTERNATIONAL MATCH DATA
=============================================================================

WHAT THIS SCRIPT DOES:
  1. Configures soccerdata to cache under {repo}/.soccerdata/
  2. Calls FBref via soccerdata (Selenium + Chrome when cache is cold)
  3. Stores schedule HTML for each competition/season in the cache
  4. Does NOT write match_logs_normalized.csv — that is step 02

REQUIREMENTS:
  - Python 3.12 venv at data-pipeline/venv (see docs/VENV.md)
  - soccerdata >= 1.9 (older versions get FBref 403)
  - Google Chrome installed for live scrapes

NEXT STEP:
  python data-pipeline/scripts/02_normalize_and_export.py
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Resolve paths relative to this file so the script works from any cwd
SCRIPT_DIR = Path(__file__).resolve().parent          # .../data-pipeline/scripts/
PIPELINE_DIR = SCRIPT_DIR.parent                      # .../data-pipeline/
PROJECT_ROOT = PIPELINE_DIR.parent                    # .../premalytics/

# Allow `from soccer.importers import ...` without installing the package
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from soccer.importers import FBrefInternationalImporter, COMPETITIONS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download international match schedules (soccerdata → FBref)"
    )
    parser.add_argument(
        "--competition",
        action="append",
        default=[],
        help=f"Competition slug (repeatable). Default: all ({', '.join(COMPETITIONS)}).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force soccerdata to refresh cache for current seasons",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless (default: False — often avoids FBref blocks)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=5.0,
        help="Seconds between competition downloads (default: 5)",
    )
    args = parser.parse_args()

    # Empty list from argparse → download all competitions in COMPETITIONS
    comp_ids = args.competition or None

    print()
    print("PREMALYTICS STEP 1: DOWNLOAD INTERNATIONAL MATCH DATA")
    print("Source: soccerdata → FBref")
    print(f"Cache:  {PROJECT_ROOT / '.soccerdata'}")
    print(f"Comps:  {comp_ids or list(COMPETITIONS.keys())}")
    print(f"Mode:   {'Force refresh cache' if args.force else 'Use cache when possible'}")
    print()

    importer = FBrefInternationalImporter(
        PROJECT_ROOT,
        headless=args.headless,
        sleep_seconds=args.sleep,
    )

    try:
        results = importer.download(comp_ids, force=args.force)
    except Exception as e:
        logger.error("Download failed: %s", e)
        sys.exit(1)

    print()
    print("DOWNLOAD SUMMARY")
    ok = 0
    for comp_id, rows in results.items():
        status = "OK" if rows > 0 else "FAIL"
        print(f"  [{status}] {comp_id}: {rows} schedule rows")
        if rows > 0:
            ok += 1
    print()
    print(f"{ok}/{len(results)} competitions cached successfully")
    print()
    print("Next step:")
    print("  python data-pipeline/scripts/02_normalize_and_export.py")

    # Non-zero exit if any competition failed (for CI / shell chaining)
    if ok < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
