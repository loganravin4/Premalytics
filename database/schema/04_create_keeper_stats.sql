-- ============================================================================
-- File: 04_create_keeper_stats.sql
-- Description: Creates goalkeeper-specific statistics table
-- Dependencies: 01_create_dimensions.sql (requires players table)
-- Schema: pl_data
-- ============================================================================

-- Set search path to pl_data schema
SET search_path TO pl_data, public;

-- ============================================================================
-- FACT TABLE: player_keeper_stats
-- Description: Goalkeeper-specific statistics (separate from outfield players)
-- 
-- WHY SEPARATE TABLE?
-- Goalkeeper stats are fundamentally different from outfield player stats:
--   - Only ~2-3 goalkeepers per team have data
--   - 40+ unique goalkeeper metrics (saves, distribution, sweeping)
--   - Would create 95%+ NULL values in player_season_stats table
--
-- DESIGN: One-to-One relationship with players table
--   - Only players with position='GK' will have records here
--   - Foreign key ensures data integrity
--
-- DATA SOURCE: Merges two CSV file types:
--   1. player_keeper_stats.csv         (Basic keeper stats: 25 columns)
--   2. player_advanced_keeper_stats.csv (Advanced keeper stats: 31 columns)
--   TOTAL: 54 goalkeeper-specific columns
--
-- Expected rows per season: ~60 goalkeepers (20 teams × ~3 keepers each)
-- Total rows (4 seasons): ~240 goalkeeper records
-- ============================================================================

DROP TABLE IF EXISTS pl_data.player_keeper_stats CASCADE;

