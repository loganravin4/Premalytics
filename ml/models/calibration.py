"""
Post-hoc calibration and blending for (n, 3) [home, draw, away] probabilities.
Fit only on out-of-sample predictions from earlier walk-forward folds, never on the fold being scored.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from ml.models.metrics import DRAW, HOME, AWAY, log_loss, normalize

_EPS = 1e-12


def _power(p: np.ndarray, t: float, b: float = 0.0) -> np.ndarray:
    lp = np.log(np.clip(normalize(p), _EPS, 1.0)) / t
    lp[:, DRAW] += b
    lp -= lp.max(axis=1, keepdims=True)
    e = np.exp(lp)
    return e / e.sum(axis=1, keepdims=True)


class TemperatureScaler:
    def __init__(self):
        self.t_ = 1.0

    def fit(self, p, y):
        res = minimize(lambda v: log_loss(_power(p, np.exp(v[0])), y), [0.0],
                       method="Nelder-Mead")
        self.t_ = float(np.exp(res.x[0]))
        return self

    def transform(self, p):
        return _power(p, self.t_)

    def params(self):
        return {"temperature": round(self.t_, 4)}


class DrawBiasScaler:
    def __init__(self):
        self.t_, self.b_ = 1.0, 0.0

    def fit(self, p, y):
        res = minimize(lambda v: log_loss(_power(p, np.exp(v[0]), v[1]), y), [0.0, 0.0],
                       method="Nelder-Mead")
        self.t_, self.b_ = float(np.exp(res.x[0])), float(res.x[1])
        return self

    def transform(self, p):
        return _power(p, self.t_, self.b_)

    def params(self):
        return {"temperature": round(self.t_, 4), "draw_bias": round(self.b_, 4)}


class LinearPool:
    GRID = np.round(np.linspace(0.0, 1.0, 21), 2)

    def __init__(self):
        self.w_ = 0.5

    def fit(self, pa, pb, y):
        losses = [log_loss(w * pa + (1 - w) * pb, y) for w in self.GRID]
        self.w_ = float(self.GRID[int(np.argmin(losses))])
        return self

    def transform(self, pa, pb):
        return normalize(self.w_ * pa + (1 - self.w_) * pb)

    def params(self):
        return {"weight_first": self.w_}


def apply_threshold_draw_cal(p: np.ndarray, threshold: float, alpha: float) -> np.ndarray:
    """Vectorized ml.pipeline.predict._apply_draw_calibration."""
    p = normalize(p).copy()
    home_fav = p[:, HOME] >= p[:, AWAY]
    fav = np.where(home_fav, p[:, HOME], p[:, AWAY])
    shift = np.where(fav > threshold, alpha * (fav - threshold), 0.0)
    p[:, DRAW] += shift
    p[home_fav, HOME] -= shift[home_fav]
    p[~home_fav, AWAY] -= shift[~home_fav]
    return normalize(p)


class ThresholdDrawCal:
    # 1.01 disables the rule, so the search can pick "no calibration".
    THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.01]
    ALPHAS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]

    def __init__(self):
        self.threshold_, self.alpha_ = 1.01, 0.0

    def fit(self, p, y):
        best = (log_loss(p, y), 1.01, 0.0)
        for t in self.THRESHOLDS:
            for a in self.ALPHAS:
                ll = log_loss(apply_threshold_draw_cal(p, t, a), y)
                if ll < best[0] - 1e-9:
                    best = (ll, t, a)
        _, self.threshold_, self.alpha_ = best
        return self

    def transform(self, p):
        return apply_threshold_draw_cal(p, self.threshold_, self.alpha_)

    def params(self):
        return {"threshold": self.threshold_, "alpha": self.alpha_}
