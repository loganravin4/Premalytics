"""
Tests for xG enrichment reliability.

Covers:
- Missing source behavior (no crash, no silent data)
- Partial match behavior (only matched rows enriched)
- No silent corruption (unmatched rows stay null; existing values not overwritten)
- FBRef loader correctness (normalized CSV excluded, correct file picked)
"""

import numpy as np
import pandas as pd
import pytest

from ml.features.loader import _fill_xg_from_lookup, _load_fbref_xg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rows(n: int = 4, team: str = "Arsenal") -> pd.DataFrame:
    dates = pd.date_range("2021-08-14", periods=n, freq="7D")
    return pd.DataFrame({
        "match_id":    [f"m{i:03d}" for i in range(n)],
        "season_id":   ["2021-2022"] * n,
        "team_id":     [team] * n,
        "opponent_id": [f"Opp{i}" for i in range(n)],
        "match_date":  dates,
        "venue":       ["Home"] * n,
        "result":      ["W"] * n,
        "goals_for":   [2] * n,
        "goals_against": [0] * n,
        "xg_for":      [np.nan] * n,
        "xg_against":  [np.nan] * n,
    })


def _key(df: pd.DataFrame, i: int) -> tuple:
    return (
        df.at[i, "match_date"].strftime("%Y-%m-%d"),
        df.at[i, "team_id"],
        df.at[i, "opponent_id"],
    )


# ---------------------------------------------------------------------------
# Missing source behavior
# ---------------------------------------------------------------------------

class TestMissingSource:
    def test_empty_data_dir_returns_empty_lookup(self, tmp_path):
        lookup = _load_fbref_xg(tmp_path, ["2021-2022"])
        assert lookup == {}

    def test_missing_season_subdir_returns_empty_lookup(self, tmp_path):
        lookup = _load_fbref_xg(tmp_path, ["2099-2100"])
        assert lookup == {}

    def test_empty_lookup_leaves_all_xg_null(self):
        df = _make_rows(n=3)
        result = _fill_xg_from_lookup(df, {})
        assert df["xg_for"].isna().all()
        assert result["xg_against"].isna().all()

    def test_season_dir_exists_but_no_fbref_csvs(self, tmp_path):
        (tmp_path / "2021-2022" / "Arsenal").mkdir(parents=True)
        lookup = _load_fbref_xg(tmp_path, ["2021-2022"])
        assert lookup == {}


# ---------------------------------------------------------------------------
# Partial match behavior
# ---------------------------------------------------------------------------

