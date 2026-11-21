"""ML-02 / ML-05: scoring rules, shootout crediting, calibration maps."""

import numpy as np
import pytest

from ml.models import metrics as M
from ml.models.calibration import (DrawBiasScaler, LinearPool, TemperatureScaler,
                                   ThresholdDrawCal, apply_threshold_draw_cal)


def test_rps_known_values():
    y = np.array([M.HOME])
    assert M.rps(np.array([[1.0, 0.0, 0.0]]), y) == pytest.approx(0.0)
    assert M.rps(np.array([[0.0, 0.0, 1.0]]), y) == pytest.approx(1.0)
    # (0.5-1)^2 + (0.8-1)^2, halved
    assert M.rps(np.array([[0.5, 0.3, 0.2]]), y) == pytest.approx((0.25 + 0.04) / 2)
    # RPS rewards being "close": predicting draw beats predicting away for a home win
    assert M.rps(np.array([[0, 1.0, 0]]), y) < M.rps(np.array([[0, 0, 1.0]]), y)


def test_brier_and_log_loss():
    p = np.array([[0.5, 0.3, 0.2]])
    y = np.array([M.DRAW])
    assert M.brier(p, y) == pytest.approx(0.25 + 0.49 + 0.04)
    assert M.log_loss(p, y) == pytest.approx(-np.log(0.3))


def test_from_model_proba_reorders_columns():
    # model columns: A, D, H
    assert M.from_model_proba(np.array([[0.1, 0.2, 0.7]])).tolist() == [[0.7, 0.2, 0.1]]


def test_credit_shootouts():
    p = np.array([[0.4, 0.4, 0.2], [0.5, 0.3, 0.2], [0.3, 0.3, 0.4]])
    y = np.array([M.DRAW, M.DRAW, M.AWAY])
    ko = np.array([False, False, True])
    # Match 0 went to penalties and the away side advanced
    sw = np.array([0.0, np.nan, np.nan])
    pc, yc = M.credit_shootouts(p, y, ko, sw)
    assert yc.tolist() == [M.AWAY, M.DRAW, M.AWAY]
    np.testing.assert_allclose(pc[0], [0.4 + 0.4 * 2 / 3, 0.0, 0.2 + 0.4 / 3])
    # Not a knockout, so the draw stands
    np.testing.assert_allclose(pc[1], p[1])
    assert pc[2, 1] == 0.0 and pc.sum(axis=1) == pytest.approx(1.0)
    out = M.score_raw_and_credited(p, y, ko, sw)
    assert {"rps", "brier", "log_loss_raw", "log_loss_shootout_credited"} <= out.keys()


def test_reliability_bins():
    rng = np.random.default_rng(0)
    p = rng.dirichlet([2, 1, 2], 2000)
    y = np.array([rng.choice(3, p=row) for row in p])
    rel = M.reliability(p, y)
    assert set(rel["classes"]) == {"home", "draw", "away"}
    assert sum(b["n"] for b in rel["classes"]["home"]["bins"]) == 2000
    # Labels are sampled from p, so it's calibrated by construction
    assert rel["ece_mean"] < 0.05


def test_temperature_recovers_overconfidence():
    rng = np.random.default_rng(1)
    true = rng.dirichlet([2, 1.5, 2], 4000)
    y = np.array([rng.choice(3, p=row) for row in true])
    # Squaring is temperature 0.5, so the fit should recover T = 2
    sharp = true ** 2 / (true ** 2).sum(axis=1, keepdims=True)
    ts = TemperatureScaler().fit(sharp, y)
    assert ts.t_ == pytest.approx(2.0, rel=0.15)
    assert M.log_loss(ts.transform(sharp), y) < M.log_loss(sharp, y)
    db = DrawBiasScaler().fit(sharp, y)
    np.testing.assert_allclose(db.transform(sharp).sum(axis=1), 1.0)


def test_threshold_draw_cal_matches_scalar_rule():
    from ml.pipeline.predict import _apply_draw_calibration
    p = np.array([[0.85, 0.1, 0.05], [0.1, 0.1, 0.8], [0.4, 0.3, 0.3]])
    vec = apply_threshold_draw_cal(p, 0.75, 0.6)
    for row, v in zip(p, vec):
        np.testing.assert_allclose(_apply_draw_calibration(*row, 0.75, 0.6), v)
    t = ThresholdDrawCal().fit(p, np.array([0, 2, 1]))
    assert t.params()["threshold"] in ThresholdDrawCal.THRESHOLDS


def test_linear_pool_picks_better_model():
    rng = np.random.default_rng(2)
    true = rng.dirichlet([2, 1.5, 2], 3000)
    y = np.array([rng.choice(3, p=row) for row in true])
    noise = rng.dirichlet([1, 1, 1], 3000)
    lp = LinearPool().fit(true, noise, y)
    assert lp.w_ >= 0.8
