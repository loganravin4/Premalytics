from __future__ import annotations

import math

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Must match train.CONFEDERATIONS so one-hot columns are stable across train, eval and inference.
CONFEDERATIONS = ["UEFA", "CONMEBOL", "CONCACAF", "CAF", "AFC", "OFC", "OTHER"]
CATEGORICAL = ["home_confederation", "away_confederation"]

# Dropped (use_xg=False) when xG is still null because 06_backfill_xg.py hasn't run.
XG_NUMERIC = ["home_xgf_avg_5", "home_xga_avg_5", "away_xgf_avg_5", "away_xga_avg_5"]
BASE_NUMERIC = ["home_gf_avg_5", "home_ga_avg_5", "diff_elo", "home_is_neutral_venue"]

MAX_GOALS = 7


def numeric_columns(use_xg: bool = True) -> list[str]:
    return (XG_NUMERIC + BASE_NUMERIC) if use_xg else list(BASE_NUMERIC)


def feature_columns(use_xg: bool = True) -> list[str]:
    return numeric_columns(use_xg) + CATEGORICAL


def prepare_score_features(features: pd.DataFrame, use_xg: bool = True) -> pd.DataFrame:
    cols = feature_columns(use_xg)
    # Missing columns become NaN for the pipeline's imputer to fill.
    X = features.reindex(columns=cols).copy()
    for c in numeric_columns(use_xg):
        X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
    for c in CATEGORICAL:
        X[c] = X[c].fillna("OTHER").astype(str)
    return X


def _make_poisson_pipeline(use_xg: bool) -> Pipeline:
    num = numeric_columns(use_xg)
    pre = ColumnTransformer(
        transformers=[
            ("num", Pipeline([
                ("impute", SimpleImputer(strategy="constant", fill_value=0.0)),
                ("scale", StandardScaler()),
            ]), num),
            ("cat", OneHotEncoder(
                categories=[CONFEDERATIONS, CONFEDERATIONS],
                handle_unknown="ignore",
            ), CATEGORICAL),
        ],
    )
    return Pipeline([
        ("prep", pre),
        ("reg", PoissonRegressor(alpha=1e-4, max_iter=1000)),
    ])


def make_home_goals_pipeline(use_xg: bool = True) -> Pipeline:
    return _make_poisson_pipeline(use_xg)


def make_away_goals_pipeline(use_xg: bool = True) -> Pipeline:
    return _make_poisson_pipeline(use_xg)


def _poisson_pmf(k: int, lam: float) -> float:
    lam = max(float(lam), 0.0)
    if lam == 0.0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def predict_scoreline(home_lambda: float, away_lambda: float,
                      max_goals: int = MAX_GOALS) -> dict:
    home_pmf = [_poisson_pmf(i, home_lambda) for i in range(max_goals + 1)]
    away_pmf = [_poisson_pmf(j, away_lambda) for j in range(max_goals + 1)]

    best_i, best_j, best_p = 0, 0, -1.0
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = home_pmf[i] * away_pmf[j]
            if p > best_p:
                best_i, best_j, best_p = i, j, p
    return {"home_goals": best_i, "away_goals": best_j,
            "probability": round(best_p, 4)}
