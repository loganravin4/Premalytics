"""
Tests for the score-prediction pipeline:
  - pure functions in ml.models.score_predictor (no artifacts on disk)
  - ml.pipeline.train_scores.main()'s metrics.json persistence

The metrics-writing test monkeypatches load_score_features() with a small
synthetic feature matrix and ARTIFACTS_DIR with tmp_path, so it exercises the
real training/eval/persistence code path without touching real (gitignored)
raw match data or the real ml/artifacts directory.
"""

import json

import numpy as np
import pandas as pd
import pytest

from ml.models.score_predictor import (
    numeric_columns,
    feature_columns,
    prepare_score_features,
    predict_scoreline,
    _poisson_pmf,
    XG_NUMERIC,
    BASE_NUMERIC,
    CATEGORICAL,
)
import ml.pipeline.train_scores as train_scores


# ---------------------------------------------------------------------------
# ml.models.score_predictor — pure functions
# ---------------------------------------------------------------------------

class TestFeatureColumns:
    def test_numeric_columns_use_xg_true_includes_xg_features(self):
        cols = numeric_columns(use_xg=True)
        assert cols == XG_NUMERIC + BASE_NUMERIC

    def test_numeric_columns_use_xg_false_drops_xg_features(self):
        cols = numeric_columns(use_xg=False)
        assert cols == BASE_NUMERIC
        assert not any(c in cols for c in XG_NUMERIC)

    def test_feature_columns_appends_categorical(self):
        assert feature_columns(use_xg=True) == numeric_columns(True) + CATEGORICAL
        assert feature_columns(use_xg=False) == numeric_columns(False) + CATEGORICAL


class TestPrepareScoreFeatures:
    def test_fills_missing_columns_and_coerces_types(self):
        # Only one numeric column and no categorical columns present at all —
        # prepare_score_features must still produce every expected column.
        raw = pd.DataFrame({"home_gf_avg_5": ["1.5", "2.0"]})
        X = prepare_score_features(raw, use_xg=False)

        assert list(X.columns) == feature_columns(use_xg=False)
        assert X["home_gf_avg_5"].tolist() == [1.5, 2.0]
        assert X["home_ga_avg_5"].isna().all()          # missing numeric -> NaN
        assert (X["home_confederation"] == "OTHER").all()  # missing categorical -> OTHER

    def test_drops_xg_columns_when_use_xg_false(self):
        raw = pd.DataFrame({c: [1.0, 2.0] for c in XG_NUMERIC + BASE_NUMERIC})
        X = prepare_score_features(raw, use_xg=False)
        assert not any(c in X.columns for c in XG_NUMERIC)


class TestPredictScoreline:
    def test_zero_lambda_predicts_zero_goals(self):
        result = predict_scoreline(0.0, 0.0)
        assert result == {"home_goals": 0, "away_goals": 0, "probability": 1.0}

    def test_higher_lambda_favors_more_goals(self):
        result = predict_scoreline(3.0, 0.2)
        assert result["home_goals"] > result["away_goals"]

    def test_probability_is_the_max_joint_pmf(self):
        result = predict_scoreline(1.5, 1.0)
        best = _poisson_pmf(result["home_goals"], 1.5) * _poisson_pmf(result["away_goals"], 1.0)
        assert result["probability"] == pytest.approx(best, abs=1e-4)


# ---------------------------------------------------------------------------
# ml.pipeline.train_scores — metrics.json persistence
# ---------------------------------------------------------------------------

def _synthetic_score_features(n: int = 40) -> pd.DataFrame:
    """
    Small pivoted feature matrix shaped like load_score_features()'s output,
    straddling TRAIN_CUTOFF_DATE so both the train and eval splits are non-empty.
    """
    rng = np.random.default_rng(42)
    dates = pd.date_range("2026-05-01", periods=n, freq="2D")
    return pd.DataFrame({
        "match_date": dates,
        "goals_for": rng.poisson(1.5, n).astype(float),
        "goals_against": rng.poisson(1.2, n).astype(float),
        "home_xgf_avg_5": rng.uniform(0.5, 2.5, n),
        "home_xga_avg_5": rng.uniform(0.5, 2.5, n),
        "away_xgf_avg_5": rng.uniform(0.5, 2.5, n),
        "away_xga_avg_5": rng.uniform(0.5, 2.5, n),
        "home_gf_avg_5": rng.uniform(0.5, 2.5, n),
        "home_ga_avg_5": rng.uniform(0.5, 2.5, n),
        "diff_elo": rng.uniform(-100, 100, n),
        "home_is_neutral_venue": rng.integers(0, 2, n).astype(float),
        "home_confederation": ["UEFA"] * n,
        "away_confederation": ["CONMEBOL"] * n,
    })


@pytest.fixture
def isolated_score_run(monkeypatch, tmp_path):
    """Redirect train_scores at synthetic data + a scratch artifacts dir."""
    monkeypatch.setattr(train_scores, "load_score_features", _synthetic_score_features)
    monkeypatch.setattr(train_scores, "ARTIFACTS_DIR", tmp_path)
    return tmp_path


class TestMetricsPersistence:
    def test_main_writes_metrics_json_with_expected_keys(self, isolated_score_run):
        train_scores.main()

        run_dirs = [d for d in isolated_score_run.iterdir() if d.is_dir()]
        assert len(run_dirs) == 1, "expected exactly one score_{run_ts} run directory"
        metrics_path = run_dirs[0] / "metrics.json"
        assert metrics_path.exists()

        metrics = json.loads(metrics_path.read_text())
        assert set(metrics.keys()) == {
            "run_date", "n_train", "n_eval", "use_xg",
            "mae_home_goals", "mae_away_goals",
        }
        assert metrics["n_train"] > 0
        assert metrics["n_eval"] > 0
        assert isinstance(metrics["mae_home_goals"], float)
        assert isinstance(metrics["mae_away_goals"], float)

    def test_metrics_json_written_alongside_model_artifacts(self, isolated_score_run):
        train_scores.main()

        run_dir = next(d for d in isolated_score_run.iterdir() if d.is_dir())
        for name in ("home_goals.joblib", "away_goals.joblib",
                     "score_features.joblib", "score_feature_cols.json",
                     "metrics.json"):
            assert (run_dir / name).exists(), f"missing {name} in run dir"
