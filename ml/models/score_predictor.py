"""
Scoreline prediction via two independent Poisson regressions.

Model A predicts the home team's expected goals (lambda_home); Model B predicts
the away team's expected goals (lambda_away). Both are sklearn Pipelines built
on the same pivoted single-row feature matrix produced by
ml.features.engineering.build_features().

Features (per DATA_CONTRACT.md rolling stats + confederation one-hot):
    numeric  : home_xgf_avg_5, home_xga_avg_5, home_gf_avg_5, home_ga_avg_5,
               away_xgf_avg_5, away_xga_avg_5, diff_elo, home_is_neutral_venue
    categoric: home_confederation, away_confederation  (one-hot, fixed vocab)

If the xG columns are entirely null/zero (e.g. before 06_backfill_xg.py has
run), callers pass use_xg=False and the models fall back to goal-average
features only.

A predicted scoreline comes from the joint Poisson PMF over lambda_home /
lambda_away, searched up to 7 goals per team.
"""

from __future__ import annotations

import math

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Fixed confederation vocabulary — must match train.CONFEDERATIONS so the
# one-hot columns are stable across train / eval / inference.
CONFEDERATIONS = ["UEFA", "CONMEBOL", "CONCACAF", "CAF", "AFC", "OFC", "OTHER"]
CATEGORICAL = ["home_confederation", "away_confederation"]

# xG-derived numeric features (dropped in the goal-averages-only fallback).
XG_NUMERIC = ["home_xgf_avg_5", "home_xga_avg_5", "away_xgf_avg_5", "away_xga_avg_5"]
# Always-available numeric features.
BASE_NUMERIC = ["home_gf_avg_5", "home_ga_avg_5", "diff_elo", "home_is_neutral_venue"]

MAX_GOALS = 7


def numeric_columns(use_xg: bool = True) -> list[str]:
    return (XG_NUMERIC + BASE_NUMERIC) if use_xg else list(BASE_NUMERIC)


def feature_columns(use_xg: bool = True) -> list[str]:
    return numeric_columns(use_xg) + CATEGORICAL


def prepare_score_features(features: pd.DataFrame, use_xg: bool = True) -> pd.DataFrame:
    """
    Slice + coerce the pivoted feature matrix to the score-model input frame.

    Missing columns are created as NaN (the numeric imputer fills them);
    confederation is coerced to string with an OTHER fallback.
    """
    cols = feature_columns(use_xg)
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
    """Poisson pipeline for the home team's expected goals (lambda_home)."""
    return _make_poisson_pipeline(use_xg)


def make_away_goals_pipeline(use_xg: bool = True) -> Pipeline:
    """Poisson pipeline for the away team's expected goals (lambda_away)."""
    return _make_poisson_pipeline(use_xg)


def _poisson_pmf(k: int, lam: float) -> float:
    lam = max(float(lam), 0.0)
    if lam == 0.0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * lam ** k / math.factorial(k)


def predict_scoreline(home_lambda: float, away_lambda: float,
                      max_goals: int = MAX_GOALS) -> dict:
    """
    Most likely exact scoreline under independent Poisson goal counts.

    Returns {"home_goals": int, "away_goals": int, "probability": float},
    searching 0..max_goals goals per team.
    """
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
