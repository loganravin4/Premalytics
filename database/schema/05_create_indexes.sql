-- ============================================================================
-- File: 05_create_indexes.sql
-- Description: Comprehensive indexing strategy for query optimization
-- Dependencies: All previous schema files (01-04)
-- Schema: pl_data
-- ============================================================================

-- Set search path to pl_data schema
SET search_path TO pl_data, public;

-- ============================================================================
-- INDEXING STRATEGY OVERVIEW
-- ============================================================================
-- This file creates additional indexes beyond those already created in 
-- individual table files. Focus areas:
--   1. Cross-table join optimization (multi-table queries)
--   2. ML feature extraction patterns (aggregations, filters)
--   3. Common analytical queries (rankings, comparisons)
--   4. Time-series queries (seasonal trends, form analysis)
--
-- Note: Each table file (01-04) already created basic indexes
-- This file adds COMPOSITE and SPECIALIZED indexes for complex queries
-- ============================================================================

-- ============================================================================
-- SECTION 1: CROSS-TABLE JOIN OPTIMIZATION
-- These indexes speed up joins between related tables
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Creating cross-table join indexes...'; END $$;

-- Players + Teams joins (very common: "which players played for Liverpool?")
CREATE INDEX IF NOT EXISTS idx_players_team_season_name 
    ON pl_data.players(team_id, season_id, player_name);
COMMENT ON INDEX pl_data.idx_players_team_season_name IS 
    'Optimizes queries filtering by team and season, then sorting by player name';

-- Players + Seasons joins with position filter (common ML query)
CREATE INDEX IF NOT EXISTS idx_players_season_position 
    ON pl_data.players(season_id, position, player_id);
COMMENT ON INDEX pl_data.idx_players_season_position IS 
    'Fast filtering by season and position (e.g., all forwards in 2023-2024)';

-- Matches + Teams temporal queries (form analysis over time)
CREATE INDEX IF NOT EXISTS idx_matches_team_date_result 
    ON pl_data.matches(team_id, match_date, result);
COMMENT ON INDEX pl_data.idx_matches_team_date_result IS 
    'Optimizes time-ordered queries like recent form (last 5 games)';

-- Matches opponent analysis (head-to-head records)
CREATE INDEX IF NOT EXISTS idx_matches_team_opponent_season 
    ON pl_data.matches(team_id, opponent_id, season_id);
COMMENT ON INDEX pl_data.idx_matches_team_opponent_season IS 
    'Fast head-to-head lookups between specific teams across seasons';

-- ============================================================================
-- SECTION 2: ML FEATURE EXTRACTION INDEXES
-- These indexes optimize common ML data preparation queries
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Creating ML feature extraction indexes...'; END $$;

-- Player stats with minimum playing time filter (exclude bench warmers)
CREATE INDEX IF NOT EXISTS idx_player_stats_minutes_threshold 
    ON pl_data.player_season_stats(player_season_id, minutes_90s) 
    WHERE minutes_90s >= 5.0;
COMMENT ON INDEX pl_data.idx_player_stats_minutes_threshold IS 
    'Partial index: Only players with 5+ ninety-minute units (450+ minutes played)';

-- Player stats for goal scorers (feature: goal-scoring ability)
CREATE INDEX IF NOT EXISTS idx_player_stats_goal_scorers 
    ON pl_data.player_season_stats(player_season_id, goals, xg, npxg) 
    WHERE goals > 0;
COMMENT ON INDEX pl_data.idx_player_stats_goal_scorers IS 
    'Partial index: Only players who scored goals (for striker analysis)';

-- Player stats for playmakers (feature: creativity metrics)
CREATE INDEX IF NOT EXISTS idx_player_stats_playmakers 
    ON pl_data.player_season_stats(player_season_id, assists, xg_assist, sca_per90, gca_per90) 
    WHERE assists > 0 OR sca_per90 > 3.0;
COMMENT ON INDEX pl_data.idx_player_stats_playmakers IS 
    'Partial index: Creative players (assists or high shot-creating actions)';

