-- ============================================================================
-- File: 03_create_player_stats.sql
-- Description: Creates player season statistics fact table (WIDE TABLE)
-- Dependencies: 01_create_dimensions.sql (requires players table)
-- Schema: pl_data
-- ============================================================================

-- Set search path to pl_data schema
SET search_path TO pl_data, public;

-- ============================================================================
-- FACT TABLE: player_season_stats
-- Description: Comprehensive player statistics aggregated by season
-- 
-- DESIGN DECISION: Wide Table (130+ columns) vs. Normalized (9 separate tables)
-- We chose WIDE TABLE for ML optimization:
--   ✅ Single query gets all features for model training
--   ✅ No complex joins needed (faster queries)
--   ✅ Better for pandas DataFrames (one df.read_sql())
--   ✅ Easier feature correlation analysis
--   ❌ Many NULLs for goalkeepers (acceptable trade-off)
--
-- This table merges data from 9 CSV file types:
--   1. player_standard_stats       (26 columns)
--   2. player_shooting_stats       (13 columns)
--   3. player_passing_stats        (20 columns)
--   4. player_passing_types_stats  (12 columns)
--   5. player_gca_stats            (18 columns)
--   6. player_defense_stats        (17 columns)
--   7. player_possession_stats     (23 columns)
--   TOTAL: 129 statistical columns + metadata
--
-- Note: Goalkeeper-specific stats go in separate table (04_create_keeper_stats.sql)
-- ============================================================================

DROP TABLE IF EXISTS pl_data.player_season_stats CASCADE;

