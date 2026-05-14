"""
Predict upcoming fixtures.

Usage:
    python -m ml.pipeline.predict --fixtures fixtures.csv [--run-id RUN_ID]

fixtures.csv format (one row per match):
    match_date,home_team,away_team
    2025-05-10,Arsenal,Chelsea
    2025-05-10,Liverpool,Manchester City

Output: CSV with H/D/A probabilities per fixture.
"""

import argparse
import json
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ml.config import (
    ARTIFACTS_DIR, TARGET_CLASSES, LOG_FORMAT,
    SEASONS_TRAIN, SEASONS_VALID, SEASONS_TEST,
)
from ml.features.loader import load_raw_matches
from ml.features.engineering import (
    build_team_features, build_h2h_features, get_feature_columns,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)


def _load_model(run_dir: Path, model_name: str = "gradient_boost"):
    model_path = run_dir / f"{model_name}.pkl"
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    with open(model_path, "rb") as f:
        return pickle.load(f)


def _get_run_dir(run_id: str | None) -> Path:
    if run_id:
        return ARTIFACTS_DIR / run_id
    latest = ARTIFACTS_DIR / "latest_run.txt"
    if not latest.exists():
        raise FileNotFoundError("No run found. Train first: python -m ml.pipeline.train")
    return ARTIFACTS_DIR / latest.read_text().strip()


def _build_current_team_stats(all_seasons: list[str]) -> pd.DataFrame:
    """
    Load historical data and compute rolling features for each team.
    The last computed feature row for each team represents their current form.
    """
    raw = load_raw_matches(seasons=all_seasons)
    return build_team_features(raw)


def predict_fixtures(
    fixtures: list[dict],
    historical_df: pd.DataFrame,
    model,
    feature_cols: list[str],
) -> pd.DataFrame:
    """
    Generate predictions for a list of upcoming fixtures.

    Args:
        fixtures:      List of dicts with keys: match_date, home_team, away_team
        historical_df: Team-feature enriched dual-row DataFrame (from build_team_features)
        model:         Fitted sklearn-compatible classifier
        feature_cols:  Ordered feature column list from training

    Returns:
        DataFrame with columns: match_date, home_team, away_team, prob_H, prob_D, prob_A, predicted
    """
    results = []

    for fix in fixtures:
        match_date = pd.to_datetime(fix["match_date"])
        home_team  = fix["home_team"]
        away_team  = fix["away_team"]

        # Get the most recent feature row for each team (all matches before match_date)
        home_hist = historical_df[
            (historical_df["team_id"] == home_team) &
            (historical_df["match_date"] < match_date)
        ].sort_values("match_date")

        away_hist = historical_df[
            (historical_df["team_id"] == away_team) &
            (historical_df["match_date"] < match_date)
        ].sort_values("match_date")

        if home_hist.empty or away_hist.empty:
            logger.warning(f"No history found for {home_team} or {away_team} before {match_date.date()}")
            continue

        home_row = home_hist.iloc[-1]
        away_row = away_hist.iloc[-1]

        # Build feature vector in training order
        # home_ prefixed features come from home team's last row
        # away_ prefixed features come from away team's last row
        feature_vec = {}
        for col in feature_cols:
            if col.startswith("home_"):
                src_col = col[5:]  # strip 'home_'
                feature_vec[col] = home_row.get(src_col, np.nan)
            elif col.startswith("away_"):
                src_col = col[5:]  # strip 'away_'
                feature_vec[col] = away_row.get(src_col, np.nan)
            else:
                feature_vec[col] = np.nan

        X = np.array([[feature_vec.get(c, np.nan) for c in feature_cols]])
        proba = model.predict_proba(X)[0]

        # Map to TARGET_CLASSES order
        classes = getattr(model, "classes_", TARGET_CLASSES)
        proba_dict = dict(zip(classes, proba))

        results.append({
            "match_date": match_date.date(),
            "home_team":  home_team,
            "away_team":  away_team,
            "prob_H":     round(proba_dict.get("H", 0.0), 4),
            "prob_D":     round(proba_dict.get("D", 0.0), 4),
            "prob_A":     round(proba_dict.get("A", 0.0), 4),
            "predicted":  max(proba_dict, key=proba_dict.get),
        })

    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict upcoming EPL fixtures")
    parser.add_argument("--fixtures", required=True, help="CSV with match_date,home_team,away_team")
    parser.add_argument("--run-id",   default=None,  help="Run ID (default: latest)")
    parser.add_argument("--model",    default="gradient_boost", help="Model name")
    parser.add_argument("--output",   default="predictions.csv", help="Output file")
    args = parser.parse_args()

    run_dir = _get_run_dir(args.run_id)
    model   = _load_model(run_dir, args.model)

    feat_path = run_dir / "feature_cols.json"
    if not feat_path.exists():
        raise FileNotFoundError(f"Feature column list not found: {feat_path}")
    feature_cols = json.loads(feat_path.read_text())

    # Load fixtures file
    fix_path = Path(args.fixtures)
    if not fix_path.exists():
        logger.error(f"Fixtures file not found: {fix_path}")
        sys.exit(1)

    fixtures_df = pd.read_csv(fix_path)
    required    = {"match_date", "home_team", "away_team"}
    if not required.issubset(fixtures_df.columns):
        logger.error(f"Fixtures CSV must have columns: {required}")
        sys.exit(1)

    fixtures = fixtures_df.to_dict(orient="records")
    logger.info(f"Loaded {len(fixtures)} fixtures from {fix_path}")

    # Build current team stats from all historical data
    all_seasons = SEASONS_TRAIN + SEASONS_VALID + SEASONS_TEST
    logger.info("Building current team form from historical data...")
    hist_df = _build_current_team_stats(all_seasons)

    predictions = predict_fixtures(fixtures, hist_df, model, feature_cols)

    if predictions.empty:
        logger.warning("No predictions generated — check team names match training data")
        sys.exit(1)

    out_path = Path(args.output)
    predictions.to_csv(out_path, index=False)
    logger.info(f"Predictions saved to {out_path}")
    print(predictions.to_string(index=False))


if __name__ == "__main__":
    main()