-- Player stats for defenders (feature: defensive contributions)
CREATE INDEX IF NOT EXISTS idx_player_stats_defenders 
    ON pl_data.player_season_stats(player_season_id, tackles, interceptions, clearances, blocks) 
    WHERE tackles > 0 OR interceptions > 0;
COMMENT ON INDEX pl_data.idx_player_stats_defenders IS 
    'Partial index: Players with defensive actions (for defender analysis)';

-- Matches for high-scoring games (outlier detection)
CREATE INDEX IF NOT EXISTS idx_matches_high_scoring 
    ON pl_data.matches(match_team_id, goals_for, goals_against) 
    WHERE (goals_for + goals_against) >= 4;
COMMENT ON INDEX pl_data.idx_matches_high_scoring IS 
    'Partial index: High-scoring matches (4+ total goals) for outlier analysis';

-- Matches with xG data (ensure complete data for ML training)
CREATE INDEX IF NOT EXISTS idx_matches_xg_complete 
    ON pl_data.matches(match_team_id, xg_for, xg_against) 
    WHERE xg_for IS NOT NULL AND xg_against IS NOT NULL;
COMMENT ON INDEX pl_data.idx_matches_xg_complete IS 
    'Partial index: Only matches with complete xG data (critical ML feature)';

-- ============================================================================
-- SECTION 3: AGGREGATION QUERY OPTIMIZATION
-- These indexes speed up GROUP BY and aggregate calculations
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Creating aggregation optimization indexes...'; END $$;

-- Team season aggregations (total goals, points, etc.)
CREATE INDEX IF NOT EXISTS idx_matches_team_season_aggregates 
    ON pl_data.matches(team_id, season_id, result, goals_for, goals_against, xg_for);
COMMENT ON INDEX pl_data.idx_matches_team_season_aggregates IS 
    'Optimizes team-level seasonal aggregations (points, goals, xG totals)';

-- Venue-specific aggregations (home vs away performance)
CREATE INDEX IF NOT EXISTS idx_matches_team_venue_performance 
    ON pl_data.matches(team_id, venue, result, goals_for, xg_for);
COMMENT ON INDEX pl_data.idx_matches_team_venue_performance IS 
    'Optimizes home/away split analysis (common ML feature)';

-- Player position-based aggregations
CREATE INDEX IF NOT EXISTS idx_players_position_aggregates 
    ON pl_data.players(position, season_id, team_id);
COMMENT ON INDEX pl_data.idx_players_position_aggregates IS 
    'Fast position-based grouping (e.g., average stats by position)';

-- ============================================================================
-- SECTION 4: RANKING AND COMPARISON QUERIES
-- These indexes optimize ORDER BY operations for leaderboards
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Creating ranking optimization indexes...'; END $$;

-- Top scorers ranking (goals descending)
CREATE INDEX IF NOT EXISTS idx_player_stats_goals_ranking 
    ON pl_data.player_season_stats(goals DESC NULLS LAST, player_season_id) 
    WHERE minutes_90s >= 10.0;
COMMENT ON INDEX pl_data.idx_player_stats_goals_ranking IS 
    'Fast leaderboard: Top goal scorers (min 10 ninety-minute units)';

-- Top assisters ranking
CREATE INDEX IF NOT EXISTS idx_player_stats_assists_ranking 
    ON pl_data.player_season_stats(assists DESC NULLS LAST, player_season_id) 
    WHERE minutes_90s >= 10.0;
COMMENT ON INDEX pl_data.idx_player_stats_assists_ranking IS 
    'Fast leaderboard: Top assist providers (min 10 ninety-minute units)';

-- xG overperformance ranking (players exceeding expected goals)
CREATE INDEX IF NOT EXISTS idx_player_stats_xg_net_ranking 
    ON pl_data.player_season_stats(xg_net DESC NULLS LAST, player_season_id) 
    WHERE minutes_90s >= 10.0 AND xg_net IS NOT NULL;
COMMENT ON INDEX pl_data.idx_player_stats_xg_net_ranking IS 
    'Fast leaderboard: Players most exceeding xG expectations (clinical finishers)';