CREATE TABLE pl_data.player_season_stats (
    -- ========================================================================
    -- PRIMARY KEY & FOREIGN KEY
    -- ========================================================================
    player_season_id INTEGER PRIMARY KEY,     -- References pl_data.players(player_season_id)
    
    -- ========================================================================
    -- SECTION 1: STANDARD STATS (from player_standard_stats.csv)
    -- Core performance metrics: games, goals, assists, cards, xG
    -- ========================================================================
    
    -- Playing time
    games INTEGER,                            -- Total games appeared in (including sub appearances)
    games_starts INTEGER,                     -- Games started (in starting XI)
    minutes INTEGER,                          -- Total minutes played (e.g., 2534)
    minutes_90s DECIMAL(5,2),                 -- Minutes expressed as 90-minute units (e.g., 28.2)
    
    -- Goal contributions
    goals DECIMAL(4,1),                       -- Total goals scored (can have .5 for own goals against)
    assists DECIMAL(4,1),                     -- Total assists provided
    goals_assists DECIMAL(4,1),               -- Goals + Assists combined
    goals_pens DECIMAL(4,1),                  -- Goals excluding penalties
    pens_made DECIMAL(4,1),                   -- Penalties scored
    pens_att DECIMAL(4,1),                    -- Penalties attempted
    
    -- Discipline
    cards_yellow DECIMAL(4,1),                -- Yellow cards received
    cards_red DECIMAL(4,1),                   -- Red cards received
    
    -- Expected metrics (xG = Expected Goals based on shot quality)
    xg DECIMAL(5,2),                          -- Expected goals (total)
    npxg DECIMAL(5,2),                        -- Non-penalty expected goals
    xg_assist DECIMAL(5,2),                   -- Expected assists (xA)
    npxg_xg_assist DECIMAL(5,2),              -- Non-penalty xG + xA
    
    -- Progressive play (moving ball towards opponent goal)
    progressive_carries DECIMAL(5,2),         -- Carries that move ball significantly forward
    progressive_passes DECIMAL(5,2),          -- Passes that move ball significantly forward
    progressive_passes_received DECIMAL(5,2), -- Times player received progressive pass
    
    -- Per 90 minute rates (normalized for playing time)
    goals_per90 DECIMAL(4,2),                 -- Goals per 90 minutes played
    assists_per90 DECIMAL(4,2),               -- Assists per 90 minutes
    goals_assists_per90 DECIMAL(4,2),         -- Goal contributions per 90
    goals_pens_per90 DECIMAL(4,2),            -- Non-penalty goals per 90
    goals_assists_pens_per90 DECIMAL(4,2),    -- Non-penalty goal contributions per 90
    xg_per90 DECIMAL(4,2),                    -- Expected goals per 90
    xg_assist_per90 DECIMAL(4,2),             -- Expected assists per 90
    xg_xg_assist_per90 DECIMAL(4,2),          -- Total expected contributions per 90
    npxg_per90 DECIMAL(4,2),                  -- Non-penalty xG per 90
    npxg_xg_assist_per90 DECIMAL(4,2),        -- Non-penalty xG + xA per 90
    
    -- ========================================================================
    -- SECTION 2: SHOOTING STATS (from player_shooting_stats.csv)
    -- Shot quantity, quality, and accuracy metrics
    -- ========================================================================
    
    -- Shot volume
    shots INTEGER,                            -- Total shots taken
    shots_on_target INTEGER,                  -- Shots on target (forcing save or goal)
    shots_on_target_pct DECIMAL(5,2),         -- % of shots on target (accuracy)
    
    -- Shot frequency
    shots_per90 DECIMAL(4,2),                 -- Shots taken per 90 minutes
    shots_on_target_per90 DECIMAL(4,2),       -- Shots on target per 90
    
    -- Shooting efficiency
    goals_per_shot DECIMAL(4,2),              -- Conversion rate (goals/shots)
    goals_per_shot_on_target DECIMAL(4,2),    -- Conversion rate from shots on target
    
    -- Shot characteristics
    average_shot_distance DECIMAL(5,2),       -- Average distance from goal in yards
    shots_free_kicks INTEGER,                 -- Shots from direct free kicks
    
    -- Expected goals (xG) detail
    npxg_per_shot DECIMAL(4,2),               -- Non-penalty xG per shot (shot quality)
    xg_net DECIMAL(5,2),                      -- Goals - xG (overperformance/underperformance)
    npxg_net DECIMAL(5,2),                    -- Non-penalty goals - npxG difference
    
    -- ========================================================================
    -- SECTION 3: PASSING STATS (from player_passing_stats.csv)
    -- Pass completion, distance, and creativity metrics
    -- ========================================================================
    
    -- Pass volume and accuracy
    passes_completed INTEGER,                 -- Total passes completed
    passes INTEGER,                           -- Total passes attempted
    passes_pct DECIMAL(5,2),                  -- Pass completion percentage
    
    -- Pass distance
    passes_total_distance INTEGER,            -- Total yards of all completed passes
    passes_progressive_distance INTEGER,      -- Total yards of progressive passes
    
    -- Short passes (< 15 yards)
    passes_completed_short INTEGER,           -- Short passes completed
    passes_short INTEGER,                     -- Short passes attempted
    passes_pct_short DECIMAL(5,2),            -- Short pass completion %
    
    -- Medium passes (15-30 yards)
    passes_completed_medium INTEGER,          -- Medium passes completed
    passes_medium INTEGER,                    -- Medium passes attempted
    passes_pct_medium DECIMAL(5,2),           -- Medium pass completion %
    
    -- Long passes (> 30 yards)
    passes_completed_long INTEGER,            -- Long passes completed
    passes_long INTEGER,                      -- Long passes attempted
    passes_pct_long DECIMAL(5,2),             -- Long pass completion %
    
    -- Creativity metrics
    pass_xa DECIMAL(5,2),                     -- Expected assisted goals (pass xA)
    xg_assist_net DECIMAL(5,2),               -- Assists - xA (over/underperformance)
    assisted_shots INTEGER,                   -- Passes leading to shots
    passes_into_final_third INTEGER,          -- Passes into attacking third
    passes_into_penalty_area INTEGER,         -- Passes into penalty box
    crosses_into_penalty_area INTEGER,        -- Crosses into penalty box
    
    -- ========================================================================
    -- SECTION 4: PASSING TYPES (from player_passing_types_stats.csv)
    -- Breakdown of pass types: live, dead ball, crosses, corners
    -- ========================================================================
    
    -- Pass situation types
    passes_live INTEGER,                      -- Passes attempted from open play
    passes_dead INTEGER,                      -- Passes from dead ball situations
    passes_free_kicks INTEGER,                -- Passes from free kicks
    
    -- Special pass types
    through_balls INTEGER,                    -- Through balls attempted
    passes_switches INTEGER,                  -- Switches of play (diagonal/long)
    crosses INTEGER,                          -- Crosses attempted
    throw_ins INTEGER,                        -- Throw-ins taken
    
    -- Corner kicks
    corner_kicks INTEGER,                     -- Total corner kicks taken
    corner_kicks_in INTEGER,                  -- In-swinging corners
    corner_kicks_out INTEGER,                 -- Out-swinging corners
    corner_kicks_straight INTEGER,            -- Straight corners
    
    -- Pass outcomes
    passes_offsides INTEGER,                  -- Passes resulting in offside
    passes_blocked INTEGER,                   -- Passes blocked by opponent
    
    -- ========================================================================
    -- SECTION 5: GOAL & SHOT CREATION (from player_gca_stats.csv)
    -- Shot-Creating Actions (SCA) and Goal-Creating Actions (GCA)
    -- These are KEY playmaking metrics
    -- ========================================================================
    
    -- Shot-Creating Actions (SCA): Actions leading to shots
    sca INTEGER,                              -- Total shot-creating actions
    sca_per90 DECIMAL(4,2),                   -- SCA per 90 minutes (key creativity metric)
    
    -- SCA breakdown by action type
    sca_passes_live INTEGER,                  -- SCA from live-ball passes
    sca_passes_dead INTEGER,                  -- SCA from dead-ball passes (FK, corners)
    sca_take_ons INTEGER,                     -- SCA from successful dribbles
    sca_shots INTEGER,                        -- SCA from shots leading to another shot
    sca_fouled INTEGER,                       -- SCA from drawing fouls
    sca_defense INTEGER,                      -- SCA from defensive actions
    
    -- Goal-Creating Actions (GCA): Actions directly leading to goals
    gca INTEGER,                              -- Total goal-creating actions
    gca_per90 DECIMAL(4,2),                   -- GCA per 90 minutes (elite playmaker metric)
    
    -- GCA breakdown by action type
    gca_passes_live INTEGER,                  -- GCA from live-ball passes
    gca_passes_dead INTEGER,                  -- GCA from dead-ball passes
    gca_take_ons INTEGER,                     -- GCA from successful dribbles
    gca_shots INTEGER,                        -- GCA from shots (rebounds, deflections)
    gca_fouled INTEGER,                       -- GCA from drawing fouls leading to goals
    gca_defense INTEGER,                      -- GCA from defensive actions
    
    -- ========================================================================
    -- SECTION 6: DEFENSIVE STATS (from player_defense_stats.csv)
    -- Tackles, interceptions, blocks, clearances
    -- ========================================================================
    
    -- Tackles
    tackles INTEGER,                          -- Total tackles attempted
    tackles_won INTEGER,                      -- Successful tackles
    tackles_def_3rd INTEGER,                  -- Tackles in defensive third
    tackles_mid_3rd INTEGER,                  -- Tackles in middle third
    tackles_att_3rd INTEGER,                  -- Tackles in attacking third
    
    -- Challenges (50/50 battles)
    challenge_tackles INTEGER,                -- Tackles during 50/50 challenges
    challenges INTEGER,                       -- Total challenges contested
    challenge_tackles_pct DECIMAL(5,2),       -- % of challenges won
    challenges_lost INTEGER,                  -- Challenges lost
    
    -- Blocks and interceptions
    blocks INTEGER,                           -- Total blocks (shots + passes)
    blocked_shots INTEGER,                    -- Shots blocked
    blocked_passes INTEGER,                   -- Passes blocked
    interceptions INTEGER,                    -- Passes intercepted
    tackles_interceptions INTEGER,            -- Tackles + Interceptions combined
    
    -- Clearances and errors
    clearances INTEGER,                       -- Clearances (defensive actions)
    errors INTEGER,                           -- Errors leading to opponent shot
    
    -- ========================================================================
    -- SECTION 7: POSSESSION STATS (from player_possession_stats.csv)
    -- Touches, dribbles, carries (ball progression while dribbling)
    -- ========================================================================
    
    -- Touch volume and location
    touches INTEGER,                          -- Total touches on the ball
    touches_def_pen_area INTEGER,             -- Touches in own penalty area
    touches_def_3rd INTEGER,                  -- Touches in defensive third
    touches_mid_3rd INTEGER,                  -- Touches in middle third
    touches_att_3rd INTEGER,                  -- Touches in attacking third
    touches_att_pen_area INTEGER,             -- Touches in opponent's penalty area
    touches_live_ball INTEGER,                -- Touches of live ball (excluding restarts)
    
    -- Dribbles (take-ons)
    take_ons INTEGER,                         -- Dribbles attempted
    take_ons_won INTEGER,                     -- Successful dribbles
    take_ons_won_pct DECIMAL(5,2),            -- Dribble success rate %
    take_ons_tackled INTEGER,                 -- Times tackled during dribble
    take_ons_tackled_pct DECIMAL(5,2),        -- % of dribbles where tackled
    
    -- Carries (moving with the ball via dribbling)
    carries INTEGER,                          -- Total ball carries
    carries_distance INTEGER,                 -- Total carry distance in yards
    carries_progressive_distance INTEGER,     -- Distance carried towards goal
    progressive_carries_poss INTEGER,         -- Carries moving ball significantly forward
    carries_into_final_third INTEGER,         -- Carries into attacking third
    carries_into_penalty_area INTEGER,        -- Carries into penalty box
    
    -- Ball control
    miscontrols INTEGER,                      -- Times player miscontrolled ball
    dispossessed INTEGER,                     -- Times player lost possession
    
    -- Receiving
    passes_received INTEGER,                  -- Total passes received
    progressive_passes_received_poss INTEGER, -- Progressive passes received
    
    -- ========================================================================
    -- METADATA
    -- ========================================================================
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- ========================================================================
    -- FOREIGN KEY CONSTRAINTS
    -- ========================================================================
    CONSTRAINT fk_player_stats_player FOREIGN KEY (player_season_id) 
        REFERENCES pl_data.players(player_season_id) 
        ON DELETE CASCADE,
    
    -- ========================================================================
    -- DATA INTEGRITY CONSTRAINTS
    -- ========================================================================
    
    -- Games started cannot exceed games played
    CONSTRAINT check_games_starts CHECK (games_starts IS NULL OR games_starts <= games),
    
    -- Minutes must be non-negative
    CONSTRAINT check_minutes CHECK (minutes IS NULL OR minutes >= 0),
    
    -- Shots on target cannot exceed total shots
    CONSTRAINT check_shots_on_target CHECK (
        shots_on_target IS NULL OR shots IS NULL OR shots_on_target <= shots
    ),
    
    -- Passes completed cannot exceed passes attempted
    CONSTRAINT check_passes_completed CHECK (
        passes_completed IS NULL OR passes IS NULL OR passes_completed <= passes
    ),
    
    -- Percentage values must be between 0 and 100
    CONSTRAINT check_percentages CHECK (
        (shots_on_target_pct IS NULL OR (shots_on_target_pct >= 0 AND shots_on_target_pct <= 100)) AND
        (passes_pct IS NULL OR (passes_pct >= 0 AND passes_pct <= 100)) AND
        (passes_pct_short IS NULL OR (passes_pct_short >= 0 AND passes_pct_short <= 100)) AND
        (passes_pct_medium IS NULL OR (passes_pct_medium >= 0 AND passes_pct_medium <= 100)) AND
        (passes_pct_long IS NULL OR (passes_pct_long >= 0 AND passes_pct_long <= 100)) AND
        (challenge_tackles_pct IS NULL OR (challenge_tackles_pct >= 0 AND challenge_tackles_pct <= 100)) AND
        (take_ons_won_pct IS NULL OR (take_ons_won_pct >= 0 AND take_ons_won_pct <= 100)) AND
        (take_ons_tackled_pct IS NULL OR (take_ons_tackled_pct >= 0 AND take_ons_tackled_pct <= 100))
    ),
    
    -- Cards must be non-negative
    CONSTRAINT check_cards CHECK (
        (cards_yellow IS NULL OR cards_yellow >= 0) AND
        (cards_red IS NULL OR cards_red >= 0)
    ),
    
    -- Tackles won cannot exceed tackles attempted
    CONSTRAINT check_tackles_won CHECK (
        tackles_won IS NULL OR tackles IS NULL OR tackles_won <= tackles
    )
);

