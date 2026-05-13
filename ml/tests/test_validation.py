"""
Data contract and validation tests.
"""

import numpy as np
import pandas as pd
import pytest

from ml.features.loader import validate_data_contract, REQUIRED_COLS, VALID_RESULTS, VALID_VENUES


def _minimal_valid_df(n: int = 10) -> pd.DataFrame:
    """Minimal valid DataFrame that passes all contract checks."""
    dates   = pd.date_range("2021-08-14", periods=n, freq="7D")
    cycle   = ["W", "D", "L"]
    results = [cycle[i % 3] for i in range(n)]
    goals_f = [0] * n
    goals_a = [0] * n

    # Ensure result consistency
    for i in range(n):
        r = results[i]
        if r == "W":
            goals_f[i] = 2; goals_a[i] = 0
        elif r == "D":
            goals_f[i] = 1; goals_a[i] = 1
        else:
            goals_f[i] = 0; goals_a[i] = 1

    return pd.DataFrame({
        "match_id":    [f"m{i:03d}" for i in range(n)],
        "season_id":   ["2021-2022"] * n,
        "team_id":     ["Arsenal"] * n,
        "opponent_id": ["Chelsea"] * n,
        "match_date":  dates,
        "venue":       ["Home" if i % 2 == 0 else "Away" for i in range(n)],
        "result":      results[:n],
        "goals_for":   goals_f[:n],
        "goals_against": goals_a[:n],
    })


class TestContractPasses:
    def test_valid_df_passes(self):
        df = _minimal_valid_df()
        result = validate_data_contract(df)
        assert result["passed"] is True

    def test_returns_total_rows(self):
        df = _minimal_valid_df(n=20)
        result = validate_data_contract(df)
        assert result["total_rows"] == 20

    def test_warnings_is_list(self):
        df = _minimal_valid_df()
        result = validate_data_contract(df)
        assert isinstance(result["warnings"], list)


class TestContractFailures:
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


class TestRowCountWarnings:
    def test_sparse_season_generates_warning(self):
        """A season with far fewer rows than expected triggers a warning."""
        df = _minimal_valid_df(n=5)   # Only 5 rows for a 20-team season
        result = validate_data_contract(df)
        # Should pass but with a warning
        assert result["passed"] is True
        # Expected ~760 rows for a full season, 5 is very sparse
        assert len(result["warnings"]) > 0


class TestNullRates:
    def test_high_null_xg_triggers_warning(self):
        df = _minimal_valid_df(n=20)
        df["xg_for"]    = None
        df["xg_against"] = None
        result = validate_data_contract(df)
        # Should pass but warn about high NULL rate
        assert result["passed"] is True
        xg_warning = any("xg_for" in w for w in result["warnings"])
        assert xg_warning, "Expected warning about high xg_for NULL rate"