CREATE TABLE pl_data.player_keeper_stats (
    -- ========================================================================
    -- PRIMARY KEY & FOREIGN KEY
    -- ========================================================================
    player_season_id INTEGER PRIMARY KEY,     -- References pl_data.players(player_season_id)
    
    -- ========================================================================
    -- SECTION 1: BASIC GOALKEEPER STATS (from player_keeper_stats.csv)
    -- Games, saves, clean sheets, goals against
    -- ========================================================================
    
    -- Playing time (goalkeeper-specific)
    gk_games INTEGER,                         -- Total games as goalkeeper
    gk_games_starts INTEGER,                  -- Games started as goalkeeper
    gk_minutes INTEGER,                       -- Minutes played as goalkeeper
    minutes_90s DECIMAL(5,2),                 -- Minutes as 90-minute units (for per-90 stats)
    
    -- Goals against
    gk_goals_against INTEGER,                 -- Total goals conceded
    gk_goals_against_per90 DECIMAL(4,2),      -- Goals conceded per 90 minutes (lower = better)
    
    -- Shot stopping
    gk_shots_on_target_against INTEGER,       -- Shots on target faced
    gk_saves INTEGER,                         -- Saves made
    gk_save_pct DECIMAL(5,2),                 -- Save percentage (higher = better, elite: >75%)
    
    -- Match results (from goalkeeper perspective)
    gk_wins INTEGER,                          -- Wins as goalkeeper
    gk_ties INTEGER,                          -- Draws as goalkeeper
    gk_losses INTEGER,                        -- Losses as goalkeeper
    
    -- Clean sheets (KEY goalkeeper metric)
    gk_clean_sheets INTEGER,                  -- Games without conceding (shutouts)
    gk_clean_sheets_pct DECIMAL(5,2),         -- Clean sheet percentage (elite: >40%)
    
    -- Penalty saving
    gk_pens_att INTEGER,                      -- Penalties faced
    gk_pens_allowed INTEGER,                  -- Penalties conceded
    gk_pens_saved INTEGER,                    -- Penalties saved
    gk_pens_missed INTEGER,                   -- Penalties missed by opponent (off target)
    gk_pens_save_pct DECIMAL(5,2),            -- Penalty save % (elite: >25%, average: ~20%)
    
    -- ========================================================================
    -- SECTION 2: ADVANCED GOALKEEPER STATS (from player_advanced_keeper_stats.csv)
    -- Post-shot xG (PSxG), distribution, sweeping, cross claiming
    -- ========================================================================
    
    -- Goals against breakdown by situation
    gk_pens_allowed_adv INTEGER,              -- Penalties allowed (from advanced stats)
    gk_free_kick_goals_against INTEGER,       -- Goals from direct free kicks
    gk_corner_kick_goals_against INTEGER,     -- Goals from corners
    gk_own_goals_against INTEGER,             -- Own goals (not keeper's fault)
    
    -- Post-Shot Expected Goals (PSxG) - Elite metric for shot-stopping quality
    gk_psxg DECIMAL(5,2),                     -- Post-shot xG (expected goals based on shot placement)
    gk_psnpxg_per_shot_on_target_against DECIMAL(4,2),  -- PSxG per shot on target
    gk_psxg_net DECIMAL(5,2),                 -- Goals allowed - PSxG (negative = good shot-stopping)
    gk_psxg_net_per90 DECIMAL(4,2),           -- PSxG net per 90 (KEY elite keeper metric)
    
    -- Distribution - Launched passes (long balls from goalkeeper)
    gk_passes_completed_launched INTEGER,     -- Long passes (>40 yards) completed
    gk_passes_launched INTEGER,               -- Long passes attempted
    gk_passes_pct_launched DECIMAL(5,2),      -- Long pass completion % (typical: 30-40%)
    
    -- Distribution - Overall passing
    gk_passes INTEGER,                        -- Total passes attempted by keeper
    gk_passes_throws INTEGER,                 -- Throws made (typically high success rate)
    gk_pct_passes_launched DECIMAL(5,2),      -- % of passes that were long balls
    gk_passes_length_avg DECIMAL(5,2),        -- Average pass distance in yards
    
    -- Distribution - Goal kicks
    gk_goal_kicks INTEGER,                    -- Total goal kicks taken
    gk_pct_goal_kicks_launched DECIMAL(5,2),  -- % of goal kicks that were long (>40 yards)
    gk_goal_kick_length_avg DECIMAL(5,2),     -- Average goal kick distance in yards
    
    -- Cross claiming (dealing with crosses into the box)
    gk_crosses INTEGER,                       -- Crosses into box faced
    gk_crosses_stopped INTEGER,               -- Crosses claimed/punched/stopped
    gk_crosses_stopped_pct DECIMAL(5,2),      -- Cross stopping % (elite: >10%)
    
    -- Sweeping (acting as sweeper-keeper outside penalty area)
    gk_def_actions_outside_pen_area INTEGER,  -- Defensive actions outside box
    gk_def_actions_outside_pen_area_per90 DECIMAL(4,2),  -- Sweeping actions per 90
    gk_avg_distance_def_actions DECIMAL(5,2), -- Average distance from goal for def actions (yards)
    
    -- ========================================================================
    -- METADATA
    -- ========================================================================
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- ========================================================================
    -- FOREIGN KEY CONSTRAINTS
    -- ========================================================================
    CONSTRAINT fk_keeper_stats_player FOREIGN KEY (player_season_id) 
        REFERENCES pl_data.players(player_season_id) 
        ON DELETE CASCADE,
    
    -- ========================================================================
    -- DATA INTEGRITY CONSTRAINTS
    -- ========================================================================
    
    -- Games started cannot exceed games played
    CONSTRAINT check_gk_games_starts CHECK (
        gk_games_starts IS NULL OR gk_games IS NULL OR gk_games_starts <= gk_games
    ),
    
    -- Minutes must be non-negative
    CONSTRAINT check_gk_minutes CHECK (gk_minutes IS NULL OR gk_minutes >= 0),
    
    -- Goals against must be non-negative
    CONSTRAINT check_gk_goals_against CHECK (
        gk_goals_against IS NULL OR gk_goals_against >= 0
    ),
    
    -- Saves must be non-negative
    CONSTRAINT check_gk_saves CHECK (gk_saves IS NULL OR gk_saves >= 0),
    
    -- Save percentage must be between 0 and 100
    CONSTRAINT check_gk_save_pct CHECK (
        gk_save_pct IS NULL OR (gk_save_pct >= 0 AND gk_save_pct <= 100)
    ),
    
    -- Clean sheet percentage must be between 0 and 100
    CONSTRAINT check_gk_clean_sheets_pct CHECK (
        gk_clean_sheets_pct IS NULL OR (gk_clean_sheets_pct >= 0 AND gk_clean_sheets_pct <= 100)
    ),
    
    -- Match results must sum to total games
    CONSTRAINT check_gk_results CHECK (
        gk_games IS NULL OR 
        (gk_wins IS NULL AND gk_ties IS NULL AND gk_losses IS NULL) OR
        (gk_wins + gk_ties + gk_losses = gk_games)
    ),
    
    -- Clean sheets cannot exceed games played
    CONSTRAINT check_gk_clean_sheets CHECK (
        gk_clean_sheets IS NULL OR gk_games IS NULL OR gk_clean_sheets <= gk_games
    ),
    
    -- Penalties saved cannot exceed penalties faced
    CONSTRAINT check_gk_pens_saved CHECK (
        gk_pens_saved IS NULL OR gk_pens_att IS NULL OR gk_pens_saved <= gk_pens_att
    ),
    
    -- Penalties allowed cannot exceed penalties faced
    CONSTRAINT check_gk_pens_allowed CHECK (
        gk_pens_allowed IS NULL OR gk_pens_att IS NULL OR gk_pens_allowed <= gk_pens_att
    ),
    
    -- Penalty save percentage must be between 0 and 100
    CONSTRAINT check_gk_pens_save_pct CHECK (
        gk_pens_save_pct IS NULL OR (gk_pens_save_pct >= 0 AND gk_pens_save_pct <= 100)
    ),
    
    -- Passes completed cannot exceed passes attempted
    CONSTRAINT check_gk_passes_launched CHECK (
        gk_passes_completed_launched IS NULL OR 
        gk_passes_launched IS NULL OR 
        gk_passes_completed_launched <= gk_passes_launched
    ),
    
    -- Percentage constraints (0-100)
    CONSTRAINT check_gk_percentages CHECK (
        (gk_passes_pct_launched IS NULL OR (gk_passes_pct_launched >= 0 AND gk_passes_pct_launched <= 100)) AND
        (gk_pct_passes_launched IS NULL OR (gk_pct_passes_launched >= 0 AND gk_pct_passes_launched <= 100)) AND
        (gk_pct_goal_kicks_launched IS NULL OR (gk_pct_goal_kicks_launched >= 0 AND gk_pct_goal_kicks_launched <= 100)) AND
        (gk_crosses_stopped_pct IS NULL OR (gk_crosses_stopped_pct >= 0 AND gk_crosses_stopped_pct <= 100))
    ),
    
    -- Crosses stopped cannot exceed crosses faced
    CONSTRAINT check_gk_crosses_stopped CHECK (
        gk_crosses_stopped IS NULL OR 
        gk_crosses IS NULL OR 
        gk_crosses_stopped <= gk_crosses
    )
);

-- ============================================================================
-- TABLE COMMENTS (Documentation)
-- ============================================================================
COMMENT ON TABLE pl_data.player_keeper_stats IS 
'Goalkeeper-specific statistics. Only players with position=GK have records here.';

COMMENT ON COLUMN pl_data.player_keeper_stats.player_season_id IS 
'Foreign key to pl_data.players. One-to-one relationship with goalkeeper players.';

-- Basic keeper stats comments
COMMENT ON COLUMN pl_data.player_keeper_stats.gk_save_pct IS 
'Save percentage: (saves / shots on target against) × 100. Elite keepers: >75%.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_clean_sheets IS 
'Games where goalkeeper did not concede any goals. KEY performance metric.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_clean_sheets_pct IS 
'Clean sheet percentage. Elite keepers: >40%, Average: 25-35%.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_goals_against_per90 IS 
'Goals conceded per 90 minutes. Elite keepers: <1.0, Average: 1.0-1.3.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_pens_save_pct IS 
'Penalty save percentage. Elite: >25%, Average: ~20%, Random chance: ~20%.';

-- Advanced keeper stats comments
COMMENT ON COLUMN pl_data.player_keeper_stats.gk_psxg IS 
'Post-Shot xG: Expected goals based on shot placement after shot is taken. Measures shot difficulty faced.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_psxg_net IS 
'Goals Against - PSxG. Negative values = shot-stopping above expectation (better). KEY elite keeper metric.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_psxg_net_per90 IS 
'PSxG net per 90 minutes. Elite shot-stoppers: < -0.10 (preventing 0.1 goals per 90 above expected).';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_passes_pct_launched IS 
'Percentage of completed launched passes. Modern keepers: 30-40%, Traditional: 20-30%.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_passes_length_avg IS 
'Average pass length in yards. Ball-playing keepers: <30 yards, Traditional: >35 yards.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_crosses_stopped_pct IS 
'Percentage of crosses into box that keeper deals with. Elite: >10%, Average: 6-9%.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_def_actions_outside_pen_area_per90 IS 
'Sweeper-keeper actions per 90. High pressing teams: >1.5, Traditional: <1.0.';

COMMENT ON COLUMN pl_data.player_keeper_stats.gk_avg_distance_def_actions IS 
'Average distance from goal for defensive actions. Sweeper-keepers: >17 yards, Traditional: <15 yards.';

-- ============================================================================
-- INDEXES FOR QUERY PERFORMANCE
-- ============================================================================

-- Foreign key index
CREATE INDEX idx_keeper_stats_player_season ON pl_data.player_keeper_stats(player_season_id);

-- Performance metric indexes (for finding elite keepers)
CREATE INDEX idx_keeper_stats_save_pct ON pl_data.player_keeper_stats(gk_save_pct DESC NULLS LAST);
CREATE INDEX idx_keeper_stats_clean_sheets_pct ON pl_data.player_keeper_stats(gk_clean_sheets_pct DESC NULLS LAST);
CREATE INDEX idx_keeper_stats_goals_against_per90 ON pl_data.player_keeper_stats(gk_goals_against_per90 ASC NULLS LAST);
CREATE INDEX idx_keeper_stats_psxg_net_per90 ON pl_data.player_keeper_stats(gk_psxg_net_per90 ASC NULLS LAST);

-- Style indexes (ball-playing vs traditional)
CREATE INDEX idx_keeper_stats_sweeping ON pl_data.player_keeper_stats(gk_def_actions_outside_pen_area_per90 DESC NULLS LAST);
CREATE INDEX idx_keeper_stats_pass_length ON pl_data.player_keeper_stats(gk_passes_length_avg ASC NULLS LAST);

-- ============================================================================
-- DATA QUALITY VIEWS
-- ============================================================================

-- View: Goalkeeper performance summary with player context
CREATE OR REPLACE VIEW pl_data.v_keeper_performance AS
SELECT 
    p.player_season_id,
    p.player_name,
    t.team_name,
    s.season_id,
    
    -- Playing time
    gks.gk_games,
    gks.gk_games_starts,
    gks.minutes_90s,
    
    -- Shot stopping
    gks.gk_save_pct,
    gks.gk_clean_sheets,
    gks.gk_clean_sheets_pct,
    gks.gk_goals_against_per90,
    
    -- Advanced metrics
    gks.gk_psxg_net,
    gks.gk_psxg_net_per90,
    
    -- Style indicators
    gks.gk_passes_length_avg,
    gks.gk_def_actions_outside_pen_area_per90,
    
    -- Classification
    CASE 
        WHEN gks.gk_passes_length_avg < 30 THEN 'Ball-Playing'
        WHEN gks.gk_passes_length_avg >= 30 THEN 'Traditional'
        ELSE 'Unknown'
    END as keeper_style,
    
    CASE
        WHEN gks.gk_def_actions_outside_pen_area_per90 > 1.5 THEN 'Sweeper-Keeper'
        WHEN gks.gk_def_actions_outside_pen_area_per90 <= 1.5 THEN 'Traditional'
        ELSE 'Unknown'
    END as sweeping_style
    
FROM pl_data.player_keeper_stats gks
JOIN pl_data.players p USING (player_season_id)
JOIN pl_data.teams t ON p.team_id = t.team_id
JOIN pl_data.seasons s ON p.season_id = s.season_id
WHERE gks.gk_games >= 5  -- Minimum games threshold
ORDER BY s.season_id DESC, gks.gk_save_pct DESC;

COMMENT ON VIEW pl_data.v_keeper_performance IS 
'Goalkeeper performance summary with style classification. Filtered to keepers with 5+ games.';

-- View: Elite shot-stoppers (PSxG net analysis)
CREATE OR REPLACE VIEW pl_data.v_elite_shot_stoppers AS
SELECT 
    p.player_name,
    t.team_name,
    s.season_id,
    gks.gk_games_starts,
    gks.gk_save_pct,
    gks.gk_psxg,
    gks.gk_goals_against,
    gks.gk_psxg_net,
    gks.gk_psxg_net_per90,
    
    -- Interpretation
    CASE
        WHEN gks.gk_psxg_net_per90 < -0.10 THEN 'Elite'
        WHEN gks.gk_psxg_net_per90 < 0 THEN 'Above Average'
        WHEN gks.gk_psxg_net_per90 = 0 THEN 'Average'
        WHEN gks.gk_psxg_net_per90 > 0 THEN 'Below Average'
        ELSE 'Unknown'
    END as shot_stopping_quality
    
FROM pl_data.player_keeper_stats gks
JOIN pl_data.players p USING (player_season_id)
JOIN pl_data.teams t ON p.team_id = t.team_id
JOIN pl_data.seasons s ON p.season_id = s.season_id
WHERE gks.gk_games_starts >= 10  -- Significant playing time
  AND gks.gk_psxg IS NOT NULL
ORDER BY gks.gk_psxg_net_per90 ASC;

COMMENT ON VIEW pl_data.v_elite_shot_stoppers IS 
'Keepers ranked by PSxG net per 90 (elite shot-stopping metric). Filtered to 10+ starts.';

-- View: Data completeness check for goalkeeper stats
CREATE OR REPLACE VIEW pl_data.v_keeper_stats_data_quality AS
SELECT 
    s.season_id,
    COUNT(*) as total_keepers,
    
    -- Basic stats completeness
    COUNT(gks.gk_games) as has_games,
    COUNT(gks.gk_saves) as has_saves,
    COUNT(gks.gk_save_pct) as has_save_pct,
    COUNT(gks.gk_clean_sheets) as has_clean_sheets,
    
    -- Advanced stats completeness
    COUNT(gks.gk_psxg) as has_psxg,
    COUNT(gks.gk_psxg_net) as has_psxg_net,
    COUNT(gks.gk_passes_length_avg) as has_pass_length,
    COUNT(gks.gk_def_actions_outside_pen_area) as has_sweeping_actions
    
FROM pl_data.player_keeper_stats gks
JOIN pl_data.players p USING (player_season_id)
JOIN pl_data.seasons s ON p.season_id = s.season_id
GROUP BY s.season_id
ORDER BY s.season_id;

COMMENT ON VIEW pl_data.v_keeper_stats_data_quality IS 
'Data completeness check for goalkeeper statistics per season.';

-- ============================================================================
-- EXAMPLE QUERIES (for documentation/testing)
-- ============================================================================

-- Query 1: Top shot-stoppers by save percentage (min 15 games started)
-- SELECT 
--     p.player_name,
--     t.team_name,
--     s.season_id,
--     gks.gk_games_starts,
--     gks.gk_save_pct,
--     gks.gk_saves,
--     gks.gk_shots_on_target_against
-- FROM pl_data.player_keeper_stats gks
-- JOIN pl_data.players p USING (player_season_id)
-- JOIN pl_data.teams t ON p.team_id = t.team_id
-- JOIN pl_data.seasons s ON p.season_id = s.season_id
-- WHERE gks.gk_games_starts >= 15
-- ORDER BY gks.gk_save_pct DESC
-- LIMIT 20;

-- Query 2: Elite shot-stoppers (PSxG analysis)
-- SELECT * FROM pl_data.v_elite_shot_stoppers
-- WHERE shot_stopping_quality = 'Elite'
-- ORDER BY gk_psxg_net_per90 ASC;

-- Query 3: Ball-playing vs Traditional keepers
-- SELECT 
--     keeper_style,
--     COUNT(*) as count,
--     AVG(gk_save_pct) as avg_save_pct,
--     AVG(gk_passes_length_avg) as avg_pass_length,
--     AVG(gk_def_actions_outside_pen_area_per90) as avg_sweeping
-- FROM pl_data.v_keeper_performance
-- WHERE gk_games >= 15
-- GROUP BY keeper_style;

-- Query 4: Best penalty savers
-- SELECT 
--     p.player_name,
--     t.team_name,
--     gks.gk_pens_att,
--     gks.gk_pens_saved,
--     gks.gk_pens_allowed,
--     gks.gk_pens_save_pct
-- FROM pl_data.player_keeper_stats gks
-- JOIN pl_data.players p USING (player_season_id)
-- JOIN pl_data.teams t ON p.team_id = t.team_id
-- WHERE gks.gk_pens_att >= 3  -- Faced at least 3 penalties
-- ORDER BY gks.gk_pens_save_pct DESC;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================
DO $$ 
BEGIN 
    RAISE NOTICE 'Successfully created player_keeper_stats table in pl_data schema';
    RAISE NOTICE '   - pl_data.player_keeper_stats (54 goalkeeper-specific columns)';
    RAISE NOTICE '   - pl_data.v_keeper_performance (performance summary view)';
    RAISE NOTICE '   - pl_data.v_elite_shot_stoppers (PSxG-based ranking view)';
    RAISE NOTICE '   - pl_data.v_keeper_stats_data_quality (completeness check)';
    RAISE NOTICE '';
    RAISE NOTICE 'Table structure:';
    RAISE NOTICE '   - Separate table for goalkeeper-only stats';
    RAISE NOTICE '   - Merges basic + advanced keeper statistics';
    RAISE NOTICE '   - One-to-one relationship with pl_data.players';
    RAISE NOTICE '';
    RAISE NOTICE 'Expected data:';
    RAISE NOTICE '   - ~60 goalkeeper records per season (20 teams × ~3 keepers)';
    RAISE NOTICE '   - ~240 total rows (4 complete seasons)';
    RAISE NOTICE '';
    RAISE NOTICE 'Performance:';
    RAISE NOTICE '   - 6 indexes for keeper-specific queries';
    RAISE NOTICE '   - 3 data views (performance, elite ranking, quality check)';
    RAISE NOTICE '';
    RAISE NOTICE 'Key Metrics:';
    RAISE NOTICE '   - Save pct: Elite >75, Average 70-75';
    RAISE NOTICE '   - Clean Sheets pct: Elite >40, Average 25-35';
    RAISE NOTICE '   - PSxG net/90: Elite <-0.10 (saves 0.1 goals per 90 above expected)';
    RAISE NOTICE '';
    RAISE NOTICE 'Next step: Run 05_create_indexes.sql';
END $$;