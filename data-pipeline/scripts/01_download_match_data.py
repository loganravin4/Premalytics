"""Step 01: cache FBref international schedules under .soccerdata/ via soccerdata; step 02 normalizes them.

Needs soccerdata >= 1.9 (older versions get FBref 403) and Chrome for live scrapes.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = PIPELINE_DIR.parent

# soccer/ isn't an installed package
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

    comp_ids = args.competition or None

    print()
    print("NEUTRAL GROUND STEP 1: DOWNLOAD INTERNATIONAL MATCH DATA")
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

    if ok < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
