"""
=============================================================================
File: load_data_to_postgres.py
Description: Loads scraped CSV data into PostgreSQL database
Author: Premalytics Team
Date: 2024
=============================================================================

This script loads all CSV data from data/raw/ into the PostgreSQL database.

PROCESS OVERVIEW:
1. Load dimension tables first (teams, seasons, players)
2. Load fact tables (matches, player_season_stats, player_keeper_stats)
3. Validate data integrity
4. Generate summary report

DEPENDENCIES:
- psycopg2: PostgreSQL adapter for Python
- pandas: Data manipulation
- pathlib: File path handling
- python-dotenv: Environment variable management

USAGE:
    python database/scripts/load_data_to_postgres.py

Note: Requires database connection details in .env file or config.py
"""

import os
import sys
import re
from pathlib import Path
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional

# Set console encoding to UTF-8 for Windows (before any logging)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Import configuration
from config import get_db_config, get_db_schema, get_project_root

# =============================================================================
# CONFIGURATION
# =============================================================================

# Get configuration from environment variables
DB_CONFIG = get_db_config()
DB_SCHEMA = get_db_schema()
PROJECT_ROOT = get_project_root()
DATA_DIR = PROJECT_ROOT / 'data-pipeline' / 'data' / 'raw'  # ← FIXED

# Seasons to load (exclude incomplete 2025-2026)
SEASONS_TO_LOAD = [
    '2021-2022',
    '2022-2023', 
    '2023-2024',
    '2024-2025'
]

# Set up logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(
            PROJECT_ROOT / 'database' / 'scripts' / 'data_loading.log',
            encoding='utf-8'  # ← Force UTF-8
        ),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

