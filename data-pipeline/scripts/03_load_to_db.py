"""
Load normalized match data from data-pipeline/data/raw/ into Postgres.

WHAT THIS SCRIPT DOES:
  1. Executes all SQL files in database/schema/ to create a clean schema
  2. Scans data-pipeline/data/raw/ for seasons and teams and inserts them into
     pl_data.seasons and pl_data.teams
  3. Reads all match_logs_normalized.csv files from data-pipeline/data/raw/ and
     inserts rows into pl_data.matches using INSERT ... ON CONFLICT DO NOTHING
"""

import sys                      # For sys.exit() and sys.path
import logging                  # Structured log output
from pathlib import Path        # Cross-platform file paths
from datetime import date       # For is_complete logic on current season
from typing import List, Dict   # Type hints

import pandas as pd             # For reading normalized CSVs
import psycopg2                 # PostgreSQL connection library
from psycopg2.extras import execute_values   # Efficient bulk insert helper

# Add the data-pipeline directory to Python's module search path so we can
# import shared modules regardless of where the script is run from
SCRIPT_DIR = Path(__file__).resolve().parent  # .../data-pipeline/scripts/
PIPELINE_DIR = SCRIPT_DIR.parent  # .../data-pipeline/
PROJECT_ROOT = PIPELINE_DIR.parent  # .../premalytics/

# Insert the data-pipeline directory at the front of sys.path
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

# Add database/scripts/ to path for the shared config.py
DB_SCRIPTS_DIR = PROJECT_ROOT / "database" / "scripts"
if str(DB_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DB_SCRIPTS_DIR))

from config import get_db_config   # Loads DB credentials from .env file

# Set up logging to print to the console with timestamps and log level labels
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

SCHEMA_DIR = PROJECT_ROOT / "database" / "schema"
RAW_DATA_DIR = PIPELINE_DIR / "data" / "raw"

# SQL schema files in the order they must be executed
# Order matters because of foreign key constraints:
#   dimensions (teams/seasons) must exist before matches or player_stats
SCHEMA_FILES = [
    SCHEMA_DIR / "01_create_dimensions.sql",
    SCHEMA_DIR / "02_create_matches.sql",
    SCHEMA_DIR / "03_create_player_stats.sql",
    SCHEMA_DIR / "04_create_keeper_stats.sql",
    SCHEMA_DIR / "05_create_indexes.sql",
]

CURRENT_SEASON = "2025-2026"   # The in-progress season (marked is_complete=False)

# PHASE A: SCHEMA SETUP
def run_schema_setup(conn) -> None:
    """
    Execute all SQL schema files to create/recreate the database tables.

    This wipes and recreates all tables — intended for a clean setup.
    Each SQL file is run in a separate transaction so errors are isolated.
    """
    logger.info("PHASE A: Running schema setup SQL files")

    for sql_file in SCHEMA_FILES:
        if not sql_file.exists():
            # If a schema file is missing, skip with a warning (e.g. 05_indexes.sql may not exist)
            logger.warning(f"[SKIP] Schema file not found: {sql_file.name}")
            continue

        logger.info(f"[SQL] Executing {sql_file.name}...")

        # Read the entire SQL file as a string
        sql_content = sql_file.read_text(encoding="utf-8")

        try:
            with conn.cursor() as cur:
                cur.execute(sql_content)    # Execute the entire file as one command
            conn.commit()                   # Commit the transaction
            logger.info(f"[OK] {sql_file.name} executed successfully")
        except Exception as e:
            conn.rollback()                 # Roll back on error
            logger.error(f"[ERROR] {sql_file.name} failed: {e}")
            raise   # Re-raise so the caller knows schema setup failed

# PHASE B: DIMENSION DATA (teams + seasons)
def discover_dimension_data(raw_data_dir: Path) -> tuple:
    """
    Scan the data/raw/ directory to discover all unique seasons and team names.
    This determines what to insert into the teams and seasons dimension tables.
    """
    seasons = set()   # Unique season_ids like "2023-2024"
    teams   = set()   # Unique team names like "Arsenal", "Manchester City"

    # Walk the directory structure: data/raw/{season}/{team}/
    for season_dir in sorted(raw_data_dir.iterdir()):
        if not season_dir.is_dir():
            continue   # Skip files at this level (shouldn't exist but be safe)

        season_id = season_dir.name   # e.g. "2023-2024"

        # Only process directories that look like valid season IDs
        if not season_id[0].isdigit():
            continue   # Skip "api_football", "api_soccer" subdirs from old scraper

        for team_dir in sorted(season_dir.iterdir()):
            if not team_dir.is_dir():
                continue   # Skip files at this level

            # Look for our normalized CSV file in this team directory
            csv_path = team_dir / "match_logs_normalized.csv"
            if not csv_path.exists():
                continue   # Skip team dirs that have no normalized CSV yet

            # Read just enough to get the team name (first data row)
            try:
                df = pd.read_csv(csv_path, nrows=1)   # Only read one row — fast
                if "team_id" in df.columns and len(df) > 0:
                    team_name = str(df["team_id"].iloc[0]).strip()
                    if team_name:
                        teams.add(team_name)
                        seasons.add(season_id)
            except Exception as e:
                logger.warning(f"Could not read {csv_path}: {e}")

    logger.info(f"Discovered {len(seasons)} seasons and {len(teams)} unique teams")
    return seasons, teams