-- Best passers ranking (pass completion percentage)
CREATE INDEX IF NOT EXISTS idx_player_stats_passing_ranking 
    ON pl_data.player_season_stats(passes_pct DESC NULLS LAST, player_season_id) 
    WHERE passes >= 500;
COMMENT ON INDEX pl_data.idx_player_stats_passing_ranking IS 
    'Fast leaderboard: Best passers by completion rate (min 500 passes)';

-- Team points ranking (wins/draws/losses)
CREATE INDEX IF NOT EXISTS idx_matches_team_points 
    ON pl_data.matches(season_id, team_id, result);
COMMENT ON INDEX pl_data.idx_matches_team_points IS 
    'Optimizes league table calculations (points = 3*wins + 1*draws)';

-- ============================================================================
-- SECTION 5: TIME-SERIES ANALYSIS INDEXES
-- These indexes optimize temporal queries (form, trends, momentum)
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Creating time-series analysis indexes...'; END $$;

-- Recent form analysis (last N games for a team)
CREATE INDEX IF NOT EXISTS idx_matches_team_recent_form 
    ON pl_data.matches(team_id, match_date DESC, result, goals_for, xg_for);
COMMENT ON INDEX pl_data.idx_matches_team_recent_form IS 
    'Optimizes recent form queries (e.g., last 5 games performance)';

-- Match chronology (all matches in date order)
CREATE INDEX IF NOT EXISTS idx_matches_chronological 
    ON pl_data.matches(match_date, season_id, team_id);
COMMENT ON INDEX pl_data.idx_matches_chronological IS 
    'Fast chronological ordering of all matches across seasons';

-- Season progression (early vs late season performance)
CREATE INDEX IF NOT EXISTS idx_matches_season_progression 
    ON pl_data.matches(season_id, match_date, round);
COMMENT ON INDEX pl_data.idx_matches_season_progression IS 
    'Analyzes performance trends within a season (momentum analysis)';

-- ============================================================================
-- SECTION 6: GOALKEEPER-SPECIFIC ADVANCED INDEXES
-- Additional indexes for keeper analysis beyond basic table indexes
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Creating goalkeeper-specific indexes...'; END $$;

-- Elite keeper identification (PSxG + save percentage)
CREATE INDEX IF NOT EXISTS idx_keeper_elite_metrics 
    ON pl_data.player_keeper_stats(gk_psxg_net_per90, gk_save_pct DESC, player_season_id) 
    WHERE gk_games_starts >= 10;
COMMENT ON INDEX pl_data.idx_keeper_elite_metrics IS 
    'Composite index for identifying elite keepers (PSxG + save rate, min 10 starts)';

-- Ball-playing keeper identification
CREATE INDEX IF NOT EXISTS idx_keeper_distribution 
    ON pl_data.player_keeper_stats(gk_passes_length_avg, gk_passes_pct_launched, player_season_id) 
    WHERE gk_games >= 5;
COMMENT ON INDEX pl_data.idx_keeper_distribution IS 
    'Identifies ball-playing vs traditional keepers by distribution patterns';

-- Sweeper-keeper identification
CREATE INDEX IF NOT EXISTS idx_keeper_sweeping 
    ON pl_data.player_keeper_stats(gk_def_actions_outside_pen_area_per90 DESC, 
                                     gk_avg_distance_def_actions DESC, 
                                     player_season_id) 
    WHERE gk_games >= 5;
COMMENT ON INDEX pl_data.idx_keeper_sweeping IS 
    'Identifies sweeper-keepers by defensive actions outside penalty area';

-- ============================================================================
-- SECTION 7: COVERING INDEXES (Include Additional Columns)
-- These indexes include extra columns to avoid table lookups
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Creating covering indexes...'; END $$;

-- Player stats with position context (avoid join to players table)
CREATE INDEX IF NOT EXISTS idx_player_stats_with_position 
    ON pl_data.player_season_stats(player_season_id) 
    INCLUDE (goals, assists, xg, npxg, minutes_90s);