-- ============================================================================
-- TABLE COMMENTS (Documentation)
-- ============================================================================
COMMENT ON TABLE pl_data.player_season_stats IS 
'Comprehensive player statistics aggregated by season. Wide table (130+ columns) combining 7 stat categories for ML optimization.';

COMMENT ON COLUMN pl_data.player_season_stats.player_season_id IS 
'Foreign key to pl_data.players. One row per player per season.';

-- Standard stats comments
COMMENT ON COLUMN pl_data.player_season_stats.minutes_90s IS 
'Minutes played expressed as 90-minute units. Used for per-90 calculations.';

COMMENT ON COLUMN pl_data.player_season_stats.xg IS 
'Expected Goals: Statistical measure of shot quality. Higher = better chances created.';

COMMENT ON COLUMN pl_data.player_season_stats.npxg IS 
'Non-penalty xG: Expected goals excluding penalties. Better measure of open-play finishing.';

COMMENT ON COLUMN pl_data.player_season_stats.progressive_carries IS 
'Carries that move ball ≥10 yards closer to opponent goal. Measure of ball progression.';

-- Shooting stats comments
COMMENT ON COLUMN pl_data.player_season_stats.xg_net IS 
'Goals minus xG. Positive = overperforming expectations, Negative = underperforming.';