def insert_seasons(conn, seasons: set) -> None:
    """
    Insert season records into the pl_data.seasons dimension table.

    Uses INSERT ... ON CONFLICT DO NOTHING so it's safe to re-run.
    """
    logger.info(f"Inserting {len(seasons)} seasons into pl_data.seasons...")

    rows = []
    for season_id in sorted(seasons):
        # Parse the season_id to get start and end years
        # Format is always "YYYY-YYYY" e.g. "2023-2024"
        parts = season_id.split("-")
        if len(parts) != 2:
            logger.warning(f"Unexpected season_id format: {season_id!r} — skipping")
            continue

        start_year = int(parts[0])     # e.g. 2023
        end_year   = int(parts[1])     # e.g. 2024

        # Mark the current in-progress season as not complete
        is_complete = (season_id != CURRENT_SEASON)

        rows.append((
            season_id,      # season_id VARCHAR(20)
            start_year,     # start_year INTEGER
            end_year,       # end_year INTEGER
            is_complete,    # is_complete BOOLEAN
        ))

    if not rows:
        logger.warning("No valid season rows to insert")
        return

    sql = """
        INSERT INTO pl_data.seasons (season_id, start_year, end_year, is_complete)
        VALUES %s
        ON CONFLICT (season_id) DO NOTHING
    """

    with conn.cursor() as cur:
        execute_values(cur, sql, rows)   # Bulk insert all rows at once
    conn.commit()
    logger.info(f"[OK] Inserted/skipped {len(rows)} season rows")


def insert_teams(conn, teams: set) -> None:
    """
    Insert team records into the pl_data.teams dimension table.

    team_id and team_name are the same value (the normalized team name string).
    """
    logger.info(f"Inserting {len(teams)} teams into pl_data.teams...")

    rows = [
        (team_name, team_name)   # (team_id, team_name) — both are the same
        for team_name in sorted(teams)
    ]

    sql = """
        INSERT INTO pl_data.teams (team_id, team_name)
        VALUES %s
        ON CONFLICT (team_id) DO NOTHING
    """

    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()
    logger.info(f"[OK] Inserted/skipped {len(rows)} team rows")


# =============================================================================
# PHASE C: MATCH DATA
# =============================================================================

def load_all_normalized_csvs(raw_data_dir: Path) -> List[Dict]:
    """
    Read all match_logs_normalized.csv files from data/raw/ into a single list.

    Args:
        raw_data_dir: Path to data/raw/

    Returns:
        List of dicts, one per match-team row across all seasons and teams
    """
    all_rows = []

    for season_dir in sorted(raw_data_dir.iterdir()):
        if not season_dir.is_dir() or not season_dir.name[0].isdigit():
            continue   # Skip non-season directories

        for team_dir in sorted(season_dir.iterdir()):
            if not team_dir.is_dir():
                continue

            csv_path = team_dir / "match_logs_normalized.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path)
                all_rows.extend(df.to_dict(orient="records"))   # Convert rows to dicts
            except Exception as e:
                logger.warning(f"Could not read {csv_path}: {e}")

    logger.info(f"Loaded {len(all_rows)} total match rows from data/raw/")
    return all_rows


