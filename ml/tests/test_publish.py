"""Row builders of ml.pipeline.publish. No database or trained artifacts needed."""

import pandas as pd
import pytest

from ml.pipeline.publish import (
    PublishError,
    build_elo,
    build_matches,
    build_penalty_aggregates,
    build_predictions,
    build_teams,
    build_xg_grid,
)

FIXTURES = [
    {"match_date": "2026-06-11", "home_team": "KOR", "away_team": "CZE", "is_neutral_venue": "True",
     "competition_id": "fifa_world_cup", "competition_stage": "group"},
    {"match_date": "2026-06-12", "home_team": "CAN", "away_team": "BIH", "is_neutral_venue": "False",
     "competition_id": "fifa_world_cup", "competition_stage": "group"},
    {"match_date": "2026-07-07", "home_team": "SUI", "away_team": "COL", "is_neutral_venue": "True",
     "competition_id": "fifa_world_cup", "competition_stage": "round_of_16"},
    {"match_date": "2026-07-19", "home_team": "ESP", "away_team": "ARG", "is_neutral_venue": "True",
     "competition_id": "fifa_world_cup", "competition_stage": "final"},
]
RESULTS = [
    {"match_date": "2026-06-11", "home_team": "KOR", "away_team": "CZE", "goals_for": "2", "goals_against": "1",
     "result": "W", "competition_stage": "group", "winner": "KOR"},
    {"match_date": "2026-06-12", "home_team": "CAN", "away_team": "BIH", "goals_for": "1", "goals_against": "1",
     "result": "D", "competition_stage": "group", "winner": ""},
    {"match_date": "2026-07-07", "home_team": "SUI", "away_team": "COL", "goals_for": "0", "goals_against": "0",
     "result": "D", "competition_stage": "round_of_16", "winner": "SUI"},
]


def _pred(h, a, ph=0.5, pd_=0.3, pa=0.2):
    return {"home_team": h, "away_team": a, "p_home_win": ph, "p_draw": pd_, "p_away_win": pa}


def test_build_teams_dedupes_aliases():
    rows = [
        {"alias": "Brazil", "team_id": "BRA", "full_name": "Brazil", "confederation": "CONMEBOL"},
        {"alias": "Brasil", "team_id": "BRA", "full_name": "Brazil", "confederation": "CONMEBOL"},
        {"alias": "Spain", "team_id": "ESP", "full_name": "Spain", "confederation": "UEFA"},
    ]
    assert build_teams(rows) == [("BRA", "Brazil", "CONMEBOL"), ("ESP", "Spain", "UEFA")]


def test_build_matches_joins_results_and_detects_shootouts():
    matches = build_matches(FIXTURES, RESULTS)
    kor, can, sui, final = matches
    assert [m.match_number for m in matches] == [1, 2, 3, 4]
    assert (kor.home_goals, kor.away_goals, kor.winner, kor.decided_on_penalties) == (2, 1, "KOR", False)
    assert can.neutral_venue is False
    assert (can.winner, can.decided_on_penalties) == (None, False)
    assert (sui.winner, sui.decided_on_penalties) == ("SUI", True)
    assert final.home_goals is None and final.winner is None


def test_build_matches_rejects_orphan_result_and_bad_stage():
    with pytest.raises(PublishError):
        build_matches(FIXTURES, RESULTS + [{**RESULTS[0], "home_team": "BRA"}])
    with pytest.raises(PublishError):
        build_matches([{**FIXTURES[0], "competition_stage": "semis"}])


def test_build_matches_rejects_group_shootout():
    with pytest.raises(PublishError):
        build_matches(FIXTURES[:2], [RESULTS[0], {**RESULTS[1], "winner": "CAN"}])


def test_build_predictions_pairs_by_position_with_team_check():
    matches = build_matches(FIXTURES)
    preds = build_predictions(matches, [_pred(m.home_team, m.away_team) for m in matches])
    assert preds[2].match_key == ("2026-07-07", "SUI", "COL")

    with pytest.raises(PublishError):
        build_predictions(matches, [_pred("CZE", "KOR")] + [_pred(m.home_team, m.away_team) for m in matches[1:]])
    with pytest.raises(PublishError):
        build_predictions(matches, [_pred(m.home_team, m.away_team) for m in matches[:-1]])


def test_build_predictions_rejects_non_distribution():
    matches = build_matches(FIXTURES[:1])
    with pytest.raises(PublishError):
        build_predictions(matches, [_pred("KOR", "CZE", 0.6, 0.6, 0.2)])


def test_build_predictions_attaches_scores():
    matches = build_matches(FIXTURES[:1])
    scores = [{"home_team": "KOR", "away_team": "CZE", "predicted_home_goals": 1, "predicted_away_goals": 0,
               "home_xg": 1.234567, "away_xg": 0.8}]
    (p,) = build_predictions(matches, [_pred("KOR", "CZE")], scores)
    assert (p.predicted_home_goals, p.predicted_away_goals, p.home_xg) == (1, 0, 1.2346)


def test_build_elo_filters_dates_and_teams():
    features = pd.DataFrame({
        "match_date": pd.to_datetime(["2009-05-01", "2018-06-14", "2026-06-11"]),
        "home_team": ["BRA", "RUS", "KOR"],
        "away_team": ["ARG", "KSA", "CZE"],
        "home_elo": [1800.0, 1500.0, 1700.0],
        "away_elo": [1790.0, float("nan"), 1650.04],
    })
    rows = build_elo(features, "2010-01-01", {"RUS", "KSA", "KOR", "CZE"})
    assert rows == [("CZE", "2026-06-11", 1650.04), ("KOR", "2026-06-11", 1700.0), ("RUS", "2018-06-14", 1500.0)]


def test_build_xg_grid_and_penalties():
    run_id, cells = build_xg_grid({"model_run_id": "shot-1", "cells": [{"distance_m": 6, "angle_deg": 0,
                                                                         "p_goal": 0.4}]})
    assert run_id == "shot-1"
    assert cells[0]["body_part"] == "any"

    name, rows = build_penalty_aggregates({"aggregates": [{"dimension": "zone", "bucket": "top_left",
                                                           "kicks": 4, "goals": 3}]})
    assert name == "penalty_kicks_v0"
    assert rows[0]["conversion"] == 0.75