COMMENT ON COLUMN pl_data.player_season_stats.npxg_per_shot IS 
'Non-penalty xG per shot. Measure of shot quality (higher = taking better chances).';

-- Passing stats comments
COMMENT ON COLUMN pl_data.player_season_stats.pass_xa IS 
'Expected Assisted Goals (xA): Quality of passes that led to shots.';

-- GCA comments
COMMENT ON COLUMN pl_data.player_season_stats.sca IS 
'Shot-Creating Actions: Two offensive actions leading to a shot (key creativity metric).';

COMMENT ON COLUMN pl_data.player_season_stats.gca IS 
'Goal-Creating Actions: Two offensive actions leading directly to a goal (elite playmaker metric).';

COMMENT ON COLUMN pl_data.player_season_stats.sca_per90 IS 
'SCA per 90 minutes. Values >5.0 indicate elite creative players.';

COMMENT ON COLUMN pl_data.player_season_stats.gca_per90 IS 
'GCA per 90 minutes. Values >0.5 indicate top-tier playmakers.';

-- Defensive stats comments
COMMENT ON COLUMN pl_data.player_season_stats.tackles_interceptions IS 
'Combined tackles + interceptions. Common defensive metric.';

-- Possession stats comments
COMMENT ON COLUMN pl_data.player_season_stats.carries IS 
'Number of times player moved ≥5 yards with ball. Measure of ball-carrying ability.';

