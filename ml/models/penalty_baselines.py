"""
Penalty baselines: descriptive conversion tables and pre-kick predictors, kept apart on purpose.
The tables slice by where the ball went, known only after the kick, so they describe and never predict.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.config import RANDOM_SEED

ZONE_ROWS = ["high", "mid", "low"]
# Left and right are from the taker's view, not the keeper's.
ZONE_COLS = ["left", "center", "right"]
ZONES = [f"{r}_{c}" for r in ZONE_ROWS for c in ZONE_COLS]

# Columns known before the kick. Everything else in the CSV is post-kick or an id.
PREKICK_CATEGORICAL = ["phase", "taker_foot", "pressure_bucket", "order_bucket"]
PREKICK_NUMERIC = ["is_womens"]
PREKICK_FEATURES = PREKICK_CATEGORICAL + PREKICK_NUMERIC

# Post-kick columns. Never a predictor input.
POSTKICK_COLUMNS = {
    "outcome", "is_goal", "end_y", "end_z", "on_target", "placement_col", "placement_row",
    "placement_zone", "foot_side", "keeper_technique", "keeper_set",
}

# Pseudo-count pulling small groups toward the overall rate.
SHRINK_K = 20.0
MIN_DISPLAY_N = 20


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def order_bucket(team_kick_number) -> str:
    if team_kick_number is None or pd.isna(team_kick_number):
        return "in_game"
    k = int(team_kick_number)
    return str(k) if k <= 5 else "6+"


def add_prekick_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["is_womens"] = (out["competition_gender"] == "female").astype(int)
    out["order_bucket"] = out["team_kick_number"].map(order_bucket)
    out["pressure_bucket"] = np.where(
        out["phase"] == "shootout",
        "so_" + out["shootout_pressure"].fillna("neutral").astype(str),
        "ig_" + out["game_state"].fillna("level").astype(str),
    )
    out["label"] = out["is_goal"].astype(int)
    return out


def conversion_table(df: pd.DataFrame, by: list[str], total: int | None = None) -> list[dict]:
    total = total if total is not None else len(df)
    rows = []
    for keys, g in df.groupby(by, dropna=True, observed=True):
        keys = keys if isinstance(keys, tuple) else (keys,)
        n, k = len(g), int(g["is_goal"].sum())
        lo, hi = wilson_interval(k, n)
        rec = {col: (v.item() if hasattr(v, "item") else v) for col, v in zip(by, keys)}
        rec.update({
            "n": n, "goals": k, "conversion": round(k / n, 4),
            "ci95": [round(lo, 4), round(hi, 4)],
            "share": round(n / total, 4) if total else None,
            "low_sample": n < MIN_DISPLAY_N,
        })
        rows.append(rec)
    return rows


def zone_grid(df: pd.DataFrame) -> dict:
    total = len(df)
    cells = []
    for r in ZONE_ROWS:
        row_cells = []
        for c in ZONE_COLS:
            g = df[df["placement_zone"] == f"{r}_{c}"]
            n, k = len(g), int(g["is_goal"].sum())
            lo, hi = wilson_interval(k, n)
            row_cells.append({
                "zone": f"{r}_{c}", "row": r, "col": c, "n": n,
                "share": round(n / total, 4) if total else 0.0,
                "goals": k,
                "saved": int((g["outcome"] == "saved").sum()),
                "missed": int(g["outcome"].isin(["post", "off_target"]).sum()),
                "conversion": round(k / n, 4) if n else None,
                "ci95": [round(lo, 4), round(hi, 4)] if n else None,
                "low_sample": n < MIN_DISPLAY_N,
            })
        cells.append(row_cells)
    return {"rows": ZONE_ROWS, "cols": ZONE_COLS, "perspective": "taker", "cells": cells}


def shootout_summary(df: pd.DataFrame) -> dict:
    """How often the team kicking first won a decided shootout."""
    so = df[df["phase"] == "shootout"]
    n_shootouts, first_won = 0, 0
    for _, g in so.groupby("match_id"):
        g = g.sort_values("shootout_kick_number")
        goals = g.groupby("team_id")["is_goal"].sum()
        if len(goals) != 2 or goals.iloc[0] == goals.iloc[1]:
            continue
        n_shootouts += 1
        first_team = g.iloc[0]["team_id"]
        if goals.idxmax() == first_team:
            first_won += 1
    lo, hi = wilson_interval(first_won, n_shootouts)
    return {"n_shootouts": n_shootouts, "first_kicker_won": first_won,
            "first_kicker_win_rate": round(first_won / n_shootouts, 4) if n_shootouts else None,
            "ci95": [round(lo, 4), round(hi, 4)]}


class ConstantRate:
    name = "constant"

    def fit(self, df: pd.DataFrame):
        self.rate_ = float(df["label"].mean())
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        return np.full(len(df), self.rate_)


class GroupRate:
    """Group conversion rate shrunk toward the overall rate: (k + K*p0) / (n + K)."""

    def __init__(self, by: list[str], name: str, k: float = SHRINK_K):
        self.by, self.name, self.k = by, name, k

    def fit(self, df: pd.DataFrame):
        self.p0_ = float(df["label"].mean())
        g = df.groupby(self.by)["label"].agg(["sum", "size"])
        self.table_ = ((g["sum"] + self.k * self.p0_) / (g["size"] + self.k)).to_dict()
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        keys = df[self.by].itertuples(index=False, name=None)
        if len(self.by) == 1:
            keys = (k[0] for k in keys)
        return np.array([self.table_.get(k, self.p0_) for k in keys])


class SklearnPrekick:
    def __init__(self, name: str, estimator):
        self.name = name
        self.pipe = Pipeline([
            ("prep", ColumnTransformer([
                ("cat", OneHotEncoder(handle_unknown="ignore"), PREKICK_CATEGORICAL),
                ("num", "passthrough", PREKICK_NUMERIC),
            ], sparse_threshold=0)),
            ("clf", estimator),
        ])

    def fit(self, df: pd.DataFrame):
        self.pipe.fit(df[PREKICK_FEATURES], df["label"])
        return self

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        proba = self.pipe.predict_proba(df[PREKICK_FEATURES])
        return proba[:, list(self.pipe.classes_).index(1)]


def make_predictors() -> list:
    return [
        ConstantRate(),
        GroupRate(["phase"], "phase_rate"),
        GroupRate(["pressure_bucket"], "pressure_rate"),
        SklearnPrekick("logistic_prekick",
                       LogisticRegression(C=0.3, max_iter=2000, random_state=RANDOM_SEED)),
        SklearnPrekick("gbm_prekick",
                       HistGradientBoostingClassifier(max_iter=100, learning_rate=0.05, max_depth=2,
                                                      min_samples_leaf=20, random_state=RANDOM_SEED)),
    ]
