"""
Tests for critical feature transformations.

Key property verified: no data leakage — features for match i use only
matches 0..i-1 (strictly prior dates).
"""

import numpy as np
import pandas as pd
import pytest

from ml.features.engineering import (
    _compute_team_rolling,
    build_team_features,
    compute_elo_features,
    _add_diff_features,
    build_features,
    pivot_to_match_rows,
    get_feature_columns,
)
from ml.features.loader import _clean_and_validate
from ml.config import TARGET_COL, ELO_INITIAL, ELO_K_FACTOR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_team_df(n: int = 15, team: str = "Arsenal", opponent: str = "Chelsea") -> pd.DataFrame:
    """
    Create a synthetic single-team DataFrame with n matches in chronological order.
    """
    dates   = pd.date_range("2021-08-14", periods=n, freq="7D")
    results = ["W", "D", "L", "W", "W", "D", "L", "W", "D", "W", "L", "W", "W", "D", "L"][:n]
    goals_f = [2, 1, 0, 3, 2, 1, 0, 2, 1, 3, 0, 2, 3, 1, 0][:n]
    goals_a = [0, 1, 2, 1, 0, 1, 3, 1, 1, 0, 1, 1, 0, 1, 2][:n]

    return pd.DataFrame({
        "match_id":    [f"m{i:03d}" for i in range(n)],
        "season_id":   ["2021-2022"] * n,
        "team_id":     [team] * n,
        "opponent_id": [opponent] * n,
        "match_date":  dates,
        "venue":       ["Home" if i % 2 == 0 else "Away" for i in range(n)],
        "result":      results,
        "goals_for":   goals_f,
        "goals_against": goals_a,
        "xg_for":      [float(g) + 0.2 for g in goals_f],
        "xg_against":  [float(g) + 0.1 for g in goals_a],
        "shots_for":   [g * 5 + 3 for g in goals_f],
        "shots_against": [g * 4 + 2 for g in goals_a],
        "shots_on_target_for": [g * 3 + 1 for g in goals_f],
        "shots_on_target_against": [g * 2 + 1 for g in goals_a],
        "corners_for": [g * 2 + 1 for g in goals_f],
        "corners_against": [g + 1 for g in goals_a],
    })


