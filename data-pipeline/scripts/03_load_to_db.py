"""Recreate the pl_data schema and load every data/raw/{season}/{team}/match_logs_normalized.csv into Postgres."""

import sys
import logging
import math
from pathlib import Path
from typing import List, Dict

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = PIPELINE_DIR.parent

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

DB_SCRIPTS_DIR = PROJECT_ROOT / "database" / "scripts"
if str(DB_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(DB_SCRIPTS_DIR))

from config import get_db_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

SCHEMA_DIR = PROJECT_ROOT / "database" / "schema"
RAW_DATA_DIR = PIPELINE_DIR / "data" / "raw"

# FK order: dimensions must exist before matches and player_stats
SCHEMA_FILES = [
    SCHEMA_DIR / "01_create_dimensions.sql",
    SCHEMA_DIR / "02_create_matches.sql",
    SCHEMA_DIR / "03_create_player_stats.sql",
    SCHEMA_DIR / "04_create_keeper_stats.sql",
    SCHEMA_DIR / "05_create_indexes.sql",
    SCHEMA_DIR / "06_add_match_stats.sql",
]

CURRENT_SEASON = "2025-2026"

def run_schema_setup(conn) -> None:
    """Drop and recreate every pl_data table from the SQL schema files."""
    logger.info("PHASE A: Running schema setup SQL files")

    for sql_file in SCHEMA_FILES:
        if not sql_file.exists():
            logger.warning(f"[SKIP] Schema file not found: {sql_file.name}")
            continue

        logger.info(f"[SQL] Executing {sql_file.name}...")

        sql_content = sql_file.read_text(encoding="utf-8")

        try:
            with conn.cursor() as cur:
                cur.execute(sql_content)
            conn.commit()
            logger.info(f"[OK] {sql_file.name} executed successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"[ERROR] {sql_file.name} failed: {e}")
            raise

def discover_dimension_data(raw_data_dir: Path) -> tuple:
    seasons = set()
    teams   = set()

    for season_dir in sorted(raw_data_dir.iterdir()):
        if not season_dir.is_dir():
            continue

        season_id = season_dir.name

        # Skips leftover api_football/api_soccer dirs from the old scraper
        if not season_id[0].isdigit():
            continue

        for team_dir in sorted(season_dir.iterdir()):
            if not team_dir.is_dir():
                continue

            csv_path = team_dir / "match_logs_normalized.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path, nrows=1)
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
    logger.info(f"Inserting {len(seasons)} seasons into pl_data.seasons...")

    rows = []
    for season_id in sorted(seasons):
        parts = season_id.split("-")
        if len(parts) != 2:
            logger.warning(f"Unexpected season_id format: {season_id!r} — skipping")
            continue

        start_year = int(parts[0])
        end_year   = int(parts[1])

        is_complete = (season_id != CURRENT_SEASON)

        rows.append((
            season_id,
            start_year,
            end_year,
            is_complete,
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
        execute_values(cur, sql, rows)
    conn.commit()
    logger.info(f"[OK] Inserted/skipped {len(rows)} season rows")


def insert_teams(conn, teams: set) -> None:
    logger.info(f"Inserting {len(teams)} teams into pl_data.teams...")

    rows = [
        (team_name, team_name)
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



def load_all_normalized_csvs(raw_data_dir: Path) -> List[Dict]:
    all_rows = []

    for season_dir in sorted(raw_data_dir.iterdir()):
        if not season_dir.is_dir() or not season_dir.name[0].isdigit():
            continue

        for team_dir in sorted(season_dir.iterdir()):
            if not team_dir.is_dir():
                continue

            csv_path = team_dir / "match_logs_normalized.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path)
                all_rows.extend(df.to_dict(orient="records"))
            except Exception as e:
                logger.warning(f"Could not read {csv_path}: {e}")

    logger.info(f"Loaded {len(all_rows)} total match rows from data/raw/")
    return all_rows


def insert_matches(conn, rows: List[Dict]) -> dict:
    if not rows:
        logger.warning("No match rows to insert")
        return {"inserted": 0, "errors": 0}

    logger.info(f"Inserting {len(rows)} match rows into pl_data.matches...")

    db_rows = []
    skipped = 0

    for row in rows:
        def get(col):
            val = row.get(col)
            if val is None:
                return None
            # pandas reads blanks as NaN; Postgres needs None to store NULL
            try:
                if isinstance(val, float) and math.isnan(val):
                    return None
            except (TypeError, ValueError):
                pass
            return val

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
            match_id,
            season_id,
            team_id,
            match_date,
            venue,
            opponent,
            result,
            gf,
            ga,
            get("xg_for"),
            get("xg_against"),
            get("shots_for"),
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

    # Needs migration 06_add_match_stats.sql for the extra stat columns
    sql = """
        INSERT INTO pl_data.matches (
            match_id, season_id, team_id, match_date, venue, opponent_id,
            result, goals_for, goals_against, xg_for, xg_against,
            shots_for, shots_against,
            shots_on_target_for, shots_on_target_against,
            corners_for, corners_against,
            fouls_for, fouls_against,
            yellow_cards, red_cards
        )
        VALUES %s
        ON CONFLICT (match_id, team_id) DO NOTHING
    """

    errors = 0
    try:
        with conn.cursor() as cur:
            execute_values(cur, sql, db_rows, page_size=500)
        conn.commit()
        logger.info(f"[OK] Inserted {len(db_rows)} match rows")
    except Exception as e:
        conn.rollback()
        logger.error(f"[ERROR] Batch insert failed: {e}")
        errors += 1

    return {"inserted": len(db_rows), "errors": errors}


def main():
    print()
    print("NEUTRAL GROUND STEP 3: LOAD DATA INTO POSTGRESQL")
    print(f"Schema files: {SCHEMA_DIR}")
    print(f"Match data:   {RAW_DATA_DIR}")
    print()

    logger.info("Connecting to PostgreSQL...")
    try:
        db_config = get_db_config()
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        logger.info("[OK] Connected to PostgreSQL")
    except Exception as e:
        logger.error(f"[ERROR] Could not connect to PostgreSQL: {e}")
        logger.error("Make sure PostgreSQL is running and .env has correct credentials")
        sys.exit(1)

    try:
        print("\n--- PHASE A: Schema Setup ---")
        try:
            run_schema_setup(conn)
            print("[OK] All schema files executed successfully\n")
        except Exception as e:
            logger.error(f"Schema setup failed: {e}")
            logger.error("Cannot continue without a valid schema — exiting")
            sys.exit(1)

        print("--- PHASE B: Inserting Dimension Data ---")

        seasons, teams = discover_dimension_data(RAW_DATA_DIR)

        if not seasons or not teams:
            logger.error("No data found in data/raw/ — run scripts 01 and 02 first")
            sys.exit(1)

        insert_seasons(conn, seasons)
        insert_teams(conn, teams)
        print(f"[OK] Inserted {len(seasons)} seasons and {len(teams)} teams\n")

        print("--- PHASE C: Loading Match Data ---")

        rows = load_all_normalized_csvs(RAW_DATA_DIR)

        if not rows:
            logger.error("No match rows found — check that 02_normalize_and_export.py ran correctly")
            sys.exit(1)

        match_summary = insert_matches(conn, rows)

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
        conn.close()
        logger.info("PostgreSQL connection closed")


if __name__ == "__main__":
    main()
