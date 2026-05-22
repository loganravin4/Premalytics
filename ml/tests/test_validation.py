"""
=============================================================================
Tests: DATA_CONTRACT.md validation (ml.features.loader.validate_data_contract)
=============================================================================

Covers:
  - Legacy EPL-shaped DataFrames (club names, no competition_id)
  - International fixture from ml/tests/fixtures/intl_match_logs_sample.csv
    (FIFA codes, dual-row, competition_id — produced by WC-03 ingest)
=============================================================================
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.features.loader import validate_data_contract, REQUIRED_COLS, VALID_RESULTS, VALID_VENUES

# Committed sample from real WC 2022 normalize output (see WC-04)
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "intl_match_logs_sample.csv"


def _minimal_valid_df(n: int = 10) -> pd.DataFrame:
    """
    Build a tiny synthetic EPL-era DataFrame that passes validate_data_contract.

    Uses club names as team_id (pre-pivot convention) and cycles W/D/L results
    with matching goals so result/goals consistency checks pass.
    """
    dates = pd.date_range("2021-08-14", periods=n, freq="7D")
    cycle = ["W", "D", "L"]
    results = [cycle[i % 3] for i in range(n)]
    goals_f = [0] * n
    goals_a = [0] * n

    for i in range(n):
        r = results[i]
        if r == "W":
            goals_f[i] = 2
            goals_a[i] = 0
        elif r == "D":
            goals_f[i] = 1
            goals_a[i] = 1
        else:
            goals_f[i] = 0
            goals_a[i] = 1

    return pd.DataFrame({
        "match_id": [f"m{i:03d}" for i in range(n)],
        "season_id": ["2021-2022"] * n,
        "team_id": ["Arsenal"] * n,
        "opponent_id": ["Chelsea"] * n,
        "match_date": dates,
        "venue": ["Home" if i % 2 == 0 else "Away" for i in range(n)],
        "result": results[:n],
        "goals_for": goals_f[:n],
        "goals_against": goals_a[:n],
    })


def _load_intl_fixture() -> pd.DataFrame:
    """Load committed international CSV; parse dates for contract checks."""
    assert FIXTURE_PATH.exists(), f"Missing fixture: {FIXTURE_PATH}"
    df = pd.read_csv(FIXTURE_PATH)
    df["match_date"] = pd.to_datetime(df["match_date"])
    return df


class TestContractPasses:
    """Happy-path cases — validation should return passed=True."""

    def test_valid_df_passes(self):
        df = _minimal_valid_df()
        result = validate_data_contract(df)
        assert result["passed"] is True

    def test_intl_fixture_passes(self):
        df = _load_intl_fixture()
        result = validate_data_contract(df)
        assert result["passed"] is True
        assert result["total_rows"] == len(df)

    def test_returns_total_rows(self):
        df = _minimal_valid_df(n=20)
        result = validate_data_contract(df)
        assert result["total_rows"] == 20

    def test_warnings_is_list(self):
        df = _minimal_valid_df()
        result = validate_data_contract(df)
        assert isinstance(result["warnings"], list)


class TestContractFailures:
    """Corrupt one field at a time — validation must raise ValueError."""

    def test_missing_required_column_raises(self):
        df = _minimal_valid_df()
        df = df.drop(columns=["result"])
        with pytest.raises(ValueError, match="result"):
            validate_data_contract(df)

    def test_negative_goals_raises(self):
        df = _minimal_valid_df()
        df.loc[0, "goals_for"] = -1
        with pytest.raises(ValueError):
            validate_data_contract(df)

    def test_duplicate_match_team_raises(self):
        df = _minimal_valid_df()
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)
        with pytest.raises(ValueError, match="duplicate"):
            validate_data_contract(df)

    def test_invalid_result_raises(self):
        df = _minimal_valid_df()
        df.loc[0, "result"] = "X"
        with pytest.raises(ValueError):
            validate_data_contract(df)

    def test_invalid_venue_raises(self):
        df = _minimal_valid_df()
        df.loc[0, "venue"] = "Neutral"
        with pytest.raises(ValueError):
            validate_data_contract(df)

    def test_negative_xg_raises(self):
        df = _minimal_valid_df()
        df["xg_for"] = -0.5
        with pytest.raises(ValueError):
            validate_data_contract(df)

    def test_intl_bad_team_id_raises(self):
        """International rows must use FIFA codes, not display names."""
        df = _load_intl_fixture()
        df.loc[0, "team_id"] = "Brazil"
        with pytest.raises(ValueError, match="FIFA"):
            validate_data_contract(df)

    def test_intl_inconsistent_goals_raises(self):
        """result=W requires goals_for > goals_against on that row."""
        df = _load_intl_fixture()
        df.loc[0, "result"] = "W"
        df.loc[0, "goals_for"] = 0
        df.loc[0, "goals_against"] = 2
        with pytest.raises(ValueError, match="inconsistent"):
            validate_data_contract(df)


class TestRowCountWarnings:
    def test_sparse_season_generates_warning(self):
        """Fewer than ~80% of expected EPL rows should warn, not fail."""
        df = _minimal_valid_df(n=5)
        result = validate_data_contract(df)
        assert result["passed"] is True
        assert len(result["warnings"]) > 0


class TestNullRates:
    def test_high_null_xg_triggers_warning(self):
        df = _minimal_valid_df(n=20)
        df["xg_for"] = None
        df["xg_against"] = None
        result = validate_data_contract(df)
        assert result["passed"] is True
        xg_warning = any("xg_for" in w for w in result["warnings"])
        assert xg_warning, "Expected warning about high xg_for NULL rate"
