import pandas as pd
import psycopg2
from pathlib import Path
import sys

# config lives in database/scripts, which isn't an importable package.
sys.path.append(str(Path(__file__).parent.parent.parent / 'database' / 'scripts'))
from config import get_db_config, get_db_schema

def get_connection():
    return psycopg2.connect(**get_db_config())

def query_to_dataframe(query: str, conn=None) -> pd.DataFrame:
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