-- Small WC 2026 slice for ReadApiIntegrationTest. Mirrors what ml/pipeline/publish.py writes.
INSERT INTO ng.teams (code, name, confederation) VALUES
    ('BRA', 'Brazil', 'CONMEBOL'),
    ('ARG', 'Argentina', 'CONMEBOL'),
    ('ESP', 'Spain', 'UEFA'),
    ('CPV', 'Cape Verde', 'CAF'),
    ('SUI', 'Switzerland', 'UEFA'),
    ('COL', 'Colombia', 'CONMEBOL');

INSERT INTO ng.tournaments (id, name, competition_id, season_year, hosts, start_date, end_date) VALUES
    ('wc2026', 'FIFA World Cup 2026', 'fifa_world_cup', 2026, 'Canada, Mexico, United States',
     '2026-06-11', '2026-07-19');

INSERT INTO ng.matches (id, tournament_id, match_number, match_date, stage, home_team, away_team, neutral_venue,
                        home_goals, away_goals, winner, decided_on_penalties) VALUES
    (1, 'wc2026', 1, '2026-06-13', 'group', 'BRA', 'ARG', TRUE, 2, 1, 'BRA', FALSE),
    (2, 'wc2026', 2, '2026-06-15', 'group', 'ESP', 'CPV', TRUE, 0, 0, NULL, FALSE),
    (3, 'wc2026', 3, '2026-07-07', 'round_of_16', 'SUI', 'COL', TRUE, 0, 0, 'SUI', TRUE),
    (4, 'wc2026', 4, '2026-07-19', 'final', 'ESP', 'ARG', TRUE, NULL, NULL, NULL, FALSE);

INSERT INTO ng.model_runs (id, kind, trained_through, metrics, evaluation, published_at) VALUES
    ('old_run', 'match', '2026-06-01', '{"n_train": 100}', NULL, '2026-06-01T00:00:00Z'),
    ('20260722_002607', 'match', '2026-06-11', '{"n_train": 30417, "n_features": 123}',
     '{"scoring_mode": "shootout_credited", "overall": {"accuracy": 0.6923, "correct": 72, "total": 104}}',
     '2026-07-23T23:34:07Z'),
    ('shot_xg_20260628_010155', 'shot_xg', '2018-07-15', '{"n_train": 1624}', NULL, '2026-06-28T01:01:55Z');

INSERT INTO ng.predictions (model_run_id, match_id, p_home, p_draw, p_away, predicted_home_goals,
                            predicted_away_goals, home_xg, away_xg) VALUES
    ('20260722_002607', 1, 0.4427, 0.2732, 0.2841, 1, 1, 1.31, 1.12),
    ('20260722_002607', 2, 0.7664, 0.1769, 0.0567, 2, 0, 2.10, 0.45),
    ('20260722_002607', 3, 0.5600, 0.0000, 0.4400, NULL, NULL, NULL, NULL),
    ('20260722_002607', 4, 0.5100, 0.0000, 0.4900, 1, 1, 1.20, 1.15),
    ('old_run', 1, 0.2000, 0.3000, 0.5000, NULL, NULL, NULL, NULL);

INSERT INTO ng.team_elo (team_code, as_of_date, elo, model_run_id) VALUES
    ('BRA', '2017-11-10', 1900.0, '20260722_002607'),
    ('BRA', '2026-03-26', 1985.2, '20260722_002607'),
    ('BRA', '2026-06-13', 1990.5, '20260722_002607');

INSERT INTO ng.shots_xg_grid (model_run_id, distance_m, angle_deg, body_part, situation, p_goal) VALUES
    ('shot_xg_20260628_010155', 6, 0, 'foot', 'open_play', 0.42),
    ('shot_xg_20260628_010155', 20, 30, 'foot', 'open_play', 0.05);

INSERT INTO ng.penalty_aggregates (dataset, dimension, bucket, kicks, goals, conversion) VALUES
    ('penalty_kicks_v0', 'zone', 'top_left', 40, 34, 0.85),
    ('penalty_kicks_v0', 'zone', 'bottom_center', 30, 18, 0.60),
    ('penalty_kicks_v0', 'pressure', 'must_score', 25, 16, 0.64);