COMMENT ON INDEX pl_data.idx_player_stats_with_position IS 
    'Covering index: Includes key stats for index-only scans';

-- Match results with score (avoid table lookup for common queries)
CREATE INDEX IF NOT EXISTS idx_matches_with_score 
    ON pl_data.matches(team_id, season_id, match_date) 
    INCLUDE (result, goals_for, goals_against, xg_for, xg_against);
COMMENT ON INDEX pl_data.idx_matches_with_score IS 
    'Covering index: Includes match results for index-only scans';

-- ============================================================================
-- SECTION 8: ANALYZE TABLES (Update Statistics)
-- Run ANALYZE to update query planner statistics after creating indexes
-- ============================================================================

DO $$ BEGIN RAISE NOTICE 'Analyzing tables to update query planner statistics...'; END $$;

ANALYZE pl_data.teams;
ANALYZE pl_data.seasons;
ANALYZE pl_data.players;
ANALYZE pl_data.matches;
ANALYZE pl_data.player_season_stats;
ANALYZE pl_data.player_keeper_stats;

-- ============================================================================
-- INDEX SUMMARY REPORT
-- ============================================================================

DO $$
DECLARE
    teams_idx_count INTEGER;
    seasons_idx_count INTEGER;
    players_idx_count INTEGER;
    matches_idx_count INTEGER;
    player_stats_idx_count INTEGER;
    keeper_stats_idx_count INTEGER;
    total_idx_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'INDEX CREATION SUMMARY';
    RAISE NOTICE '========================================';
    
    -- Count indexes per table
    SELECT COUNT(*) INTO teams_idx_count 
    FROM pg_indexes 
    WHERE schemaname = 'pl_data' AND tablename = 'teams';
    
    SELECT COUNT(*) INTO seasons_idx_count 
    FROM pg_indexes 
    WHERE schemaname = 'pl_data' AND tablename = 'seasons';
    
    SELECT COUNT(*) INTO players_idx_count 
    FROM pg_indexes 
    WHERE schemaname = 'pl_data' AND tablename = 'players';
    
    SELECT COUNT(*) INTO matches_idx_count 
    FROM pg_indexes 
    WHERE schemaname = 'pl_data' AND tablename = 'matches';
    
    SELECT COUNT(*) INTO player_stats_idx_count 
    FROM pg_indexes 
    WHERE schemaname = 'pl_data' AND tablename = 'player_season_stats';
    
    SELECT COUNT(*) INTO keeper_stats_idx_count 
    FROM pg_indexes 
    WHERE schemaname = 'pl_data' AND tablename = 'player_keeper_stats';
    
    total_idx_count := teams_idx_count + seasons_idx_count + players_idx_count + 
                       matches_idx_count + player_stats_idx_count + keeper_stats_idx_count;
    
    RAISE NOTICE 'Indexes created per table:';
    RAISE NOTICE '  teams: % indexes', teams_idx_count;
    RAISE NOTICE '  seasons: % indexes', seasons_idx_count;
    RAISE NOTICE '  players: % indexes', players_idx_count;
    RAISE NOTICE '  matches: % indexes', matches_idx_count;
    RAISE NOTICE '  player_season_stats: % indexes', player_stats_idx_count;
    RAISE NOTICE '  player_keeper_stats: % indexes', keeper_stats_idx_count;
    RAISE NOTICE '';
    RAISE NOTICE 'Total indexes in pl_data schema: %', total_idx_count;
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'SCHEMA CREATION COMPLETE';
    RAISE NOTICE '========================================';
    RAISE NOTICE '';
    RAISE NOTICE 'Database structure ready for data loading';
    RAISE NOTICE '';
    RAISE NOTICE 'Next steps:';
    RAISE NOTICE '  1. Load CSV data into tables using Python scripts';
    RAISE NOTICE '  2. Verify data quality using data quality views';
    RAISE NOTICE '  3. Begin ML feature engineering and model training';
    RAISE NOTICE '';
END $$;