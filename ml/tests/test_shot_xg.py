"""
Tests for the shot-level xG models and time-based split.

Uses small synthetic shot data so the suite does not depend on the
gitignored raw shot CSVs or on a prior training run.
"""

import numpy as np
import pandas as pd
import pytest

from ml.models.shot_xg import (
    make_logistic_xg_pipeline,
    make_gbm_xg_pipeline,
    LOGISTIC_FEATURES,
    GBM_FEATURES,
    GBM_CATEGORICAL,
    BODY_PART_CATEGORIES,
    SITUATION_CATEGORIES,
)
from ml.pipeline.train_shots import split_shots, TRAIN_SEASON, EVAL_SEASON


def _synth_shots(n: int = 200, seed: int = 0) -> pd.DataFrame:
    """Synthetic shots across WC 2018 (train) and WC 2022 (eval)."""
    rng = np.random.RandomState(seed)
    half = n // 2
    seasons = [TRAIN_SEASON] * half + [EVAL_SEASON] * (n - half)
    # 2018 dates strictly before 2022 dates
    dates = (
        [f"2018-06-{(i % 28) + 1:02d}" for i in range(half)]
        + [f"2022-11-{(i % 28) + 1:02d}" for i in range(n - half)]
    )
    distance = rng.uniform(2, 35, n)
    angle = rng.uniform(0, 90, n)
    # goal probability falls with distance/angle — gives the models real signal
    p = 1.0 / (1.0 + np.exp(0.18 * distance + 0.03 * angle - 2.0))
    is_goal = rng.uniform(0, 1, n) < p

    return pd.DataFrame({
        "season_id": seasons,
        "match_date": dates,
        "distance_m": distance,
        "angle_deg": angle,
        "under_pressure": rng.randint(0, 2, n),
        "body_part": rng.choice(BODY_PART_CATEGORIES, n),
        "situation": rng.choice(SITUATION_CATEGORIES, n),
        "label": is_goal.astype(int),
    })


@pytest.fixture
def synth():
    return _synth_shots()


# ---------------------------------------------------------------------------
# Model fit / predict
# ---------------------------------------------------------------------------

class TestModelsPredict:
    def test_logistic_fits_and_predicts(self, synth):
        model = make_logistic_xg_pipeline()
        model.fit(synth[LOGISTIC_FEATURES], synth["label"])
        proba = model.predict_proba(synth[LOGISTIC_FEATURES])
        assert proba.shape == (len(synth), 2)

    def test_gbm_fits_and_predicts(self, synth):
        model = make_gbm_xg_pipeline()
        model.fit(synth[GBM_FEATURES], synth["label"])
        proba = model.predict_proba(synth[GBM_FEATURES])
        assert proba.shape == (len(synth), 2)

    def test_predict_proba_within_unit_interval(self, synth):
        for make, feats in [
            (make_logistic_xg_pipeline, LOGISTIC_FEATURES),
            (make_gbm_xg_pipeline, GBM_FEATURES),
        ]:
            model = make()
            model.fit(synth[feats], synth["label"])
            proba = model.predict_proba(synth[feats])
            assert (proba >= 0).all() and (proba <= 1).all()
            assert np.allclose(proba.sum(axis=1), 1.0)


# ---------------------------------------------------------------------------
# Time-based split (no leakage)
# ---------------------------------------------------------------------------

class TestTimeSplit:
    def test_train_strictly_before_eval(self, synth):
        train, eval_ = split_shots(synth)
        assert len(train) > 0 and len(eval_) > 0
        assert (train["season_id"] == TRAIN_SEASON).all()
        assert (eval_["season_id"] == EVAL_SEASON).all()
        # WC 2018 dates must all precede WC 2022 dates
        assert train["match_date"].max() < eval_["match_date"].min()


# ---------------------------------------------------------------------------
# Feature-set contracts
# ---------------------------------------------------------------------------

class TestFeatureSets:
    def test_logistic_uses_only_distance_and_angle(self):
        assert LOGISTIC_FEATURES == ["distance_m", "angle_deg"]

    def test_gbm_includes_body_part_and_situation(self):
        assert "body_part" in GBM_FEATURES
        assert "situation" in GBM_FEATURES
        assert set(GBM_CATEGORICAL) == {"body_part", "situation"}

    def test_gbm_one_hot_expands_categoricals(self, synth):
        """GBM preprocessor: 3 numeric + one-hot(3 body_part + 3 situation) = 9 cols."""
        model = make_gbm_xg_pipeline()
        model.fit(synth[GBM_FEATURES], synth["label"])
        # CalibratedClassifierCV wraps the Pipeline; inspect the inner estimator's
        # preprocessor. cv folds clone the template, so fit it to inspect transform.
        inner = model.estimator
        inner.fit(synth[GBM_FEATURES], synth["label"])
        transformed = inner.named_steps["prep"].transform(synth[GBM_FEATURES])
        assert transformed.shape[1] == 9
