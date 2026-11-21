"""
Dixon-Coles bivariate Poisson score model with the low-score tau correction.
Time-decayed and L2-shrunk toward average, since many international sides play only 8-10 games a year.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln

MAX_GOALS = 10
RHO_BOUNDS = (-0.25, 0.25)


class DixonColes:
    def __init__(self, xi: float = 0.0010, l2: float = 2.0, max_goals: int = MAX_GOALS):
        # 0.001 per day is roughly a 1.9-year half-life.
        self.xi = xi
        self.l2 = l2
        self.max_goals = max_goals

    def fit(self, home: pd.Series, away: pd.Series, hg, ag, neutral, dates,
            ref_date=None, weights=None) -> "DixonColes":
        home = np.asarray(home).astype(str)
        away = np.asarray(away).astype(str)
        hg = np.asarray(hg, dtype=float)
        ag = np.asarray(ag, dtype=float)
        not_neutral = (~np.asarray(neutral, dtype=bool)).astype(float)
        dates = pd.to_datetime(pd.Series(dates)).to_numpy()
        ref = pd.Timestamp(ref_date) if ref_date is not None else pd.Timestamp(dates.max())
        days = (ref.to_datetime64() - dates) / np.timedelta64(1, "D")
        w = np.exp(-self.xi * np.clip(days.astype(float), 0, None))
        if weights is not None:
            w = w * np.asarray(weights, dtype=float)

        teams = np.unique(np.concatenate([home, away]))
        self.teams_ = {t: i for i, t in enumerate(teams)}
        hi = np.array([self.teams_[t] for t in home])
        ai = np.array([self.teams_[t] for t in away])
        n = len(teams)
        x00 = (hg == 0) & (ag == 0)
        x01 = (hg == 0) & (ag == 1)
        x10 = (hg == 1) & (ag == 0)
        x11 = (hg == 1) & (ag == 1)
        const = np.sum(w * (gammaln(hg + 1) + gammaln(ag + 1)))
        wsum = w.sum()

        def unpack(theta):
            return theta[0], theta[1], theta[2], theta[3:3 + n], theta[3 + n:]

        def nll(theta):
            mu, h, rho, att, de = unpack(theta)
            el = mu + h * not_neutral + att[hi] - de[ai]
            em = mu + att[ai] - de[hi]
            lam, m = np.exp(el), np.exp(em)
            tau = np.ones_like(lam)
            tau[x00] = 1 - lam[x00] * m[x00] * rho
            tau[x01] = 1 + lam[x01] * rho
            tau[x10] = 1 + m[x10] * rho
            tau[x11] = 1 - rho
            tau = np.clip(tau, 1e-10, None)
            ll = w * (np.log(tau) + hg * el - lam + ag * em - m)
            # The L2 penalty also identifies the model, so no sum-to-zero constraint is needed.
            f = -(ll.sum() - const) / wsum + self.l2 * (att @ att + de @ de) / wsum

            # d log tau / d lam, d mu, d rho
            dl = np.zeros_like(lam)
            dm = np.zeros_like(lam)
            dr = np.zeros_like(lam)
            dl[x00] = -m[x00] * rho / tau[x00]
            dm[x00] = -lam[x00] * rho / tau[x00]
            dr[x00] = -lam[x00] * m[x00] / tau[x00]
            dl[x01] = rho / tau[x01]
            dr[x01] = lam[x01] / tau[x01]
            dm[x10] = rho / tau[x10]
            dr[x10] = m[x10] / tau[x10]
            dr[x11] = -1 / tau[x11]
            g_el = w * (hg - lam + lam * dl)
            g_em = w * (ag - m + m * dm)
            g = np.empty_like(theta)
            g[0] = g_el.sum() + g_em.sum()
            g[1] = (g_el * not_neutral).sum()
            g[2] = (w * dr).sum()
            g_att = np.bincount(hi, g_el, n) + np.bincount(ai, g_em, n)
            g_def = -np.bincount(ai, g_el, n) - np.bincount(hi, g_em, n)
            g[3:3 + n] = g_att
            g[3 + n:] = g_def
            g = -g / wsum
            g[3:] += 2 * self.l2 * theta[3:] / wsum
            return f, g

        theta0 = np.zeros(3 + 2 * n)
        theta0[0] = np.log(max(np.average(np.concatenate([hg, ag]),
                                          weights=np.concatenate([w, w])), 0.1))
        theta0[1] = 0.2
        bounds = [(None, None), (None, None), RHO_BOUNDS] + [(None, None)] * (2 * n)
        res = minimize(nll, theta0, jac=True, method="L-BFGS-B", bounds=bounds,
                       options={"maxiter": 2000})
        self.mu_, self.home_adv_, self.rho_, self.attack_, self.defense_ = unpack(res.x)
        self.converged_ = bool(res.success)
        self.n_train_ = int(len(hg))
        return self

    def expected_goals(self, home, away, neutral) -> tuple[np.ndarray, np.ndarray]:
        # Teams unseen in training get attack = defense = 0, i.e. average.
        def look(arr, teams):
            return np.array([arr[self.teams_[t]] if t in self.teams_ else 0.0
                             for t in np.asarray(teams).astype(str)])
        nn = (~np.asarray(neutral, dtype=bool)).astype(float)
        ah, aa = look(self.attack_, home), look(self.attack_, away)
        dh, da = look(self.defense_, home), look(self.defense_, away)
        lam = np.exp(self.mu_ + self.home_adv_ * nn + ah - da)
        m = np.exp(self.mu_ + aa - dh)
        return lam, m

    def score_matrix(self, lam: float, m: float) -> np.ndarray:
        return score_matrix(lam, m, self.rho_, self.max_goals)

    def predict_outcome_proba(self, home, away, neutral) -> np.ndarray:
        """(n, 3) probabilities in outcome order [home, draw, away]."""
        lam, m = self.expected_goals(home, away, neutral)
        return np.vstack([outcome_probs(score_matrix(l, mm, self.rho_, self.max_goals))
                          for l, mm in zip(lam, m)])


def _pois(k: np.ndarray, lam: float) -> np.ndarray:
    return np.exp(-lam + k * np.log(max(lam, 1e-12)) - gammaln(k + 1))


def score_matrix(lam: float, m: float, rho: float, max_goals: int = MAX_GOALS) -> np.ndarray:
    """Joint P(home=i, away=j) up to max_goals, with the tau term, renormalized."""
    k = np.arange(max_goals + 1, dtype=float)
    mat = np.outer(_pois(k, lam), _pois(k, m))
    mat[0, 0] *= max(1 - lam * m * rho, 0.0)
    mat[0, 1] *= max(1 + lam * rho, 0.0)
    mat[1, 0] *= max(1 + m * rho, 0.0)
    mat[1, 1] *= max(1 - rho, 0.0)
    return mat / mat.sum()


def outcome_probs(mat: np.ndarray) -> np.ndarray:
    """[P(home win), P(draw), P(away win)] from a score matrix."""
    p = np.array([np.tril(mat, -1).sum(), np.trace(mat), np.triu(mat, 1).sum()])
    return p / p.sum()
