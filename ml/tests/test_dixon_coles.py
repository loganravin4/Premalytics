"""ML-04: Dixon-Coles score model and W/D/L probabilities."""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from ml.models.dixon_coles import DixonColes, outcome_probs, score_matrix


def _synthetic_matches(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(12)]
    strength = np.linspace(-0.5, 0.5, 12)
    h = rng.integers(0, 12, n)
    a = (h + rng.integers(1, 12, n)) % 12
    lam = np.exp(0.2 + 0.25 + strength[h] - strength[a] * 0.8)
    mu = np.exp(0.2 + strength[a] - strength[h] * 0.8)
    dates = pd.Timestamp("2015-01-01") + pd.to_timedelta(np.sort(rng.integers(0, 3000, n)), "D")
    return pd.DataFrame({"home": np.array(teams)[h], "away": np.array(teams)[a],
                         "hg": rng.poisson(lam), "ag": rng.poisson(mu),
                         "neutral": rng.random(n) < 0.3, "date": dates})


@pytest.fixture(scope="module")
def fitted():
    df = _synthetic_matches()
    return DixonColes(xi=0.0005, l2=0.1).fit(df.home, df.away, df.hg, df.ag,
                                             df.neutral, df.date), df


@pytest.mark.parametrize("lam,mu,rho", [(1.4, 1.1, -0.1), (0.3, 2.8, 0.15),
                                        (2.5, 0.2, -0.25), (0.05, 0.05, 0.0)])
def test_score_matrix_and_outcomes_sum_to_one(lam, mu, rho):
    mat = score_matrix(lam, mu, rho)
    assert mat.min() >= 0
    assert mat.sum() == pytest.approx(1.0)
    p = outcome_probs(mat)
    assert p.sum() == pytest.approx(1.0)
    assert (p >= 0).all()


def test_rho_zero_matches_independent_poisson():
    lam, mu = 1.3, 0.9
    mat = score_matrix(lam, mu, 0.0, max_goals=15)
    ref = np.outer(poisson.pmf(np.arange(16), lam), poisson.pmf(np.arange(16), mu))
    np.testing.assert_allclose(mat, ref / ref.sum(), atol=1e-10)


def test_negative_rho_raises_draw_probability():
    p0 = outcome_probs(score_matrix(1.2, 1.0, 0.0))
    pn = outcome_probs(score_matrix(1.2, 1.0, -0.15))
    assert pn[1] > p0[1]


def test_fitted_predictions_sum_to_one_and_rank_teams(fitted):
    dc, _ = fitted
    assert dc.converged_
    p = dc.predict_outcome_proba(["T11", "T0", "T5", "UNSEEN"], ["T0", "T11", "T6", "T3"],
                                 [True, True, False, False])
    np.testing.assert_allclose(p.sum(axis=1), 1.0)
    # T11 is the strongest team, T0 the weakest
    assert p[0, 0] > p[0, 2]
    assert p[1, 2] > p[1, 0]
    assert dc.home_adv_ > 0
    assert -0.25 <= dc.rho_ <= 0.25


def test_analytic_gradient_matches_numeric():
    from scipy.optimize import approx_fprime, minimize
    df = _synthetic_matches(n=200, seed=1)
    captured = {}
    orig = minimize

    def spy(fun, x0, jac=None, **kw):
        captured["fun"] = fun
        return orig(fun, x0, jac=jac, **kw)

    import ml.models.dixon_coles as dcm
    dcm.minimize = spy
    try:
        DixonColes(xi=0.001, l2=0.5).fit(df.home, df.away, df.hg, df.ag, df.neutral, df.date)
    finally:
        dcm.minimize = orig
    f = captured["fun"]
    rng = np.random.default_rng(3)
    theta = rng.normal(0, 0.1, 3 + 2 * 12)
    theta[2] = 0.05
    num = approx_fprime(theta, lambda t: f(t)[0], 1e-6)
    np.testing.assert_allclose(f(theta)[1], num, rtol=1e-3, atol=1e-5)
