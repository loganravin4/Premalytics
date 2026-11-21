"""Step 02: normalize cached FBref schedules into data/raw/{competition}/{season}/match_logs_normalized.csv.

Each fixture becomes two rows (home and away perspective), with teams mapped to FIFA codes via team_map_intl.csv.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = PIPELINE_DIR.parent
RAW_DATA_DIR = PIPELINE_DIR / "data" / "raw"

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
        description="Normalize international match data to contract CSVs"
    )
    parser.add_argument(
        "--competition",
        action="append",
        default=[],
        help=f"Competition slug (repeatable). Default: all ({', '.join(COMPETITIONS)}).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Chrome headless only if cache miss forces a live scrape",
    )
    args = parser.parse_args()

    comp_ids = args.competition or None

    print()
    print("NEUTRAL GROUND STEP 2: NORMALIZE AND EXPORT TO CSV")
    print(f"Input:  {PROJECT_ROOT / '.soccerdata'} (soccerdata cache)")
    print(f"Output: {RAW_DATA_DIR}")
    print(f"Comps:  {comp_ids or list(COMPETITIONS.keys())}")
    print()

    importer = FBrefInternationalImporter(PROJECT_ROOT, headless=args.headless)

    try:
        # Step 01 already cached the HTML, so skip Chrome
        written = importer.normalize(comp_ids, force_cache=True)
    except ValueError as e:
        # Usually an unmapped team name; add it to team_map_intl.csv
        logger.error("%s", e)
        sys.exit(1)
    except Exception as e:
        logger.error("Normalize failed: %s", e)
        sys.exit(1)

    if not written:
        logger.error(
            "No CSVs written — run 01_download_match_data.py first or check cache under .soccerdata/"
        )
        sys.exit(1)

    total_rows = sum(written.values())
    print()
    print("EXPORT SUMMARY")
    print(f"CSV files written: {len(written)}")
    print(f"Total team-match rows: {total_rows}")
    for path, n in sorted(written.items()):
        print(f"  - {Path(path).relative_to(PROJECT_ROOT)} ({n} rows)")
    print()
    print(f"Output location: {RAW_DATA_DIR}")


if __name__ == "__main__":
    main()
