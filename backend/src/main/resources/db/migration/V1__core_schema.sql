-- Neutral Ground core schema (schema "ng"; Flyway creates it via spring.flyway.schemas).
-- Replaces the Premier League era database/schema/*.sql (schema pl_data), which is legacy.
-- Rows are written by ml/pipeline/publish.py; the API only reads them.

CREATE TABLE teams (
    code          VARCHAR(3)   PRIMARY KEY CHECK (code ~ '^[A-Z]{3}$'),
    name          VARCHAR(80)  NOT NULL,
    confederation VARCHAR(10)  NOT NULL
        CHECK (confederation IN ('AFC', 'CAF', 'CONCACAF', 'CONMEBOL', 'OFC', 'UEFA'))
);

CREATE TABLE tournaments (
    id             VARCHAR(32)  PRIMARY KEY,             -- e.g. wc2026
    name           VARCHAR(120) NOT NULL,
    competition_id VARCHAR(40)  NOT NULL,                -- matches ml competition ids, e.g. fifa_world_cup
    season_year    INTEGER      NOT NULL,
    hosts          VARCHAR(200),
    start_date     DATE,
    end_date       DATE
);

CREATE TABLE matches (
    id               BIGSERIAL    PRIMARY KEY,
    tournament_id    VARCHAR(32)  NOT NULL REFERENCES tournaments (id) ON DELETE CASCADE,
    match_number     INTEGER      NOT NULL,              -- 1-based order within the tournament
    match_date       DATE         NOT NULL,
    stage            VARCHAR(20)  NOT NULL
        CHECK (stage IN ('group', 'round_of_32', 'round_of_16', 'quarter_final',
                         'semi_final', 'third_place', 'final')),
    home_team        VARCHAR(3)   NOT NULL REFERENCES teams (code),
    away_team        VARCHAR(3)   NOT NULL REFERENCES teams (code),
    neutral_venue    BOOLEAN      NOT NULL DEFAULT TRUE,
    -- Result columns stay NULL until the match is played. Goals include extra time.
    home_goals       INTEGER      CHECK (home_goals >= 0),
    away_goals       INTEGER      CHECK (away_goals >= 0),
    winner           VARCHAR(3)   REFERENCES teams (code), -- NULL for a group-stage draw
    decided_on_penalties BOOLEAN  NOT NULL DEFAULT FALSE,
    CONSTRAINT matches_distinct_teams CHECK (home_team <> away_team),
    CONSTRAINT matches_goals_together CHECK ((home_goals IS NULL) = (away_goals IS NULL)),
    CONSTRAINT matches_natural_key UNIQUE (tournament_id, match_date, home_team, away_team),
    CONSTRAINT matches_number_key UNIQUE (tournament_id, match_number)
);

CREATE INDEX matches_tournament_stage_idx ON matches (tournament_id, stage, match_date);
CREATE INDEX matches_home_team_idx ON matches (home_team);
CREATE INDEX matches_away_team_idx ON matches (away_team);

CREATE TABLE model_runs (
    id               VARCHAR(64)  PRIMARY KEY,           -- artifact dir name, e.g. 20260722_002607
    kind             VARCHAR(16)  NOT NULL CHECK (kind IN ('match', 'score', 'shot_xg', 'penalty')),
    trained_through  DATE,                               -- last date of training data (exclusive cutoff)
    metrics          JSONB        NOT NULL DEFAULT '{}'::jsonb, -- training-time metrics.json
    evaluation       JSONB,                              -- tournament evaluation metrics.json, if any
    notes            VARCHAR(500),
    published_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX model_runs_kind_published_idx ON model_runs (kind, published_at DESC);

CREATE TABLE predictions (
    id                   BIGSERIAL        PRIMARY KEY,
    model_run_id         VARCHAR(64)      NOT NULL REFERENCES model_runs (id) ON DELETE CASCADE,
    match_id             BIGINT           NOT NULL REFERENCES matches (id) ON DELETE CASCADE,
    p_home               DOUBLE PRECISION NOT NULL CHECK (p_home BETWEEN 0 AND 1),
    p_draw               DOUBLE PRECISION NOT NULL CHECK (p_draw BETWEEN 0 AND 1),
    p_away               DOUBLE PRECISION NOT NULL CHECK (p_away BETWEEN 0 AND 1),
    predicted_home_goals INTEGER          CHECK (predicted_home_goals >= 0),
    predicted_away_goals INTEGER          CHECK (predicted_away_goals >= 0),
    home_xg              DOUBLE PRECISION,
    away_xg              DOUBLE PRECISION,
    score_model_run_id   VARCHAR(64),                    -- score run that produced the scoreline, if any
    created_at           TIMESTAMPTZ      NOT NULL DEFAULT now(),
    CONSTRAINT predictions_probabilities_sum CHECK (abs(p_home + p_draw + p_away - 1) < 0.01),
    CONSTRAINT predictions_run_match_key UNIQUE (model_run_id, match_id)
);

CREATE INDEX predictions_match_idx ON predictions (match_id);

-- Pre-match Elo per team per date, exported from the match model's feature matrix.
CREATE TABLE team_elo (
    team_code    VARCHAR(3)       NOT NULL REFERENCES teams (code) ON DELETE CASCADE,
    as_of_date   DATE             NOT NULL,
    elo          DOUBLE PRECISION NOT NULL,
    model_run_id VARCHAR(64)      REFERENCES model_runs (id) ON DELETE SET NULL,
    PRIMARY KEY (team_code, as_of_date)
);

-- Precomputed shot xG grid for the frontend xG lab (XG-04 xg_grid.json).
CREATE TABLE shots_xg_grid (
    id           BIGSERIAL        PRIMARY KEY,
    model_run_id VARCHAR(64)      NOT NULL REFERENCES model_runs (id) ON DELETE CASCADE,
    distance_m   DOUBLE PRECISION NOT NULL CHECK (distance_m >= 0),
    angle_deg    DOUBLE PRECISION NOT NULL CHECK (angle_deg BETWEEN 0 AND 180),
    body_part    VARCHAR(20)      NOT NULL DEFAULT 'any',
    situation    VARCHAR(20)      NOT NULL DEFAULT 'any',
    p_goal       DOUBLE PRECISION NOT NULL CHECK (p_goal BETWEEN 0 AND 1),
    CONSTRAINT shots_xg_grid_cell_key UNIQUE (model_run_id, distance_m, angle_deg, body_part, situation)
);

-- Penalty conversion aggregates for the frontend penalties lab (PEN-03 penalty_aggregates.json).
CREATE TABLE penalty_aggregates (
    id           BIGSERIAL        PRIMARY KEY,
    dataset      VARCHAR(64)      NOT NULL,              -- e.g. penalty_kicks_v0
    dimension    VARCHAR(32)      NOT NULL,              -- zone, foot_side, shootout_order, pressure, ...
    bucket       VARCHAR(48)      NOT NULL,              -- e.g. top_left, 1, must_score
    kicks        INTEGER          NOT NULL CHECK (kicks >= 0),
    goals        INTEGER          NOT NULL CHECK (goals >= 0 AND goals <= kicks),
    conversion   DOUBLE PRECISION NOT NULL CHECK (conversion BETWEEN 0 AND 1),
    CONSTRAINT penalty_aggregates_key UNIQUE (dataset, dimension, bucket)
);