COMMENT ON COLUMN pl_data.player_season_stats.take_ons IS 
'Dribbles attempted (1v1 situations). Measure of dribbling willingness.';

COMMENT ON COLUMN pl_data.player_season_stats.take_ons_won_pct IS 
'Dribble success rate. Elite dribblers: >60%, Average: 40-50%.';

-- ============================================================================
-- INDEXES FOR QUERY PERFORMANCE
-- ============================================================================

-- Foreign key index (automatically used in joins)
CREATE INDEX idx_player_stats_player_season ON pl_data.player_season_stats(player_season_id);

-- Filtering indexes for common ML feature queries
CREATE INDEX idx_player_stats_minutes ON pl_data.player_season_stats(minutes_90s) 
    WHERE minutes_90s >= 5.0;  -- Players with significant playing time

CREATE INDEX idx_player_stats_goals ON pl_data.player_season_stats(goals) 
    WHERE goals > 0;  -- Goal scorers only

CREATE INDEX idx_player_stats_assists ON pl_data.player_season_stats(assists) 
    WHERE assists > 0;  -- Assist providers only

-- Position-specific performance indexes (requires joining with players table)
-- These support queries like "Top scorers among midfielders"
CREATE INDEX idx_player_stats_xg ON pl_data.player_season_stats(xg DESC NULLS LAST);
CREATE INDEX idx_player_stats_npxg ON pl_data.player_season_stats(npxg DESC NULLS LAST);
CREATE INDEX idx_player_stats_sca_per90 ON pl_data.player_season_stats(sca_per90 DESC NULLS LAST);
CREATE INDEX idx_player_stats_gca_per90 ON pl_data.player_season_stats(gca_per90 DESC NULLS LAST);

