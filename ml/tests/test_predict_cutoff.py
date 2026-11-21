"""predict.py must never read a team's form from matches on/after the fixture date."""

import pandas as pd

from ml.pipeline.predict import _fixture_feature_row, _team_latest_vector, fixture_cutoffs

COLS = ["home_elo", "away_elo", "diff_elo"]


def _features():
    return pd.DataFrame({
        "match_date": pd.to_datetime(["2026-06-01", "2026-06-15", "2026-07-19"]),
        "home_team": ["ARG", "ARG", "ESP"],
        "away_team": ["BRA", "MEX", "ARG"],
        "home_elo": [2000.0, 2030.0, 2050.0],
        "away_elo": [1990.0, 1800.0, 2100.0],
        "diff_elo": [10.0, 230.0, -50.0],
    })


def test_latest_vector_respects_cutoff():
    f = _features()
    # Without a cutoff, the final's rating is used
    assert _team_latest_vector(f, COLS, "ARG")["elo"] == 2100.0
    assert _team_latest_vector(f, COLS, "ARG", pd.Timestamp("2026-06-15"))["elo"] == 2000.0
    assert _team_latest_vector(f, COLS, "ARG", pd.Timestamp("2026-06-01")) == {}


def test_fixture_cutoffs_use_match_date_capped_by_as_of():
    fx = pd.DataFrame({"match_date": ["2026-06-15", "2026-07-19"],
                       "home_team": ["ARG", "ESP"], "away_team": ["MEX", "ARG"]})
    assert fixture_cutoffs(fx) == [pd.Timestamp("2026-06-15"), pd.Timestamp("2026-07-19")]
    assert fixture_cutoffs(fx, "2026-06-11") == [pd.Timestamp("2026-06-11")] * 2
    row = _fixture_feature_row(_features(), COLS, "ESP", "ARG", pd.Timestamp("2026-07-19"))
    # ARG's row before the final, not the final itself
    assert row["away_elo"] == 2030.0
