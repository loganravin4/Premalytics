"""
WC-06 prediction CLI.

Usage:
    python -m ml.pipeline.predict --fixtures path/to/wc_fixtures.csv [--run-id RUN_ID]

Fixtures CSV columns:
    match_date, home_team, away_team, is_neutral_venue,
    competition_id, competition_stage

Output: JSON array on stdout, one object per fixture:
    [{"home_team": "BRA", "away_team": "ARG",
      "p_home_win": 0.45, "p_draw": 0.28, "p_away_win": 0.27}, ...]

MVP feature-construction shortcut
---------------------------------
Building full leakage-safe rolling features for an unplayed fixture is
complex. For the MVP we instead reuse the pivoted feature matrix saved at
training time (features.joblib). For each team we look up its MOST RECENT
appearance in that matrix and take that match's per-team feature values
(the home_* columns if the team last played at home, else the away_*
columns). Those values populate the fixture's home_*/away_* slots; each
diff_* feature is recomputed as home - away. Teams with no WC history get
all-zero features. The fixture's own match_date / venue / competition
columns are metadata only and are NOT used as model inputs.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

from ml.config import ARTIFACTS_DIR, TARGET_ENCODE, LOG_FORMAT

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

REQUIRED_FIXTURE_COLS = {"match_date", "home_team", "away_team"}


def _resolve_run_dir(run_id: str | None) -> Path:
    if run_id:
        d = ARTIFACTS_DIR / run_id
        if not d.exists():
            raise FileNotFoundError(f"Run directory not found: {d}")
        return d
    latest = ARTIFACTS_DIR / "latest_run.txt"
    if not latest.exists():
        raise FileNotFoundError("No run found. Train first: python -m ml.pipeline.train")
    return ARTIFACTS_DIR / latest.read_text().strip()


def _team_latest_vector(features: pd.DataFrame, feature_cols: list[str], team: str) -> dict:
    """
    Return {base_feature_name: value} from the team's most recent match in the
    training feature matrix. Reads home_* columns if the team last played at
    home, else away_* columns. Returns {} for teams with no history.

    `features` is chronologically sorted by build_features, so iloc[-1] is the
    team's latest appearance on each side.
    """
    appearances = []
    home_rows = features[features["home_team"] == team]
    away_rows = features[features["away_team"] == team]
    if not home_rows.empty:
        appearances.append(("home_", home_rows.iloc[-1]))
    if not away_rows.empty:
        appearances.append(("away_", away_rows.iloc[-1]))
    if not appearances:
        return {}

    prefix, row = max(appearances, key=lambda pr: pr[1]["match_date"])
    return {
        c[len(prefix):]: row[c]
        for c in feature_cols
        if c.startswith(prefix)
    }


def _fixture_feature_row(features: pd.DataFrame, feature_cols: list[str],
                         home_team: str, away_team: str) -> dict:
    """Assemble one feature row for a fixture from each team's latest form."""
    home_vec = _team_latest_vector(features, feature_cols, home_team)
    away_vec = _team_latest_vector(features, feature_cols, away_team)

    row = {}
    for c in feature_cols:
        if c.startswith("home_"):
            row[c] = home_vec.get(c[5:], 0.0)
        elif c.startswith("away_"):
            row[c] = away_vec.get(c[5:], 0.0)
        elif c.startswith("diff_"):
            base = c[5:]
            row[c] = home_vec.get(base, 0.0) - away_vec.get(base, 0.0)
        else:
            row[c] = 0.0
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict WC fixtures")
    parser.add_argument("--fixtures", required=True, help="CSV of fixtures to predict")
    parser.add_argument("--run-id", default=None, help="Run ID (default: latest)")
    args = parser.parse_args()

    run_dir = _resolve_run_dir(args.run_id)

    fix_path = Path(args.fixtures)
    if not fix_path.exists():
        logger.error(f"Fixtures file not found: {fix_path}")
        sys.exit(1)

    fixtures = pd.read_csv(fix_path, comment="#")
    if not REQUIRED_FIXTURE_COLS.issubset(fixtures.columns):
        logger.error(f"Fixtures CSV must contain at least: {REQUIRED_FIXTURE_COLS}")
        sys.exit(1)

    model = joblib.load(run_dir / "gradient_boosting.joblib")
    feature_cols = json.loads((run_dir / "feature_cols.json").read_text())
    features = joblib.load(run_dir / "features.joblib")
    logger.info(f"Loaded {len(fixtures)} fixtures; predicting with run {run_dir.name}")

    rows = [
        _fixture_feature_row(features, feature_cols, f.home_team, f.away_team)
        for f in fixtures.itertuples()
    ]
    X = pd.DataFrame(rows, columns=feature_cols).fillna(0.0).astype(float)

    proba = model.predict_proba(X)
    classes = list(model.classes_)  # encoded ints, sorted: [0, 1, 2]

    predictions = []
    for f, p in zip(fixtures.itertuples(), proba):
        pmap = dict(zip(classes, p))
        predictions.append({
            "home_team":  f.home_team,
            "away_team":  f.away_team,
            "p_home_win": round(float(pmap.get(TARGET_ENCODE["H"], 0.0)), 4),
            "p_draw":     round(float(pmap.get(TARGET_ENCODE["D"], 0.0)), 4),
            "p_away_win": round(float(pmap.get(TARGET_ENCODE["A"], 0.0)), 4),
        })

    print(json.dumps(predictions, indent=2))


if __name__ == "__main__":
    main()
