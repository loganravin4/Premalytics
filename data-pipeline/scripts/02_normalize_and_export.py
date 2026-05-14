"""
Normalize EPL match data and export to data-pipeline/data/raw/.

WHAT THIS SCRIPT DOES:
  1. Loads all raw CSVs from data-pipeline/data/static/football_data_co_uk/
  2. Normalizes column names, team names, dates, and results
  3. Optionally merges xG values from data-pipeline/data/static/xg/understat_epl_xg.csv
  4. Writes one normalized CSV per team per season to:
       data-pipeline/data/raw/{season}/{team_slug}/match_logs_normalized.csv
"""

import argparse
import logging
import re
import sys
from pathlib import Path

import pandas as pd

# Add the data-pipeline directory to Python's module search path so we can
# import from soccer/importers/ regardless of where the script is run from
SCRIPT_DIR = Path(__file__).resolve().parent  # .../data-pipeline/scripts/
PIPELINE_DIR = SCRIPT_DIR.parent  # .../data-pipeline/
PROJECT_ROOT = PIPELINE_DIR.parent  # .../premalytics/

# Insert the data-pipeline directory at the front of sys.path
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

# Import from soccer/importers/
from soccer.importers import FootballDataImporter, XGImporter

# Set up logging to print to the console with timestamps and log level labels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

STATIC_DIR = PIPELINE_DIR / "data" / "static" / "football_data_co_uk"
XG_CSV_PATH = PIPELINE_DIR / "data" / "static" / "xg" / "understat_epl_xg.csv"
RAW_DATA_DIR = PIPELINE_DIR / "data" / "raw"


def slugify(name: str) -> str:
    """
    Convert a team name to a filesystem-safe directory slug.
    """
    name = name.lower()                          # Lowercase everything
    name = re.sub(r"[^a-z0-9\s]", "", name)    # Strip non-alphanumeric characters
    name = re.sub(r"\s+", "_", name.strip())   # Replace whitespace runs with underscore
    return name


def export_rows_to_csv(rows: list) -> dict:
    """
    Write normalized match rows to per-team-per-season CSV files.

    For each unique (season_id, team_id) combination in the rows, writes
    a CSV to data/raw/{season}/{team_slug}/match_logs_normalized.csv
    """
    if not rows:
        logger.warning("No rows provided — nothing to export")
        return {"files_written": 0, "errors": 0}

    df = pd.DataFrame(rows)    # Convert list of dicts to a DataFrame for grouping

    files_written = 0   # Track successful writes
    errors = 0          # Track failures

    # Group the rows by season + team so each group = one CSV file
    for (season_id, team_id), group_df in df.groupby(["season_id", "team_id"]):
        # Build the output directory path
        team_slug = slugify(str(team_id))                         # "Arsenal" → "arsenal"
        output_dir = RAW_DATA_DIR / str(season_id) / team_slug    # data/raw/2023-2024/arsenal/
        output_dir.mkdir(parents=True, exist_ok=True)             # Create dirs if needed

        # Fixed filename — always the same so re-runs just overwrite
        output_path = output_dir / "match_logs_normalized.csv"

        try:
            # Sort by date so the CSV is in chronological order
            group_df = group_df.sort_values("match_date")
            group_df.to_csv(output_path, index=False, encoding="utf-8")
            files_written += 1
            logger.info(f"[WRITE] {season_id}/{team_slug}: {len(group_df)} rows → {output_path.name}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to write {season_id}/{team_slug}: {e}")
            errors += 1

    return {"files_written": files_written, "errors": errors}


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Normalize EPL match data and export CSVs"
    )
    parser.add_argument(
        "--season",
        action="append",
        default=[],
        help="Season key like 2025-26 (repeatable). Default: all seasons.",
    )
    parser.add_argument(
        "--current",
        action="store_true",
        help="Process only the current season (default: 2025-26).",
    )
    args = parser.parse_args()

    # Print basic context to the console
    print()
    print("PREMALYTICS STEP 2: NORMALIZE AND EXPORT TO CSV")
    print(f"Input:  {STATIC_DIR}")
    print(f"xG CSV: {XG_CSV_PATH}")
    print(f"Output: {RAW_DATA_DIR}")
    print()

    # Load all downloaded CSVs and normalize them
    logger.info("Loading and normalizing match data from football-data.co.uk CSVs...")

    importer = FootballDataImporter(static_dir=STATIC_DIR)

    if args.current:
        seasons = ["2025-26"]
    elif args.season:
        seasons = args.season
    else:
        seasons = importer.list_seasons()

    try:
        # Returns list of normalized match row dicts
        rows = importer.load_seasons(seasons)
    except Exception as e:
        logger.error(f"Failed to load match data: {e}")
        sys.exit(1)

    if not rows:
        logger.error("No match rows loaded — ensure 01_download_match_data.py ran successfully")
        sys.exit(1)

    logger.info(f"Loaded {len(rows)} total team-match rows across all seasons")

    # Merge in xG data (optional — won't fail if CSV not present)
    logger.info("Attempting to merge xG data...")

    xg_importer = XGImporter(xg_csv_path=XG_CSV_PATH)
    rows = xg_importer.merge_xg_into_rows(rows)   # Modifies rows in-place

    # Count how many rows got xG values (useful for verifying the merge worked)
    xg_count = sum(1 for r in rows if r.get("xg_for") is not None)
    logger.info(f"xG enriched: {xg_count}/{len(rows)} rows have xG values")

    # Write normalized CSVs to data/raw/{season}/{team}/
    logger.info("Writing normalized CSVs to data/raw/...")

    summary = export_rows_to_csv(rows)

    # Print final summary
    print()
    print("EXPORT SUMMARY")
    print(f"Total team-match rows: {len(rows)}")
    print(f"Rows with xG values:   {xg_count}")
    print(f"CSV files written:     {summary['files_written']}")
    print(f"Errors:                {summary['errors']}")
    print()
    print(f"Output location: {RAW_DATA_DIR}")
    print()
    print("Next step:")
    print("  python data-pipeline/scripts/03_load_to_db.py")

    if summary["errors"] > 0:
        sys.exit(1)   # Non-zero exit if any files failed to write

if __name__ == "__main__":
    main()