def _make_dual_row_df(n_per_team: int = 15) -> pd.DataFrame:
    """
    Create a dual-row DataFrame with two teams, n_per_team matches each.
    """
    home_df = _make_team_df(n_per_team, team="Arsenal", opponent="Chelsea")
    home_df["venue"] = "Home"

    away_df = _make_team_df(n_per_team, team="Chelsea", opponent="Arsenal")
    away_df["venue"] = "Away"
    away_df["result"] = home_df["result"].map({"W": "L", "D": "D", "L": "W"})
    away_df["goals_for"], away_df["goals_against"] = home_df["goals_against"].copy(), home_df["goals_for"].copy()

    df = pd.concat([home_df, away_df], ignore_index=True)
    df = df.sort_values(["match_date", "team_id"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Leakage tests
# ---------------------------------------------------------------------------

class TestNoLeakage:
    """
    Verify that rolling features for row i do not use information from row i.
    The golden rule: shift(1) ensures the current match's own stats are excluded.
    """

    def test_rolling_form_does_not_use_current_match(self):
        df = _make_team_df(n=10)
        result = _compute_team_rolling(df)

        # For match index 1 (second match), form_pts_5 should only use match 0
        # For match index 0 (first match), form_pts_5 should be NaN (no history)
        assert pd.isna(result.iloc[0]["form_pts_5"]), "First match must have no prior form"

        # For match 1, form_pts_5 uses only match 0
        row0_pts = {"W": 3, "D": 1, "L": 0}[df.iloc[0]["result"]]
        assert result.iloc[1]["form_pts_5"] == pytest.approx(row0_pts, abs=1e-6), \
            "form_pts_5 for match 1 must equal match 0's points only"

    def test_rolling_goals_exclude_current(self):
        df = _make_team_df(n=10)
        result = _compute_team_rolling(df)

        # Match index 2: gf_avg_3 should average goals_for of matches 0 and 1 only
        gf_01 = df.iloc[:2]["goals_for"].mean()
        assert result.iloc[2]["gf_avg_3"] == pytest.approx(gf_01, abs=1e-6), \
            "gf_avg_3 at index 2 must use only matches 0 and 1"

    def test_no_future_leakage_in_rolling(self):
        """
        Verify that feature values strictly increase in information content
        as we move forward in time (i.e., they never 'see' future matches).
        """
        df = _make_team_df(n=12)
        result = _compute_team_rolling(df)

        # The feature at row i should equal what you'd compute from df.iloc[:i]
        for i in range(2, 6):
            past     = df.iloc[:i]["goals_for"]
            expected = past.tail(3).mean()
            actual   = result.iloc[i]["gf_avg_3"]
            assert actual == pytest.approx(expected, abs=1e-6), \
                f"Leakage at index {i}: expected {expected:.4f}, got {actual:.4f}"

    def test_rest_days_no_leakage(self):
        df = _make_team_df(n=5)
        result = _compute_team_rolling(df)
        # First match has NaN rest_days (no prior match)
        assert pd.isna(result.iloc[0]["rest_days"]), "First match must have NaN rest_days"
        # Second match: 7 days after the first (weekly matches)
        assert result.iloc[1]["rest_days"] == pytest.approx(7.0, abs=1.0)

    def test_home_form_uses_only_home_games(self):
        df = _make_team_df(n=10)
        # Make matches 0,2,4,6,8 home; others away
        df["venue"] = ["Home" if i % 2 == 0 else "Away" for i in range(10)]
        result = _compute_team_rolling(df)

        # at_home_win_rate_5 should only reflect home match results
        # For match 4 (5th match, index 4), only matches 0 and 2 are home (prior home matches)
        prior_home = df.iloc[:4][df.iloc[:4]["venue"] == "Home"]
        expected   = (prior_home["result"] == "W").mean() if len(prior_home) > 0 else np.nan
        actual     = result.iloc[4]["at_home_win_rate_5"]
        if pd.isna(expected):
            assert pd.isna(actual)
        else:
            assert actual == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# Data quality tests
# ---------------------------------------------------------------------------

class TestDataQuality:
    def test_result_consistency_check(self):
        # Create intentionally bad row
        df = pd.DataFrame({
            "match_id":    ["m001"],
            "season_id":   ["2021-2022"],
            "team_id":     ["Arsenal"],
            "opponent_id": ["Chelsea"],
            "match_date":  [pd.Timestamp("2021-08-14")],
            "venue":       ["Home"],
            "result":      ["W"],
            "goals_for":   [0],    # W but 0 goals — inconsistent
            "goals_against": [2],
        })
        result = _clean_and_validate(df)
        assert len(result) == 0, "Inconsistent result row should be dropped"

    def test_negative_goals_dropped(self):
        df = pd.DataFrame({
            "match_id":    ["m001"],
            "season_id":   ["2021-2022"],
            "team_id":     ["Arsenal"],
            "opponent_id": ["Chelsea"],
            "match_date":  [pd.Timestamp("2021-08-14")],
            "venue":       ["Home"],
            "result":      ["W"],
            "goals_for":   [-1],
            "goals_against": [0],
        })
        result = _clean_and_validate(df)
        assert len(result) == 0, "Row with negative goals must be dropped"

    def test_duplicate_removal(self):
        base = {
            "match_id": "m001", "season_id": "2021-2022",
            "team_id": "Arsenal", "opponent_id": "Chelsea",
            "match_date": pd.Timestamp("2021-08-14"),
            "venue": "Home", "result": "W",
            "goals_for": 2, "goals_against": 0,
        }
        df = pd.DataFrame([base, base])  # exact duplicate
        result = _clean_and_validate(df)
        assert len(result) == 1, "Duplicate rows must be deduplicated"

    def test_invalid_result_dropped(self):
        df = pd.DataFrame({
            "match_id":    ["m001"],
            "season_id":   ["2021-2022"],
            "team_id":     ["Arsenal"],
            "opponent_id": ["Chelsea"],
            "match_date":  [pd.Timestamp("2021-08-14")],
            "venue":       ["Home"],
            "result":      ["X"],   # invalid
            "goals_for":   [2],
            "goals_against": [0],
        })
        result = _clean_and_validate(df)
        assert len(result) == 0, "Invalid result must be dropped"


# ---------------------------------------------------------------------------
# Pivot tests
# ---------------------------------------------------------------------------

class TestPivot:
    def test_pivot_halves_row_count(self):
        df = _make_dual_row_df(n_per_team=10)
        df_features = build_team_features(df)
        df_matches  = pivot_to_match_rows(df_features)
        assert len(df_matches) == 10, \
            f"Expected 10 single-row matches, got {len(df_matches)}"

    def test_pivot_outcome_column_present(self):
        df = _make_dual_row_df(n_per_team=10)
        df_features = build_team_features(df)
        df_matches  = pivot_to_match_rows(df_features)
        assert TARGET_COL in df_matches.columns
        assert set(df_matches[TARGET_COL].unique()).issubset({"H", "D", "A"})

    def test_home_win_maps_to_H(self):
        df = _make_dual_row_df(n_per_team=5)
        df_features = build_team_features(df)
        df_matches  = pivot_to_match_rows(df_features)

        # When home team won (result=W from home perspective), outcome should be H
        for _, row in df_matches.iterrows():
            home = df[(df["team_id"] == row["home_team"]) & (df["match_id"] == row["match_id"])]
            if home.empty:
                continue
            home_result = home.iloc[0]["result"]
            expected_outcome = {"W": "H", "D": "D", "L": "A"}[home_result]
            assert row[TARGET_COL] == expected_outcome, \
                f"match {row['match_id']}: home result {home_result} → expected {expected_outcome}, got {row[TARGET_COL]}"

    def test_feature_columns_have_home_and_away_prefix(self):
        df = _make_dual_row_df(n_per_team=10)
        df_features = build_team_features(df)
        df_matches  = pivot_to_match_rows(df_features)
        feature_cols = get_feature_columns(df_matches)

        home_feats = [c for c in feature_cols if c.startswith("home_")]
        away_feats = [c for c in feature_cols if c.startswith("away_")]

        assert len(home_feats) > 0, "Must have home_ prefixed features"
        assert len(away_feats) > 0, "Must have away_ prefixed features"
        assert len(home_feats) == len(away_feats), \
            f"home/away feature count mismatch: {len(home_feats)} vs {len(away_feats)}"


# ---------------------------------------------------------------------------
# Chronological split tests
# ---------------------------------------------------------------------------

class TestChronologicalSplit:
    def test_train_features_do_not_use_test_data(self):
        """
        Critical: if we split at 2023-2024, training features must not
        contain any information from 2023-2024 match outcomes.
        """
        df = _make_dual_row_df(n_per_team=14)

        # Assign two seasons
        mid = len(df) // 2
        df.loc[df.index[:mid], "season_id"] = "2021-2022"
        df.loc[df.index[mid:], "season_id"] = "2022-2023"
        # Fix dates so season 1 is clearly before season 2
        df.loc[df.index[:mid], "match_date"] = pd.date_range("2021-08-14", periods=mid, freq="7D")
        df.loc[df.index[mid:], "match_date"] = pd.date_range("2022-08-14", periods=len(df)-mid, freq="7D")

        df_features = build_team_features(df)
        df_matches  = pivot_to_match_rows(df_features)

        train = df_matches[df_matches["season_id"] == "2021-2022"]
        test  = df_matches[df_matches["season_id"] == "2022-2023"]

        assert train["match_date"].max() < test["match_date"].min(), \
            "All training matches must precede all test matches"


# ---------------------------------------------------------------------------
# ELO leakage tests
# ---------------------------------------------------------------------------

def _make_all_wins_dual_df(n: int = 6) -> pd.DataFrame:
    """
    Dual-row DataFrame where Arsenal (Home) beats Chelsea (Away) in every match.
    All matches on distinct weekly dates.
    """
    dates   = pd.date_range("2021-08-14", periods=n, freq="7D")
    goals_f = [2] * n
    goals_a = [0] * n

    home_df = pd.DataFrame({
        "match_id":      [f"m{i:03d}" for i in range(n)],
        "season_id":     ["2021-2022"] * n,
        "team_id":       ["Arsenal"] * n,
        "opponent_id":   ["Chelsea"] * n,
        "match_date":    dates,
        "venue":         ["Home"] * n,
        "result":        ["W"] * n,
        "goals_for":     goals_f,
        "goals_against": goals_a,
        "xg_for":        [2.1] * n,
        "xg_against":    [0.3] * n,
        "shots_for":     [12] * n,
        "shots_against": [4] * n,
        "shots_on_target_for":     [6] * n,
        "shots_on_target_against": [2] * n,
        "corners_for":   [5] * n,
        "corners_against": [2] * n,
    })
    away_df = home_df.copy()
    away_df["team_id"]     = "Chelsea"
    away_df["opponent_id"] = "Arsenal"
    away_df["venue"]       = "Away"
    away_df["result"]      = "L"
    away_df["goals_for"]   = goals_a
    away_df["goals_against"] = goals_f

    df = pd.concat([home_df, away_df], ignore_index=True)
    return df.sort_values(["match_date", "team_id"]).reset_index(drop=True)


class TestEloLeakage:
    """Verify that ELO features encode no future information."""

    def test_first_match_elo_is_initial(self):
        df = _make_all_wins_dual_df(n=5)
        result = compute_elo_features(df)

        for team in result["team_id"].unique():
            first_elo = (
                result[result["team_id"] == team]
                .sort_values("match_date")
                .iloc[0]["elo"]
            )
            assert first_elo == pytest.approx(ELO_INITIAL, abs=1e-6), \
                f"{team}: first-match ELO should be {ELO_INITIAL}, got {first_elo}"

    def test_elo_at_match1_reflects_only_match0_result(self):
        """
        After one win against an equal opponent (both at ELO_INITIAL), the winner's
        ELO should be exactly ELO_INITIAL + K*(1 - 0.5) = ELO_INITIAL + K/2.
        """
        df = _make_all_wins_dual_df(n=3)
        result = compute_elo_features(df)

        arsenal = result[result["team_id"] == "Arsenal"].sort_values("match_date")
        expected = ELO_INITIAL + ELO_K_FACTOR * 0.5   # win vs equal opponent
        assert arsenal.iloc[1]["elo"] == pytest.approx(expected, abs=1e-6), \
            "ELO at match 1 must reflect only the match-0 win, not the match-1 outcome"

    def test_elo_increases_monotonically_for_unbeaten_team(self):
        df = _make_all_wins_dual_df(n=6)
        result = compute_elo_features(df)

        arsenal = result[result["team_id"] == "Arsenal"].sort_values("match_date")
        elos = arsenal["elo"].tolist()
        for i in range(1, len(elos)):
            assert elos[i] > elos[i - 1], \
                f"ELO should rise after every win: match {i} ({elos[i]:.2f}) <= match {i-1} ({elos[i-1]:.2f})"

    def test_elo_decreases_monotonically_for_losing_team(self):
        df = _make_all_wins_dual_df(n=6)
        result = compute_elo_features(df)

        chelsea = result[result["team_id"] == "Chelsea"].sort_values("match_date")
        elos = chelsea["elo"].tolist()
        for i in range(1, len(elos)):
            assert elos[i] < elos[i - 1], \
                f"ELO should fall after every loss: match {i} ({elos[i]:.2f}) >= match {i-1} ({elos[i-1]:.2f})"

    def test_no_same_day_elo_leakage(self):
        """
        Two matches on the same date must each use start-of-day ELOs, not each
        other's post-match ELO.  All four teams are new → all ELOs must be ELO_INITIAL.
        """
        same_date = pd.Timestamp("2021-09-01")
        rows = [
            {"match_id": "m001", "season_id": "2021-2022", "team_id": "Arsenal",
             "opponent_id": "Chelsea", "match_date": same_date, "venue": "Home",
             "result": "W", "goals_for": 2, "goals_against": 0,
             "xg_for": 2.0, "xg_against": 0.3, "shots_for": 10, "shots_against": 4,
             "shots_on_target_for": 5, "shots_on_target_against": 2,
             "corners_for": 4, "corners_against": 2},
            {"match_id": "m001", "season_id": "2021-2022", "team_id": "Chelsea",
             "opponent_id": "Arsenal", "match_date": same_date, "venue": "Away",
             "result": "L", "goals_for": 0, "goals_against": 2,
             "xg_for": 0.3, "xg_against": 2.0, "shots_for": 4, "shots_against": 10,
             "shots_on_target_for": 2, "shots_on_target_against": 5,
             "corners_for": 2, "corners_against": 4},
            {"match_id": "m002", "season_id": "2021-2022", "team_id": "Liverpool",
             "opponent_id": "Manchester City", "match_date": same_date, "venue": "Home",
             "result": "W", "goals_for": 3, "goals_against": 1,
             "xg_for": 2.5, "xg_against": 1.0, "shots_for": 14, "shots_against": 8,
             "shots_on_target_for": 7, "shots_on_target_against": 3,
             "corners_for": 6, "corners_against": 3},
            {"match_id": "m002", "season_id": "2021-2022", "team_id": "Manchester City",
             "opponent_id": "Liverpool", "match_date": same_date, "venue": "Away",
             "result": "L", "goals_for": 1, "goals_against": 3,
             "xg_for": 1.0, "xg_against": 2.5, "shots_for": 8, "shots_against": 14,
             "shots_on_target_for": 3, "shots_on_target_against": 7,
             "corners_for": 3, "corners_against": 6},
        ]
        df = pd.DataFrame(rows)
        result = compute_elo_features(df)

        for _, row in result.iterrows():
            assert row["elo"] == pytest.approx(ELO_INITIAL, abs=1e-6), \
                f"{row['team_id']}: same-day first match ELO must be {ELO_INITIAL}, got {row['elo']}"

    def test_elo_column_present_after_pivot(self):
        df = _make_all_wins_dual_df(n=8)
        df_elo = compute_elo_features(df)
        df_pivot = pivot_to_match_rows(build_team_features(df_elo))

        assert "home_elo" in df_pivot.columns, "home_elo must be present after pivot"
        assert "away_elo" in df_pivot.columns, "away_elo must be present after pivot"

    def test_elo_not_in_meta_cols_so_pivoted_correctly(self):
        """
        home_elo and away_elo should differ by match 2+ once one team has
        accumulated wins.  If they were both ELO_INITIAL forever, something leaked
        or the column wasn't pivoted at all.
        """
        df = _make_all_wins_dual_df(n=8)
        df_features = build_features(df, include_h2h=False)

        # By match 3 Arsenal should have higher ELO than Chelsea
        later_matches = df_features.sort_values("match_date").iloc[3:]
        assert (later_matches["home_elo"] > later_matches["away_elo"]).all(), \
            "Arsenal (home, unbeaten) should have higher ELO than Chelsea (away, winless) by match 3"


# ---------------------------------------------------------------------------
# Differential feature tests
# ---------------------------------------------------------------------------

class TestDiffFeatures:
    def test_diff_elo_equals_home_minus_away_elo(self):
        df = _make_all_wins_dual_df(n=8)
        df_features = build_features(df, include_h2h=False)

        expected = df_features["home_elo"] - df_features["away_elo"]
        pd.testing.assert_series_equal(
            df_features["diff_elo"].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False,
            atol=1e-9,
        )

    def test_diff_form_pts5_equals_home_minus_away(self):
        df = _make_dual_row_df(n_per_team=12)
        df_features = build_features(df, include_h2h=False)

        if "diff_form_pts_5" in df_features.columns:
            expected = df_features["home_form_pts_5"] - df_features["away_form_pts_5"]
            pd.testing.assert_series_equal(
                df_features["diff_form_pts_5"].reset_index(drop=True),
                expected.reset_index(drop=True),
                check_names=False,
                atol=1e-9,
            )

    def test_get_feature_columns_includes_diff_cols(self):
        df = _make_dual_row_df(n_per_team=12)
        df_features = build_features(df, include_h2h=False)
        feat_cols = get_feature_columns(df_features)

        diff_cols = [c for c in feat_cols if c.startswith("diff_")]
        assert len(diff_cols) > 0, "Feature column list must include diff_ features"
        assert "diff_elo" in feat_cols, "diff_elo must be a feature"

    def test_diff_features_no_new_leakage(self):
        """
        Differential features are home minus away from already-shifted rolling stats.
        Verify they equal exactly that arithmetic — no extra shifts or accumulations.
        """
        df = _make_dual_row_df(n_per_team=12)
        df_features = build_features(df, include_h2h=False)

        for base in ("form_pts_3", "gf_avg_5", "season_pts_rate"):
            h_col = f"home_{base}"
            a_col = f"away_{base}"
            d_col = f"diff_{base}"
            if h_col in df_features.columns and d_col in df_features.columns:
                expected = df_features[h_col] - df_features[a_col]
                pd.testing.assert_series_equal(
                    df_features[d_col].reset_index(drop=True),
                    expected.reset_index(drop=True),
                    check_names=False,
                    atol=1e-9,
                    obj=f"diff feature {d_col}",
                )