-- ============================================================================
-- DATA QUALITY VIEWS
-- ============================================================================

-- View: Player statistics summary with position context
CREATE OR REPLACE VIEW pl_data.v_player_stats_summary AS
SELECT 
    p.player_season_id,
    p.player_name,
    p.position,
    t.team_name,
    s.season_id,
    pss.games,
    pss.minutes_90s,
    pss.goals,
    pss.assists,
    pss.xg,
    pss.npxg,
    pss.sca_per90,
    pss.gca_per90,
    pss.passes_pct,
    pss.take_ons_won_pct
FROM pl_data.player_season_stats pss
JOIN pl_data.players p USING (player_season_id)
JOIN pl_data.teams t ON p.team_id = t.team_id
JOIN pl_data.seasons s ON p.season_id = s.season_id
WHERE pss.minutes_90s >= 5.0  -- Filter out players with minimal playing time
ORDER BY s.season_id DESC, pss.goals DESC;

COMMENT ON VIEW pl_data.v_player_stats_summary IS 
'Player statistics with player/team/season context. Filtered to players with 5+ ninety-minute equivalents.';

-- View: Data completeness check
CREATE OR REPLACE VIEW pl_data.v_player_stats_data_quality AS
SELECT 
    s.season_id,
    COUNT(*) as total_player_records,
    
    -- Standard stats completeness
    COUNT(pss.games) as has_games,
    COUNT(pss.goals) as has_goals,
    COUNT(pss.xg) as has_xg,
    
    -- Shooting stats completeness
    COUNT(pss.shots) as has_shots,
    COUNT(pss.shots_on_target) as has_shots_on_target,
    
    -- Passing stats completeness
    COUNT(pss.passes) as has_passes,
    COUNT(pss.pass_xa) as has_pass_xa,
    
    -- GCA stats completeness
    COUNT(pss.sca) as has_sca,
    COUNT(pss.gca) as has_gca,
    
    -- Defensive stats completeness
    COUNT(pss.tackles) as has_tackles,
    COUNT(pss.interceptions) as has_interceptions,
    
    -- Possession stats completeness
    COUNT(pss.touches) as has_touches,
    COUNT(pss.carries) as has_carries
    
FROM pl_data.player_season_stats pss
JOIN pl_data.players p USING (player_season_id)
JOIN pl_data.seasons s ON p.season_id = s.season_id
GROUP BY s.season_id
ORDER BY s.season_id;

COMMENT ON VIEW pl_data.v_player_stats_data_quality IS 
'Data completeness check: Shows count of non-NULL values for key statistics per season.';

