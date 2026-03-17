"""
Download raw match CSVs from football-data.co.uk

WHAT THIS SCRIPT DOES:
  1. Creates data-pipeline/data/static/football_data_co_uk/ if it doesn't exist
  2. Downloads one CSV per season from football-data.co.uk
  3. Saves each file as e.g. "2023-24_E0.csv" in the static directory
  4. Skips seasons already downloaded (unless --force is used)
"""

import sys                    # For sys.exit() and sys.path modification
import logging                # For structured console output
import argparse               # For parsing --force command-line flag
from pathlib import Path      # Cross-platform path handling

# Add the data-pipeline directory to Python's module search path so we can 
# import from soccer/importers/ regardless of where the script is run from
SCRIPT_DIR   = Path(__file__).resolve().parent          # .../data-pipeline/scripts/
PIPELINE_DIR = SCRIPT_DIR.parent                        # .../data-pipeline/
PROJECT_ROOT = PIPELINE_DIR.parent                      # .../premalytics/

# Insert the data-pipeline directory at the front of sys.path
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

# Import from soccer/importers/
from soccer.importers import FootballDataImporter

# Set up logging to print to the console with timestamps and log level labels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],   # Print to terminal
)
logger = logging.getLogger(__name__)    # Logger for this script

# Where to store the downloaded CSV files
STATIC_DIR = PIPELINE_DIR / "data" / "static" / "football_data_co_uk"


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Download Premier League match CSVs from football-data.co.uk"
    )
    parser.add_argument(
        "--force",
        action="store_true",          # Flag — no value needed, just presence
        help="Re-download all seasons even if already cached on disk",
    )
    args = parser.parse_args()

    print()
    print("PREMALYTICS STEP 1: DOWNLOAD MATCH DATA")
    print(f"Source: football-data.co.uk (English Premier League)")
    print(f"Target: {STATIC_DIR}")
    print(
        f"Mode:   {'Force re-download all' if args.force else 'Skip already downloaded'}"
    )
    print()

    # Run the download
    importer = FootballDataImporter(static_dir=STATIC_DIR)   # Create importer instance

    try:
        # download_all_seasons() returns a dict: {short_season: Path}
        results = importer.download_all_seasons(force=args.force)
    except Exception as e:
        logger.error(f"Download failed with unexpected error: {e}")
        sys.exit(1)    # Exit with error code 1 so scripts/CI can detect failure

    # Print summary
    print()
    print("DOWNLOAD SUMMARY")

    success_count = 0
    for short_season, path in results.items():
        if path and Path(path).exists():
            size_kb = Path(path).stat().st_size // 1024     # File size in KB
            print(f"- {short_season}: {path.name} ({size_kb} KB)")
            success_count += 1
        else:
            print(f"- {short_season}: FAILED (see errors above)")

    print()
    print(f"{success_count}/{len(results)} seasons downloaded successfully")
    print()
    print("Next step:")
    print("  python data-pipeline/scripts/02_normalize_and_export.py")

    # Exit with error code if any season failed
    if success_count < len(results):
        sys.exit(1)

if __name__ == "__main__":
    main()
