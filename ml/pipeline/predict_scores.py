"""
Scoreline prediction CLI.

Predicts expected goals (lambda) for each team in a fixture using the two
Poisson models from the latest score run, then reports the single most likely
exact scoreline under the joint Poisson PMF.

Per-fixture features are assembled the same way as ml.pipeline.predict: each
team's most recent appearance in the saved feature matrix supplies its rolling
form (goals, xG, ELO, confederation).

Usage:
    python -m ml.pipeline.predict_scores --fixtures path/to/fixtures.csv

Output (stdout JSON array), one object per fixture:
    {"home_team": "ESP", "away_team": "ARG",
     "predicted_home_goals": 1, "predicted_away_goals": 1,
     "most_likely_score": "1-1", "p_score": 0.087,
     "home_xg": 1.42, "away_xg": 1.18}
"""

import argparse
import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from ml.config import ARTIFACTS_DIR, ELO_INITIAL, LOG_FORMAT
from ml.pipeline.predict import _team_latest_vector, fixture_cutoffs, load_fixtures
from ml.models.score_predictor import (
    prepare_score_features, predict_scoreline,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def _resolve_score_run(run_id: str | None = None) -> Path:
    if run_id:
        d = ARTIFACTS_DIR / run_id
        if not d.exists():
            raise FileNotFoundError(f"Score run not found: {d}")
        return d
    latest = ARTIFACTS_DIR / "latest_score_run.txt"
    if not latest.exists():
        raise FileNotFoundError(
            "No score run found. Train first: python -m ml.pipeline.train_scores"
        )
    return ARTIFACTS_DIR / latest.read_text().strip()


def _fixture_score_row(features: pd.DataFrame, prefixed_cols: list[str],
                       home_team: str, away_team: str, is_neutral: float,
                       before: pd.Timestamp | None = None) -> dict:
    """Assemble one score-model feature row from each team's latest form
    (rows dated on/after `before` are ignored, see predict.fixture_cutoffs)."""
    home_vec = _team_latest_vector(features, prefixed_cols, home_team, before)
    away_vec = _team_latest_vector(features, prefixed_cols, away_team, before)

    def g(vec, key, default=0.0):
        v = vec.get(key, default)
        return default if v is None else v

    return {
        "home_xgf_avg_5": g(home_vec, "xgf_avg_5"),
        "home_xga_avg_5": g(home_vec, "xga_avg_5"),
        "home_gf_avg_5":  g(home_vec, "gf_avg_5"),
        "home_ga_avg_5":  g(home_vec, "ga_avg_5"),
        "away_xgf_avg_5": g(away_vec, "xgf_avg_5"),
        "away_xga_avg_5": g(away_vec, "xga_avg_5"),
        "diff_elo":       g(home_vec, "elo", ELO_INITIAL) - g(away_vec, "elo", ELO_INITIAL),
        "home_is_neutral_venue": float(is_neutral),
        "home_confederation": g(home_vec, "confederation", "OTHER") or "OTHER",
        "away_confederation": g(away_vec, "confederation", "OTHER") or "OTHER",
    }


def score_fixtures(fixtures: pd.DataFrame, run_id: str | None = None,
                   as_of: str | None = None) -> list[dict]:
    """Return scoreline predictions (list of dicts) for each fixture row."""
    run_dir = _resolve_score_run(run_id)
    meta = json.loads((run_dir / "score_feature_cols.json").read_text())
    use_xg = bool(meta.get("use_xg", True))

    home_model = joblib.load(run_dir / "home_goals.joblib")
    away_model = joblib.load(run_dir / "away_goals.joblib")
    features = joblib.load(run_dir / "score_features.joblib")
    logger.info("Loaded %d fixtures; scoring with run %s (use_xg=%s)",
                len(fixtures), run_dir.name, use_xg)

    prefixed_cols = [c for c in features.columns
                     if c.startswith("home_") or c.startswith("away_")]

    neutral = (fixtures["is_neutral_venue"] if "is_neutral_venue" in fixtures.columns
               else pd.Series([True] * len(fixtures)))
    cutoffs = fixture_cutoffs(fixtures, as_of)
    rows = [
        _fixture_score_row(features, prefixed_cols, f.home_team, f.away_team,
                           bool(neutral.iloc[i]), cutoffs[i])
        for i, f in enumerate(fixtures.itertuples())
    ]
    X = prepare_score_features(pd.DataFrame(rows), use_xg)

    lambda_home = home_model.predict(X)
    lambda_away = away_model.predict(X)

    out = []
    for i, f in enumerate(fixtures.itertuples()):
        lh = float(max(lambda_home[i], 0.0))
        la = float(max(lambda_away[i], 0.0))
        sl = predict_scoreline(lh, la)
        out.append({
            "home_team": f.home_team,
            "away_team": f.away_team,
            "predicted_home_goals": sl["home_goals"],
            "predicted_away_goals": sl["away_goals"],
            "most_likely_score": f"{sl['home_goals']}-{sl['away_goals']}",
            "p_score": sl["probability"],
            "home_xg": round(lh, 2),
            "away_xg": round(la, 2),
        })
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict scorelines for WC fixtures")
    parser.add_argument("--fixtures", required=True, help="CSV of fixtures to predict")
    parser.add_argument("--run-id", default=None, help="Score run ID (default: latest)")
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures)
    print(json.dumps(score_fixtures(fixtures, run_id=args.run_id), indent=2))


if __name__ == "__main__":
    main()