class TestPartialMatch:
    def test_only_matched_rows_get_xg(self):
        df = _make_rows(n=4)
        lookup = {
            _key(df, 0): (1.0, 0.5),
            _key(df, 2): (2.0, 1.0),
        }
        result = _fill_xg_from_lookup(df, lookup)
        assert pd.notna(result.at[0, "xg_for"])
        assert pd.notna(result.at[2, "xg_for"])
        assert pd.isna(result.at[1, "xg_for"])
        assert pd.isna(result.at[3, "xg_for"])

    def test_partial_match_sets_correct_values(self):
        df = _make_rows(n=2)
        lookup = {_key(df, 0): (1.3, 0.7)}
        result = _fill_xg_from_lookup(df, lookup)
        assert result.at[0, "xg_for"] == pytest.approx(1.3)
        assert result.at[0, "xg_against"] == pytest.approx(0.7)
        assert pd.isna(result.at[1, "xg_for"])

    def test_zero_xg_is_valid_and_filled(self):
        df = _make_rows(n=1)
        lookup = {_key(df, 0): (0.0, 0.0)}
        result = _fill_xg_from_lookup(df, lookup)
        assert result.at[0, "xg_for"] == pytest.approx(0.0)
        assert result.at[0, "xg_against"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# No silent corruption
# ---------------------------------------------------------------------------

class TestNoSilentCorruption:
    def test_unmatched_rows_stay_null(self):
        df = _make_rows(n=2)
        lookup = {}  # no matches
        result = _fill_xg_from_lookup(df, lookup)
        assert result["xg_for"].isna().all()
        assert result["xg_against"].isna().all()

    def test_existing_xg_not_overwritten(self):
        df = _make_rows(n=2)
        df.loc[0, "xg_for"] = 1.5
        df.loc[0, "xg_against"] = 0.3
        # Lookup has a conflicting entry for row 0
        lookup = {_key(df, 0): (9.9, 9.9)}
        result = _fill_xg_from_lookup(df, lookup)
        assert result.at[0, "xg_for"] == pytest.approx(1.5)
        assert result.at[0, "xg_against"] == pytest.approx(0.3)

    def test_partial_existing_xg_fills_only_null_field(self):
        df = _make_rows(n=1)
        df.loc[0, "xg_for"] = 1.5   # set; xg_against still null
        lookup = {_key(df, 0): (9.9, 0.8)}
        result = _fill_xg_from_lookup(df, lookup)
        assert result.at[0, "xg_for"] == pytest.approx(1.5)   # unchanged
        assert result.at[0, "xg_against"] == pytest.approx(0.8)  # filled

    def test_row_count_unchanged_after_enrichment(self):
        df = _make_rows(n=10)
        lookup = {_key(df, i): (float(i), float(i) * 0.5) for i in range(5)}
        result = _fill_xg_from_lookup(df, lookup)
        assert len(result) == 10

    def test_no_new_columns_introduced(self):
        df = _make_rows(n=3)
        cols_before = set(df.columns)
        lookup = {_key(df, 0): (1.0, 0.5)}
        result = _fill_xg_from_lookup(df, lookup)
        assert set(result.columns) == cols_before


# ---------------------------------------------------------------------------
# FBRef loader: normalized CSV exclusion and best-file selection
# ---------------------------------------------------------------------------

class TestFBRefLookupBuild:
    def _write_fbref_csv(self, path, date, opponent, xgf, xga):
        pd.DataFrame({
            "date": [date],
            "opponent": [opponent],
            "xg_for": [xgf],
            "xg_against": [xga],
        }).to_csv(path, index=False)

    def test_normalized_csv_excluded_from_fbref_source(self, tmp_path):
        team_dir = tmp_path / "2021-2022" / "Arsenal"
        team_dir.mkdir(parents=True)

        # FBRef CSV with real xG
        self._write_fbref_csv(team_dir / "match_logs_20251019_004130.csv",
                              "2021-08-13", "Brentford", 1.3, 0.7)
        # Normalized CSV with no xG (simulates real layout)
        pd.DataFrame({"date": ["2021-08-13"], "opponent": ["Brentford"]}).to_csv(
            team_dir / "match_logs_normalized.csv", index=False
        )

        lookup = _load_fbref_xg(tmp_path, ["2021-2022"])
        assert ("2021-08-13", "Arsenal", "Brentford") in lookup, (
            "FBRef CSV key must be in lookup; normalized CSV must be excluded"
        )

    def test_best_xg_file_selected_when_multiple_exist(self, tmp_path):
        team_dir = tmp_path / "2021-2022" / "Arsenal"
        team_dir.mkdir(parents=True)

        # Older file with xG
        self._write_fbref_csv(team_dir / "match_logs_20251019_004130.csv",
                              "2021-08-13", "Brentford", 1.3, 0.7)
        # Newer file without xG column (simulates 2026 rescrape)
        pd.DataFrame({
            "date": ["2021-08-13"],
            "opponent": ["Brentford"],
            "goals_for": [2],
        }).to_csv(team_dir / "match_logs_20260316_021507.csv", index=False)

        lookup = _load_fbref_xg(tmp_path, ["2021-2022"])
        assert ("2021-08-13", "Arsenal", "Brentford") in lookup, (
            "Loader must pick the file with xG even if a newer file has none"
        )
        xgf, xga = lookup[("2021-08-13", "Arsenal", "Brentford")]
        assert xgf == pytest.approx(1.3)
        assert xga == pytest.approx(0.7)

    def test_all_xg_null_file_skipped(self, tmp_path):
        team_dir = tmp_path / "2021-2022" / "Arsenal"
        team_dir.mkdir(parents=True)

        pd.DataFrame({
            "date": ["2021-08-13"],
            "opponent": ["Brentford"],
            "xg_for": [np.nan],
            "xg_against": [np.nan],
        }).to_csv(team_dir / "match_logs_20251019_004130.csv", index=False)

        lookup = _load_fbref_xg(tmp_path, ["2021-2022"])
        assert lookup == {}, "File with all-null xG must be skipped"

    def test_unrecognised_folder_ignored(self, tmp_path):
        team_dir = tmp_path / "2021-2022" / "unknown_team_xyz"
        team_dir.mkdir(parents=True)
        self._write_fbref_csv(team_dir / "match_logs_20251019.csv",
                              "2021-08-13", "Arsenal", 1.0, 0.5)
        lookup = _load_fbref_xg(tmp_path, ["2021-2022"])
        assert lookup == {}, "Folder not in FOLDER_TO_CANONICAL must be silently ignored"