-- ============================================================================
-- EXAMPLE QUERIES (for documentation/testing)
-- ============================================================================

-- Query 1: Top scorers by season (min 900 minutes played)
-- SELECT 
--     p.player_name,
--     t.team_name,
--     s.season_id,
--     pss.goals,
--     pss.xg,
--     pss.xg_net,
--     pss.goals_per90
-- FROM pl_data.player_season_stats pss
-- JOIN pl_data.players p USING (player_season_id)
-- JOIN pl_data.teams t ON p.team_id = t.team_id
-- JOIN pl_data.seasons s ON p.season_id = s.season_id
-- WHERE pss.minutes >= 900
-- ORDER BY pss.goals DESC
-- LIMIT 20;

-- Query 2: Best playmakers (highest SCA per 90)
-- SELECT 
--     p.player_name,
--     p.position,
--     t.team_name,
--     pss.sca_per90,
--     pss.gca_per90,
--     pss.assists,
--     pss.xg_assist
-- FROM pl_data.player_season_stats pss
-- JOIN pl_data.players p USING (player_season_id)
-- JOIN pl_data.teams t ON p.team_id = t.team_id
-- WHERE pss.minutes_90s >= 10.0
-- ORDER BY pss.sca_per90 DESC
-- LIMIT 20;

-- Query 3: Best dribblers (high take-on success rate)
-- SELECT 
--     p.player_name,
--     p.position,
--     pss.take_ons,
--     pss.take_ons_won,
--     pss.take_ons_won_pct,
--     pss.carries_into_penalty_area
-- FROM pl_data.player_season_stats pss
-- JOIN pl_data.players p USING (player_season_id)
-- WHERE pss.take_ons >= 20  -- Min attempts threshold
-- ORDER BY pss.take_ons_won_pct DESC
-- LIMIT 20;

-- Query 4: Defensive stalwarts
-- SELECT 
--     p.player_name,
--     p.position,
--     t.team_name,
--     pss.tackles,
--     pss.interceptions,
--     pss.tackles_interceptions,
--     pss.blocks,
--     pss.clearances
-- FROM pl_data.player_season_stats pss
-- JOIN pl_data.players p USING (player_season_id)
-- JOIN pl_data.teams t ON p.team_id = t.team_id
-- WHERE p.position IN ('DF', 'MF')
--   AND pss.minutes_90s >= 15.0
-- ORDER BY pss.tackles_interceptions DESC
-- LIMIT 20;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================
DO $$ 
BEGIN 
    RAISE NOTICE 'Successfully created player_season_stats table in pl_data schema';
    RAISE NOTICE '   - pl_data.player_season_stats (130+ statistical columns)';
    RAISE NOTICE '   - pl_data.v_player_stats_summary (filtered summary view)';
    RAISE NOTICE '   - pl_data.v_player_stats_data_quality (completeness check)';
    RAISE NOTICE '';
    RAISE NOTICE 'Table structure:';
    RAISE NOTICE '   - WIDE TABLE design (all stats merged)';
    RAISE NOTICE '   - 7 stat categories combined into one table';
    RAISE NOTICE '   - Optimized for ML feature extraction';
    RAISE NOTICE '';
    RAISE NOTICE 'Expected data:';
    RAISE NOTICE '   - ~2,500 player records per season';
    RAISE NOTICE '   - ~10,000 total rows (4 complete seasons)';
    RAISE NOTICE '';
    RAISE NOTICE 'Performance:';
    RAISE NOTICE '   - 9 indexes created for common queries';
    RAISE NOTICE '   - Data quality views for monitoring';
    RAISE NOTICE '';
    RAISE NOTICE 'Note: Goalkeepers will have many NULLs (expected)';
    RAISE NOTICE '    Goalkeeper-specific stats go in separate table';
    RAISE NOTICE '';
    RAISE NOTICE 'Next step: Run 04_create_keeper_stats.sql';
END $$;