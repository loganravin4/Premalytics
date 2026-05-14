"""
=============================================================================
File: ml/utils/database.py
Description: Database connection and query utilities for ML pipeline
=============================================================================

Provides reusable database functions for feature engineering.
"""

import pandas as pd
import psycopg2
from pathlib import Path
import sys

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent.parent / 'database' / 'scripts'))
from config import get_db_config, get_db_schema

def get_connection():
    """
    Get database connection for ML scripts.
    
    Returns:
        psycopg2.connection: Active database connection
    """
    return psycopg2.connect(**get_db_config())

def query_to_dataframe(query: str, conn=None) -> pd.DataFrame:
    """
    Execute SQL query and return results as pandas DataFrame.
    
    Args:
        query: SQL query string
        conn: Database connection (creates new one if None)
        
    Returns:
        pd.DataFrame: Query results
        
    Example:
        >>> df = query_to_dataframe("SELECT * FROM pl_data.teams")
        >>> print(df.head())
    """
    # Create connection if not provided
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    
    try:
        df = pd.read_sql_query(query, conn)
        return df
    finally:
        if close_conn:
            conn.close()

def get_all_matches(season_id: str = None, conn=None) -> pd.DataFrame:
    """
    Get all matches, optionally filtered by season.
    
    Args:
        season_id: Optional season filter (e.g., '2023-2024')
        conn: Database connection
        
    Returns:
        pd.DataFrame: Matches with team names
    """
    query = """
        SELECT 
            m.match_id,
            m.season_id,
            m.match_date,
            m.round,
            m.team_id,
            t1.team_name as team_name,
            m.opponent_id,
            t2.team_name as opponent_name,
            m.venue,
            m.result,
            m.goals_for,
            m.goals_against,
            m.xg_for,
            m.xg_against,
            m.possession,
            m.formation,
            m.opp_formation
        FROM pl_data.matches m
        JOIN pl_data.teams t1 ON m.team_id = t1.team_id
        JOIN pl_data.teams t2 ON m.opponent_id = t2.team_id
    """
    
    if season_id:
        query += f" WHERE m.season_id = '{season_id}'"
    
    query += " ORDER BY m.match_date, m.match_id"
    
    return query_to_dataframe(query, conn)

def get_team_season_stats(season_id: str, conn=None) -> pd.DataFrame:
    """
    Get aggregated team statistics for a season.
    
    Args:
        season_id: Season identifier (e.g., '2023-2024')
        conn: Database connection
        
    Returns:
        pd.DataFrame: Team statistics
    """
    query = f"""
        SELECT 
            t.team_id,
            t.team_name,
            COUNT(*) as matches_played,
            SUM(CASE WHEN m.result = 'W' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN m.result = 'D' THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN m.result = 'L' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN m.result = 'W' THEN 3 WHEN m.result = 'D' THEN 1 ELSE 0 END) as points,
            ROUND(AVG(m.goals_for)::numeric, 2) as avg_goals_for,
            ROUND(AVG(m.goals_against)::numeric, 2) as avg_goals_against,
            ROUND(AVG(m.xg_for)::numeric, 2) as avg_xg_for,
            ROUND(AVG(m.xg_against)::numeric, 2) as avg_xg_against
        FROM pl_data.matches m
        JOIN pl_data.teams t ON m.team_id = t.team_id
        WHERE m.season_id = '{season_id}'
        GROUP BY t.team_id, t.team_name
        ORDER BY points DESC
    """
    
    return query_to_dataframe(query, conn)