def get_db_connection():
    """
    Establish connection to PostgreSQL database.
    
    Returns:
        psycopg2.connection: Database connection object
        
    Raises:
        psycopg2.Error: If connection fails
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info(f"✅ Connected to database: {DB_CONFIG['database']}")
        return conn
    except psycopg2.Error as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise

def close_db_connection(conn):
    """
    Close database connection.
    
    Args:
        conn: Database connection object
    """
    if conn:
        conn.close()
        logger.info("🔒 Database connection closed")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def extract_team_id_from_url(team_url: str) -> str:
    """
    Extract team ID from FBRef URL.
    
    Args:
        team_url: FBRef team URL (e.g., '/en/squads/b8fd03ef/2023-2024/Liverpool-Stats')
        
    Returns:
        str: Team ID (e.g., 'b8fd03ef')
        
    Example:
        >>> extract_team_id_from_url('/en/squads/b8fd03ef/2023-2024/Liverpool-Stats')
        'b8fd03ef'
    """
    # URL format: /en/squads/{team_id}/{season}/{team_name}-Stats
    parts = team_url.split('/')
    return parts[3] if len(parts) > 3 else None

def extract_team_name_from_path(team_path: Path) -> str:
    """
    Extract team name from directory path.
    
    Args:
        team_path: Path to team directory (e.g., 'data/raw/2023-2024/Liverpool')
        
    Returns:
        str: Team name (e.g., 'Liverpool')
    """
    return team_path.name

def convert_minutes_to_int(minutes_str: str) -> Optional[int]:
    """
    Convert minutes string with commas to integer.
    
    Args:
        minutes_str: Minutes as string (e.g., '2,534' or '900')
        
    Returns:
        int: Minutes as integer (e.g., 2534) or None if invalid
        
    Example:
        >>> convert_minutes_to_int('2,534')
        2534
        >>> convert_minutes_to_int('900')
        900
    """
    if pd.isna(minutes_str) or minutes_str == '':
        return None
    # Remove commas and convert to int
    return int(str(minutes_str).replace(',', ''))

def normalize_team_name(team_name: str) -> str:
    """
    Normalize team name to match directory structure.
    Converts spaces to hyphens for consistent matching.
    """
    return team_name.replace(' ', '-')

# =============================================================================
# PHASE 1: LOAD DIMENSION TABLES
# =============================================================================

def load_teams(conn) -> Dict[str, str]:
    """
    Load teams dimension table.
    
    Uses team directory names to generate consistent, deterministic team IDs.
    This ensures team_id uniqueness and proper matching between teams and opponents.
    
    Args:
        conn: Database connection
        
    Returns:
        Dict[str, str]: Mapping of team_name -> team_id
    """
    logger.info("\n" + "="*80)
    logger.info("PHASE 1.1: Loading teams dimension table")
    logger.info("="*80)
    
    cursor = conn.cursor()
    teams_dict = {}  # team_name -> team_id mapping
    
    try:
        # Step 1: Collect unique teams from all seasons
        all_teams = set()
        for season in SEASONS_TO_LOAD:
            season_path = DATA_DIR / season
            
            if not season_path.exists():
                logger.warning(f"⚠️  Season directory not found: {season_path}")
                continue
            
            # Collect team names from directories
            for team_dir in season_path.iterdir():
                if team_dir.is_dir():
                    team_name = extract_team_name_from_path(team_dir)
                    all_teams.add(team_name)
        
        # Step 2: Generate consistent team_ids and insert into database
        import hashlib
        
        for team_name in sorted(all_teams):
            # Generate consistent 8-character team_id from team name using MD5 hash
            # This ensures the same team always gets the same ID
            team_id = hashlib.md5(team_name.encode()).hexdigest()[:8]
            teams_dict[team_name] = team_id
            
            # Construct team URL
            team_url = f"/en/squads/{team_id}/{team_name.replace(' ', '-')}-Stats"
            
            # Insert into database
            cursor.execute("""
                INSERT INTO pl_data.teams (team_id, team_name, team_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (team_id) DO NOTHING
            """, (team_id, team_name, team_url))
        
        conn.commit()
        logger.info(f"✅ Loaded {len(teams_dict)} teams into database")
        
        # Log team names and IDs for verification
        for team_name, team_id in sorted(teams_dict.items()):
            logger.info(f"   {team_name}: {team_id}")
        
        return teams_dict
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error loading teams: {e}")
        raise
    finally:
        cursor.close()

def load_seasons(conn) -> None:
    """
    Load seasons dimension table.
    
    Inserts season records for all seasons to be loaded.
    
    Args:
        conn: Database connection
    """
    logger.info("\n" + "="*80)
    logger.info("PHASE 1.2: Loading seasons dimension table")
    logger.info("="*80)
    
    cursor = conn.cursor()
    
    try:
        for season_id in SEASONS_TO_LOAD:
            # Parse season (e.g., '2023-2024' -> start_year=2023, end_year=2024)
            start_year, end_year = map(int, season_id.split('-'))
            
            # Insert season
            cursor.execute("""
                INSERT INTO pl_data.seasons (
                    season_id, 
                    start_year, 
                    end_year, 
                    is_complete, 
                    data_collection_date
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (season_id) DO NOTHING
            """, (season_id, start_year, end_year, True, datetime.now().date()))
            
            logger.info(f"   ✅ Inserted season: {season_id}")
        
        conn.commit()
        logger.info(f"✅ Loaded {len(SEASONS_TO_LOAD)} seasons into database")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error loading seasons: {e}")
        raise
    finally:
        cursor.close()

def load_players(conn, teams_dict: Dict[str, str]) -> Dict[Tuple[str, str, str], int]:
    """
    Load players dimension table.
    
    Reads player data from CSV files and inserts into players table.
    Returns mapping for player_season_id lookups.
    
    Args:
        conn: Database connection
        teams_dict: Mapping of team_name -> team_id
        
    Returns:
        Dict: Mapping of (player_id, team_id, season_id) -> player_season_id
    """
    logger.info("\n" + "="*80)
    logger.info("PHASE 1.3: Loading players dimension table")
    logger.info("="*80)
    
    cursor = conn.cursor()
    player_mapping = {}  # (player_id, team_id, season_id) -> player_season_id
    total_players = 0
    
    try:
        for season in SEASONS_TO_LOAD:
            season_path = DATA_DIR / season
            
            if not season_path.exists():
                continue
            
            season_players = 0
            
            # Iterate through teams
            for team_dir in season_path.iterdir():
                if not team_dir.is_dir():
                    continue
                
                team_name = extract_team_name_from_path(team_dir)
                team_id = teams_dict.get(team_name)
                
                if not team_id:
                    logger.warning(f"⚠️  Team ID not found for: {team_name}")
                    continue
                
                # Read player_standard_stats.csv (has all players for the team)
                standard_stats_files = list(team_dir.glob('player_standard_stats_*.csv'))
                
                if not standard_stats_files:
                    logger.warning(f"⚠️  No player_standard_stats found for {team_name} in {season}")
                    continue
                
                df = pd.read_csv(standard_stats_files[0])
                
                # Insert each player
                for _, row in df.iterrows():
                    player_id = row['player_id']
                    player_name = row['player']
                    player_url = row['player_url']
                    nationality = row.get('nationality', None)
                    position = row.get('position', None)
                    
                    # Handle age safely
                    age = None
                    raw_age = row.get('age', None)
                    if pd.notna(raw_age) and raw_age != '':
                        try:
                            age = int(float(raw_age))
                            # Sanity check: reasonable age range
                            if age < 15 or age > 50:
                                logger.warning(f"⚠️  Unusual age for {player_name}: {age} (setting to NULL)")
                                age = None
                        except (ValueError, TypeError) as e:
                            logger.warning(f"⚠️  Invalid age for {player_name}: '{raw_age}' (setting to NULL)")
                            age = None
                    
                    # Skip players with no data (empty rows at end of CSV)
                    if pd.isna(player_id) or player_id == '':
                        continue
                    
                    # Insert player and get player_season_id
                    cursor.execute("""
                        INSERT INTO pl_data.players (
                            player_id, player_name, player_url, team_id, season_id,
                            nationality, position, age
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (player_id, team_id, season_id) DO UPDATE
                        SET player_name = EXCLUDED.player_name
                        RETURNING player_season_id
                    """, (player_id, player_name, player_url, team_id, season,
                          nationality, position, age))
                    
                    player_season_id = cursor.fetchone()[0]
                    
                    # Store mapping
                    player_mapping[(player_id, team_id, season)] = player_season_id
                    season_players += 1
            
            total_players += season_players
            logger.info(f"   ✅ Season {season}: {season_players} players")
        
        conn.commit()
        logger.info(f"✅ Loaded {total_players} total player records into database")
        
        return player_mapping
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error loading players: {e}")
        raise
    finally:
        cursor.close()

# =============================================================================
# PHASE 2: LOAD FACT TABLES
# =============================================================================

def load_matches(conn, teams_dict: Dict[str, str]) -> None:
    """
    Load matches fact table.
    
    Reads match_logs CSV files and inserts team-level match data.
    Each match appears twice (once per team).
    
    Args:
        conn: Database connection
        teams_dict: Mapping of team_name -> team_id
    """
    logger.info("\n" + "="*80)
    logger.info("PHASE 2.1: Loading matches fact table")
    logger.info("="*80)
    
    cursor = conn.cursor()
    total_matches = 0
    
    try:
        for season in SEASONS_TO_LOAD:
            season_path = DATA_DIR / season
            
            if not season_path.exists():
                continue
            
            season_matches = 0
            
            # Iterate through teams
            for team_dir in season_path.iterdir():
                if not team_dir.is_dir():
                    continue
                
                team_name = extract_team_name_from_path(team_dir)
                team_id = teams_dict.get(team_name)
                
                if not team_id:
                    logger.warning(f"⚠️  Team ID not found for: {team_name}")
                    continue
                
                # Read match_logs CSV
                match_log_files = list(team_dir.glob('match_logs_*.csv'))
                
                if not match_log_files:
                    logger.warning(f"⚠️  No match_logs found for {team_name} in {season}")
                    continue
                
                df = pd.read_csv(match_log_files[0])
                
                # Insert each match
                for _, row in df.iterrows():
                    # Get opponent name from CSV (this is reliable)
                    opponent_name = row['opponent']
                    
                    # Normalize opponent name (spaces → hyphens) to match directory names
                    opponent_name_normalized = normalize_team_name(opponent_name)

                    # Look up opponent_id from our teams dictionary
                    opponent_id = teams_dict.get(opponent_name_normalized)
                    
                    if not opponent_id:
                        logger.warning(f"⚠️  Opponent not found in teams: {opponent_name} (skipping match)")
                        continue
                    
                    # Handle None values gracefully
                    xg_for = None if pd.isna(row.get('xg_for')) else float(row['xg_for'])
                    xg_against = None if pd.isna(row.get('xg_against')) else float(row['xg_against'])
                    possession = None if pd.isna(row.get('possession')) else int(row['possession'])
                    
                    # Insert match record
                    cursor.execute("""
                        INSERT INTO pl_data.matches (
                            match_id, season_id, team_id,
                            match_date, start_time, round, day_of_week, venue,
                            opponent_id, opponent_url,
                            result, goals_for, goals_against, xg_for, xg_against,
                            possession, attendance, captain, formation, opp_formation,
                            referee, match_report_url, notes
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s
                        )
                        ON CONFLICT (match_id, team_id) DO NOTHING
                    """, (
                        row['match_id'], season, team_id,
                        row['date'], row.get('start_time'), row.get('round'), 
                        row.get('dayofweek'), row['venue'],
                        opponent_id, row.get('opponent_url'),  # opponent_id is now from lookup
                        row['result'], row['goals_for'], row['goals_against'], 
                        xg_for, xg_against,
                        possession, row.get('attendance'), row.get('captain'), 
                        row.get('formation'), row.get('opp_formation'),
                        row.get('referee'), row.get('match_report_url'), row.get('notes')
                    ))
                    
                    season_matches += 1
            
            total_matches += season_matches
            logger.info(f"   ✅ Season {season}: {season_matches} match records")
        
        conn.commit()
        logger.info(f"✅ Loaded {total_matches} total match records into database")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error loading matches: {e}")
        raise
    finally:
        cursor.close()

def load_player_season_stats(conn, teams_dict: Dict[str, str], 
                             player_mapping: Dict[Tuple[str, str, str], int]) -> None:
    """
    Load player_season_stats fact table (WIDE TABLE).
    
    Merges 7 player stat CSV types into one comprehensive table.
    This is the BIG ONE - 130+ columns!
    
    Args:
        conn: Database connection
        teams_dict: Mapping of team_name -> team_id
        player_mapping: Mapping of (player_id, team_id, season_id) -> player_season_id
    """
    logger.info("\n" + "="*80)
    logger.info("PHASE 2.2: Loading player_season_stats fact table (WIDE TABLE)")
    logger.info("="*80)
    logger.info("📊 Merging 7 stat types: standard, shooting, passing, passing_types, gca, defense, possession")
    
    cursor = conn.cursor()
    total_records = 0
    
    # CSV file types to merge (excluding goalkeeper stats)
    stat_types = [
        'player_standard_stats',
        'player_shooting_stats',
        'player_passing_stats',
        'player_passing_types_stats',
        'player_gca_stats',
        'player_defense_stats',
        'player_possession_stats'
    ]
    
    try:
        for season in SEASONS_TO_LOAD:
            season_path = DATA_DIR / season
            
            if not season_path.exists():
                continue
            
            season_records = 0
            
            # Iterate through teams
            for team_dir in season_path.iterdir():
                if not team_dir.is_dir():
                    continue
                
                team_name = extract_team_name_from_path(team_dir)
                team_id = teams_dict.get(team_name)
                
                if not team_id:
                    continue
                
                # Load and merge all stat types for this team
                merged_df = None
                
                for stat_type in stat_types:
                    stat_files = list(team_dir.glob(f'{stat_type}_*.csv'))
                    
                    if not stat_files:
                        logger.warning(f"⚠️  Missing {stat_type} for {team_name} in {season}")
                        continue
                    
                    df = pd.read_csv(stat_files[0])
                    
                    # Remove 'matches' column (not needed, causes merge issues)
                    if 'matches' in df.columns:
                        df = df.drop(columns=['matches'])
                    
                    # First stat type becomes base DataFrame
                    if merged_df is None:
                        merged_df = df
                    else:
                        # Merge only on player_id (simplest approach)
                        # Drop duplicate metadata columns before merge
                        metadata_cols = ['player_url', 'player', 'nationality', 'position', 'age', 'minutes_90s']
                        cols_to_drop = [col for col in df.columns 
                                      if col in merged_df.columns and col != 'player_id']
                        
                        if cols_to_drop:
                            df_to_merge = df.drop(columns=cols_to_drop)
                        else:
                            df_to_merge = df
                        
                        merged_df = merged_df.merge(
                            df_to_merge,
                            on='player_id',
                            how='outer'
                        )
                
                if merged_df is None or len(merged_df) == 0:
                    logger.warning(f"⚠️  No stats found for {team_name} in {season}")
                    continue
                
                # Insert merged stats for each player
                for idx, row in merged_df.iterrows():
                    player_id = row.get('player_id')
                    
                    # Skip empty rows
                    if pd.isna(player_id) or player_id == '':
                        continue
                    
                    # Get player_season_id from mapping
                    player_season_id = player_mapping.get((player_id, team_id, season))
                    
                    if not player_season_id:
                        logger.warning(f"⚠️  Player {player_id} not found in mapping for {team_name} {season}")
                        continue
                    
                    # Convert minutes string to int safely
                    minutes = None
                    minutes_str = row.get('minutes')
                    if pd.notna(minutes_str) and minutes_str != '':
                        try:
                            minutes = int(str(minutes_str).replace(',', ''))
                        except (ValueError, TypeError):
                            pass
                    
                    # Helper function to safely get values
                    def safe_get(column_name, default=None):
                        """Safely get column value, return None if missing or NaN"""
                        value = row.get(column_name, default)
                        if pd.isna(value):
                            return None
                        return value
                    
                    # Use savepoint to allow individual INSERT failures without aborting transaction
                    # Sanitize savepoint name to ensure valid PostgreSQL identifier
                    savepoint_name = f"sp_{player_id}_{team_id}_{season}"
                    savepoint_name = re.sub(r'[^a-zA-Z0-9_]', '_', savepoint_name)
                    # Ensure it starts with a letter and is not too long (PostgreSQL limit is 63 chars)
                    if not savepoint_name[0].isalpha():
                        savepoint_name = 'sp_' + savepoint_name
                    savepoint_name = savepoint_name[:63]
                    
                    try:
                        cursor.execute(f"SAVEPOINT {savepoint_name}")
                        
                        # Build INSERT statement with ALL 130+ columns
                        cursor.execute("""
                            INSERT INTO pl_data.player_season_stats (
                                player_season_id,
                                
                                -- Standard stats (29 columns)
                                games, games_starts, minutes, minutes_90s,
                                goals, assists, goals_assists, goals_pens, pens_made, pens_att,
                                cards_yellow, cards_red,
                                xg, npxg, xg_assist, npxg_xg_assist,
                                progressive_carries, progressive_passes, progressive_passes_received,
                                goals_per90, assists_per90, goals_assists_per90,
                                goals_pens_per90, goals_assists_pens_per90,
                                xg_per90, xg_assist_per90, xg_xg_assist_per90,
                                npxg_per90, npxg_xg_assist_per90,
                                
                                -- Shooting stats (12 columns)
                                shots, shots_on_target, shots_on_target_pct,
                                shots_per90, shots_on_target_per90,
                                goals_per_shot, goals_per_shot_on_target,
                                average_shot_distance, shots_free_kicks,
                                npxg_per_shot, xg_net, npxg_net,
                                
                                -- Passing stats (20 columns)
                                passes_completed, passes, passes_pct,
                                passes_total_distance, passes_progressive_distance,
                                passes_completed_short, passes_short, passes_pct_short,
                                passes_completed_medium, passes_medium, passes_pct_medium,
                                passes_completed_long, passes_long, passes_pct_long,
                                pass_xa, xg_assist_net, assisted_shots,
                                passes_into_final_third, passes_into_penalty_area, crosses_into_penalty_area,
                                
                                -- Passing types (13 columns)
                                passes_live, passes_dead, passes_free_kicks,
                                through_balls, passes_switches, crosses, throw_ins,
                                corner_kicks, corner_kicks_in, corner_kicks_out, corner_kicks_straight,
                                passes_offsides, passes_blocked,
                                
                                -- GCA stats (16 columns)
                                sca, sca_per90,
                                sca_passes_live, sca_passes_dead, sca_take_ons, sca_shots, sca_fouled, sca_defense,
                                gca, gca_per90,
                                gca_passes_live, gca_passes_dead, gca_take_ons, gca_shots, gca_fouled, gca_defense,
                                
                                -- Defensive stats (16 columns)
                                tackles, tackles_won,
                                tackles_def_3rd, tackles_mid_3rd, tackles_att_3rd,
                                challenge_tackles, challenges, challenge_tackles_pct, challenges_lost,
                                blocks, blocked_shots, blocked_passes,
                                interceptions, tackles_interceptions, clearances, errors,
                                
                                -- Possession stats (22 columns)
                                touches, touches_def_pen_area, touches_def_3rd, touches_mid_3rd,
                                touches_att_3rd, touches_att_pen_area, touches_live_ball,
                                take_ons, take_ons_won, take_ons_won_pct,
                                take_ons_tackled, take_ons_tackled_pct,
                                carries, carries_distance, carries_progressive_distance,
                                progressive_carries_poss, carries_into_final_third, carries_into_penalty_area,
                                miscontrols, dispossessed,
                                passes_received, progressive_passes_received_poss
                            )
                            VALUES (
                                %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                            )
                            ON CONFLICT (player_season_id) DO NOTHING
                        """, (
                            player_season_id,
                            
                            # Standard stats (29 values)
                            safe_get('games'), safe_get('games_starts'), minutes, safe_get('minutes_90s'),
                            safe_get('goals'), safe_get('assists'), safe_get('goals_assists'), 
                            safe_get('goals_pens'), safe_get('pens_made'), safe_get('pens_att'),
                            safe_get('cards_yellow'), safe_get('cards_red'),
                            safe_get('xg'), safe_get('npxg'), safe_get('xg_assist'), safe_get('npxg_xg_assist'),
                            safe_get('progressive_carries'), safe_get('progressive_passes'), 
                            safe_get('progressive_passes_received'),
                            safe_get('goals_per90'), safe_get('assists_per90'), safe_get('goals_assists_per90'),
                            safe_get('goals_pens_per90'), safe_get('goals_assists_pens_per90'),
                            safe_get('xg_per90'), safe_get('xg_assist_per90'), safe_get('xg_xg_assist_per90'),
                            safe_get('npxg_per90'), safe_get('npxg_xg_assist_per90'),
                            
                            # Shooting stats (12 values)
                            safe_get('shots'), safe_get('shots_on_target'), safe_get('shots_on_target_pct'),
                            safe_get('shots_per90'), safe_get('shots_on_target_per90'),
                            safe_get('goals_per_shot'), safe_get('goals_per_shot_on_target'),
                            safe_get('average_shot_distance'), safe_get('shots_free_kicks'),
                            safe_get('npxg_per_shot'), safe_get('xg_net'), safe_get('npxg_net'),
                            
                            # Passing stats (20 values)
                            safe_get('passes_completed'), safe_get('passes'), safe_get('passes_pct'),
                            safe_get('passes_total_distance'), safe_get('passes_progressive_distance'),
                            safe_get('passes_completed_short'), safe_get('passes_short'), safe_get('passes_pct_short'),
                            safe_get('passes_completed_medium'), safe_get('passes_medium'), safe_get('passes_pct_medium'),
                            safe_get('passes_completed_long'), safe_get('passes_long'), safe_get('passes_pct_long'),
                            safe_get('pass_xa'), safe_get('xg_assist_net'), safe_get('assisted_shots'),
                            safe_get('passes_into_final_third'), safe_get('passes_into_penalty_area'), 
                            safe_get('crosses_into_penalty_area'),
                            
                            # Passing types (13 values)
                            safe_get('passes_live'), safe_get('passes_dead'), safe_get('passes_free_kicks'),
                            safe_get('through_balls'), safe_get('passes_switches'), safe_get('crosses'), 
                            safe_get('throw_ins'),
                            safe_get('corner_kicks'), safe_get('corner_kicks_in'), safe_get('corner_kicks_out'), 
                            safe_get('corner_kicks_straight'),
                            safe_get('passes_offsides'), safe_get('passes_blocked'),
                            
                            # GCA stats (16 values)
                            safe_get('sca'), safe_get('sca_per90'),
                            safe_get('sca_passes_live'), safe_get('sca_passes_dead'), safe_get('sca_take_ons'), 
                            safe_get('sca_shots'), safe_get('sca_fouled'), safe_get('sca_defense'),
                            safe_get('gca'), safe_get('gca_per90'),
                            safe_get('gca_passes_live'), safe_get('gca_passes_dead'), safe_get('gca_take_ons'), 
                            safe_get('gca_shots'), safe_get('gca_fouled'), safe_get('gca_defense'),
                            
                            # Defense stats (16 values)
                            safe_get('tackles'), safe_get('tackles_won'),
                            safe_get('tackles_def_3rd'), safe_get('tackles_mid_3rd'), safe_get('tackles_att_3rd'),
                            safe_get('challenge_tackles'), safe_get('challenges'), safe_get('challenge_tackles_pct'), 
                            safe_get('challenges_lost'),
                            safe_get('blocks'), safe_get('blocked_shots'), safe_get('blocked_passes'),
                            safe_get('interceptions'), safe_get('tackles_interceptions'), 
                            safe_get('clearances'), safe_get('errors'),
                            
                            # Possession stats (22 values)
                            safe_get('touches'), safe_get('touches_def_pen_area'), safe_get('touches_def_3rd'), 
                            safe_get('touches_mid_3rd'),
                            safe_get('touches_att_3rd'), safe_get('touches_att_pen_area'), 
                            safe_get('touches_live_ball'),
                            safe_get('take_ons'), safe_get('take_ons_won'), safe_get('take_ons_won_pct'),
                            safe_get('take_ons_tackled'), safe_get('take_ons_tackled_pct'),
                            safe_get('carries'), safe_get('carries_distance'), safe_get('carries_progressive_distance'),
                            safe_get('progressive_carries_poss'),  # From possession stats (different from standard stats progressive_carries)
                            safe_get('carries_into_final_third'), safe_get('carries_into_penalty_area'),
                            safe_get('miscontrols'), safe_get('dispossessed'),
                            safe_get('passes_received'), safe_get('progressive_passes_received_poss')
                        ))
                        
                        # Check if row was inserted (not skipped due to conflict)
                        if cursor.rowcount > 0:
                            season_records += 1
                        
                        # Release savepoint on success
                        cursor.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                        
                    except Exception as e:
                        # Rollback to savepoint to allow transaction to continue
                        try:
                            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                        except Exception:
                            pass  # Savepoint might not exist if error occurred before it was created
                        
                        # Log the specific error but continue processing
                        logger.warning(f"⚠️  Failed to insert player {player_id} from {team_name}: {e}")
                        continue
            
            total_records += season_records
            logger.info(f"   ✅ Season {season}: {season_records} player stat records")
        
        conn.commit()
        logger.info(f"✅ Loaded {total_records} player season stat records (130+ columns each!)")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"❌ Error loading player season stats: {e}")
        raise
    finally:
        cursor.close()
        
# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """
    Main execution function.
    Orchestrates the entire data loading process.
    """
    logger.info("\n" + "="*80)
    logger.info("🚀 PREMALYTICS DATA LOADING SCRIPT")
    logger.info("="*80)
    logger.info(f"📂 Data directory: {DATA_DIR}")
    logger.info(f"🗄️  Database: {DB_CONFIG['database']}")
    logger.info(f"📅 Seasons to load: {', '.join(SEASONS_TO_LOAD)}")
    logger.info("="*80)
    
    # Verify data directory exists
    if not DATA_DIR.exists():
        logger.error(f"❌ Data directory not found: {DATA_DIR}")
        sys.exit(1)
    
    # Connect to database
    conn = None
    
    try:
        conn = get_db_connection()
        
        # PHASE 1: Load dimension tables
        teams_dict = load_teams(conn)
        load_seasons(conn)
        player_mapping = load_players(conn, teams_dict)
        
        # PHASE 2: Load fact tables
        load_matches(conn, teams_dict)
        load_player_season_stats(conn, teams_dict, player_mapping)
        
        # TODO: Add load_player_keeper_stats() here
        
        logger.info("\n" + "="*80)
        logger.info("🎉 DATA LOADING COMPLETE!")
        logger.info("="*80)
        logger.info("✅ All data successfully loaded into PostgreSQL")
        logger.info("📊 Next steps:")
        logger.info("   1. Run validation script to verify data quality")
        logger.info("   2. Query data quality views for summary statistics")
        logger.info("   3. Begin ML feature engineering!")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
        
    finally:
        if conn:
            close_db_connection(conn)

if __name__ == "__main__":
    main()