def insert_matches(conn, rows: List[Dict]) -> dict:
    """
    Insert all match rows into the pl_data.matches fact table.

    Uses ON CONFLICT DO NOTHING on the unique_match_team constraint
    (match_id + team_id), so re-running is safe and won't create duplicates.

    Args:
        conn: Open psycopg2 connection
        rows: List of match row dicts from load_all_normalized_csvs()

    Returns:
        Summary dict with inserted count and error count
    """
    if not rows:
        logger.warning("No match rows to insert")
        return {"inserted": 0, "errors": 0}

    logger.info(f"Inserting {len(rows)} match rows into pl_data.matches...")

    # Build the list of value tuples in column order matching the INSERT statement
    db_rows = []
    skipped = 0

    for row in rows:
        # Helper to safely get a value from the row dict, returning None if missing/NaN
        def get(col):
            val = row.get(col)
            if val is None:
                return None
            # pandas reads missing floats as NaN — convert to None for PostgreSQL
            try:
                import math
                if isinstance(val, float) and math.isnan(val):
                    return None
            except (TypeError, ValueError):
                pass
            return val

        # All required fields must be present — skip rows that are missing them
        match_id  = get("match_id")
        season_id = get("season_id")
        team_id   = get("team_id")
        match_date= get("match_date")
        venue     = get("venue")
        opponent  = get("opponent_id")
        result    = get("result")
        gf        = get("goals_for")
        ga        = get("goals_against")

        if not all([match_id, season_id, team_id, match_date, venue, opponent, result]):
            logger.debug(f"Skipping incomplete row: {row}")
            skipped += 1
            continue

        db_rows.append((
            match_id,           # match_id VARCHAR(50)
            season_id,          # season_id VARCHAR(20)
            team_id,            # team_id VARCHAR(50)
            match_date,         # match_date DATE
            venue,              # venue VARCHAR(10)
            opponent,           # opponent_id VARCHAR(50)
            result,             # result CHAR(1)
            gf,                 # goals_for INTEGER
            ga,                 # goals_against INTEGER
            get("xg_for"),      # xg_for DECIMAL (nullable)
            get("xg_against"),  # xg_against DECIMAL (nullable)
            get("shots_for"),           # Extra stats (nullable)
            get("shots_against"),
            get("shots_on_target_for"),
            get("shots_on_target_against"),
            get("corners_for"),
            get("corners_against"),
            get("fouls_for"),
            get("fouls_against"),
            get("yellow_cards"),
            get("red_cards"),
        ))

    if skipped:
        logger.warning(f"Skipped {skipped} incomplete rows before insert")

    # Insert into the DB — only the columns we have data for
    # Columns not listed (start_time, formation, etc.) will default to NULL
    sql = """
        INSERT INTO pl_data.matches (
            match_id, season_id, team_id, match_date, venue, opponent_id,
            result, goals_for, goals_against, xg_for, xg_against,
            possession, notes
        )
        VALUES %s
        ON CONFLICT (match_id, team_id) DO NOTHING
    """

    # We're inserting fewer columns than there are in db_rows tuples
    # Let's use a more explicit column list that matches our actual data
    sql = """
        INSERT INTO pl_data.matches (
            match_id, season_id, team_id, match_date, venue, opponent_id,
            result, goals_for, goals_against, xg_for, xg_against
        )
        VALUES %s
        ON CONFLICT (match_id, team_id) DO NOTHING
    """

    # Trim db_rows to only the 11 columns listed in the SQL above
    trimmed_rows = [r[:11] for r in db_rows]   # Take first 11 values from each tuple

    errors = 0
    try:
        with conn.cursor() as cur:
            execute_values(cur, sql, trimmed_rows, page_size=500)   # Insert in batches of 500
        conn.commit()
        logger.info(f"[OK] Inserted {len(trimmed_rows)} match rows")
    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Batch insert failed: {e}")
        errors += 1

    return {"inserted": len(trimmed_rows), "errors": errors}


def main():
    # Print basic context to the console
    print()
    print("PREMALYTICS STEP 3: LOAD DATA INTO POSTGRESQL")
    print(f"Schema files: {SCHEMA_DIR}")
    print(f"Match data:   {RAW_DATA_DIR}")
    print()

    # -------------------------------------------------------------------------
    # Connect to PostgreSQL using credentials from .env
    # -------------------------------------------------------------------------
    # Connect to PostgreSQL using credentials from .env
    logger.info("Connecting to PostgreSQL...")
    try:
        db_config = get_db_config()        # Loads from .env file
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False            # We manage transactions manually
        logger.info("[OK] Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"[ERROR] Could not connect to PostgreSQL: {e}")
        logger.error("Make sure PostgreSQL is running and .env has correct credentials")
        sys.exit(1)

    try:
        # PHASE A: Schema setup — recreate all tables from SQL files
        print("\n--- PHASE A: Schema Setup ---")
        try:
            run_schema_setup(conn)
            print("[OK] All schema files executed successfully\n")
        except Exception as e:
            logger.error(f"Schema setup failed: {e}")
            logger.error("Cannot continue without a valid schema — exiting")
            sys.exit(1)

        # PHASE B: Discover and insert dimension data (teams + seasons)
        print("--- PHASE B: Inserting Dimension Data ---")

        seasons, teams = discover_dimension_data(RAW_DATA_DIR)

        if not seasons or not teams:
            logger.error("No data found in data/raw/ — run scripts 01 and 02 first")
            sys.exit(1)

        insert_seasons(conn, seasons)   # Insert season records
        insert_teams(conn, teams)       # Insert team records
        print(f"[OK] Inserted {len(seasons)} seasons and {len(teams)} teams\n")

        # PHASE C: Load match data into pl_data.matches
        print("--- PHASE C: Loading Match Data ---")

        rows = load_all_normalized_csvs(RAW_DATA_DIR)   # Read all CSVs

        if not rows:
            logger.error("No match rows found — check that 02_normalize_and_export.py ran correctly")
            sys.exit(1)

        match_summary = insert_matches(conn, rows)      # Insert into DB

        # Final summary
        print()
        print("LOAD COMPLETE SUMMARY")
        print(f"Seasons loaded:       {len(seasons)}")
        print(f"Teams loaded:         {len(teams)}")
        print(f"Match rows processed: {len(rows)}")
        print(f"Match rows inserted:  {match_summary['inserted']}")
        print(f"Errors:               {match_summary['errors']}")
        print()
        print("You can now query your data in pgAdmin:")
        print("  SELECT COUNT(*) FROM pl_data.matches;")
        print("  SELECT * FROM pl_data.v_match_data_quality;")

        if match_summary["errors"] > 0:
            sys.exit(1)

    finally:
        # Always close the connection — even if an error occurred
        conn.close()
        logger.info("PostgreSQL connection closed")


if __name__ == "__main__":
    main()
