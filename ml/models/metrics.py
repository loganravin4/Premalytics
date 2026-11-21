"""
Probabilistic metrics for W/D/L forecasts.
Probabilities are (n, 3) in outcome order [home, draw, away]; convert sklearn predict_proba with from_model_proba.
"""

from __future__ import annotations

import numpy as np

OUTCOMES = ["home", "draw", "away"]
HOME, DRAW, AWAY = 0, 1, 2
EPS = 1e-15

# predict_proba column order is sorted TARGET_ENCODE values: A=0, D=1, H=2.
_MODEL_TO_OUTCOME = [2, 1, 0]
LABEL_TO_OUTCOME = {"H": HOME, "D": DRAW, "A": AWAY}


def from_model_proba(proba: np.ndarray) -> np.ndarray:
    return np.asarray(proba, dtype=float)[:, _MODEL_TO_OUTCOME]


def normalize(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 0.0, None)
    s = p.sum(axis=1, keepdims=True)
    s[s == 0] = 1.0
    return p / s


def _onehot(y: np.ndarray) -> np.ndarray:
    y = np.asarray(y, dtype=int)
    o = np.zeros((len(y), 3))
    o[np.arange(len(y)), y] = 1.0
    return o


def rps(p: np.ndarray, y: np.ndarray) -> float:
    p = normalize(p)
    o = _onehot(y)
    cp, co = np.cumsum(p, axis=1)[:, :2], np.cumsum(o, axis=1)[:, :2]
    return float(np.mean(np.sum((cp - co) ** 2, axis=1) / 2.0))


def brier(p: np.ndarray, y: np.ndarray) -> float:
    p = normalize(p)
    return float(np.mean(np.sum((p - _onehot(y)) ** 2, axis=1)))


def log_loss(p: np.ndarray, y: np.ndarray) -> float:
    p = normalize(p)
    y = np.asarray(y, dtype=int)
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], EPS, 1.0))))


def accuracy(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean(np.argmax(p, axis=1) == np.asarray(y, dtype=int)))


def draw_recall(p: np.ndarray, y: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    mask = y == DRAW
    if not mask.any():
        return float("nan")
    return float(np.mean(np.argmax(p[mask], axis=1) == DRAW))


def reliability(p: np.ndarray, y: np.ndarray, n_bins: int = 10) -> dict:
    p = normalize(p)
    o = _onehot(y)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    out: dict = {"n_bins": n_bins, "classes": {}}
    for k, name in enumerate(OUTCOMES):
        idx = np.clip(np.digitize(p[:, k], edges[1:-1], right=False), 0, n_bins - 1)
        bins, ece = [], 0.0
        for b in range(n_bins):
            m = idx == b
            n = int(m.sum())
            if n == 0:
                bins.append({"lo": round(edges[b], 2), "hi": round(edges[b + 1], 2),
                             "n": 0, "mean_pred": None, "obs_freq": None, "abs_gap": None})
                continue
            mp, of = float(p[m, k].mean()), float(o[m, k].mean())
            ece += n * abs(mp - of)
            bins.append({"lo": round(edges[b], 2), "hi": round(edges[b + 1], 2), "n": n,
                         "mean_pred": round(mp, 4), "obs_freq": round(of, 4),
                         "abs_gap": round(abs(mp - of), 4)})
        out["classes"][name] = {"ece": round(ece / max(len(p), 1), 4), "bins": bins}
    out["ece_mean"] = round(float(np.mean([c["ece"] for c in out["classes"].values()])), 4)
    return out


def credit_shootouts(p: np.ndarray, y: np.ndarray, knockout: np.ndarray,
                     shootout_winner_is_home: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Moves draw mass in knockouts onto the two teams and relabels shootouts to the team that advanced."""
    p = normalize(p).copy()
    y = np.asarray(y, dtype=int).copy()
    knockout = np.asarray(knockout, dtype=bool)
    sw = np.asarray(shootout_winner_is_home, dtype=float)

    ko = knockout | ~np.isnan(sw)
    ph, pd_, pa = p[ko, HOME], p[ko, DRAW], p[ko, AWAY]
    tot = ph + pa
    share = np.where(tot > 0, ph / np.where(tot > 0, tot, 1.0), 0.5)
    p[ko, HOME] = ph + pd_ * share
    p[ko, AWAY] = pa + pd_ * (1.0 - share)
    p[ko, DRAW] = 0.0

    decided = ~np.isnan(sw) & (y == DRAW)
    y[decided] = np.where(sw[decided] == 1.0, HOME, AWAY)
    return p, y


def score(p: np.ndarray, y: np.ndarray, with_reliability: bool = False) -> dict:
    y = np.asarray(y, dtype=int)
    out = {
        "n": int(len(y)),
        "accuracy": round(accuracy(p, y), 4),
        "rps": round(rps(p, y), 5),
        "brier": round(brier(p, y), 5),
        "log_loss": round(log_loss(p, y), 5),
        "draw_recall": round(draw_recall(p, y), 4),
        "draw_rate_actual": round(float(np.mean(y == DRAW)), 4) if len(y) else None,
        "draw_rate_pred_mean": round(float(np.mean(normalize(p)[:, DRAW])), 4) if len(y) else None,
    }
    if with_reliability:
        out["reliability"] = reliability(p, y)
    return out


def score_raw_and_credited(p, y, knockout, shootout_winner_is_home,
                           with_reliability: bool = False) -> dict:
    raw = score(p, y, with_reliability=with_reliability)
    pc, yc = credit_shootouts(p, y, knockout, shootout_winner_is_home)
    cred = score(pc, yc)
    return {
        **raw,
        "log_loss_raw": raw["log_loss"],
        "log_loss_shootout_credited": cred["log_loss"],
        "accuracy_shootout_credited": cred["accuracy"],
        "rps_shootout_credited": cred["rps"],
        "brier_shootout_credited": cred["brier"],
    }
