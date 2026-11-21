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
import math
import sys
from pathlib import Path

import joblib
import pandas as pd

from ml.config import (
    ARTIFACTS_DIR, TARGET_ENCODE, LOG_FORMAT,
    DRAW_CALIBRATION_THRESHOLD, DRAW_CALIBRATION_ALPHA,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

REQUIRED_FIXTURE_COLS = {"match_date", "home_team", "away_team"}


def _apply_draw_calibration(
    p_home: float,
    p_draw: float,
    p_away: float,
    threshold: float,
    alpha: float,
) -> tuple[float, float, float]:
    """
    When the favorite's probability exceeds threshold, redistribute
    alpha * (p_favorite - threshold) probability mass to the draw.
    The favorite's probability is reduced by the same amount.
    The other team's probability is unchanged.
    Renormalize to sum to 1.0.
    """
    home_is_favorite = p_home >= p_away
    favorite = p_home if home_is_favorite else p_away

    if favorite > threshold:
        shift = alpha * (favorite - threshold)
        favorite -= shift
        p_draw += shift

    if home_is_favorite:
        p_home = favorite
    else:
        p_away = favorite

    total = p_home + p_draw + p_away
    if total > 0:
        p_home, p_draw, p_away = p_home / total, p_draw / total, p_away / total
    return p_home, p_draw, p_away


def _apply_knockout_redistribution(
    p_home: float,
    p_draw: float,
    p_away: float,
    home_xg: float,
    away_xg: float,
) -> tuple[float, float, float]:
    """
    Knockout matches cannot end in a draw — a level match goes to extra time,
    then penalties, and one team advances. Redistribute the draw probability
    onto the two teams in proportion to their expected goals, yielding
    advance probabilities. Mirrors ml.pipeline.predict_knockout's formula so
    the two pipelines can't drift apart.
    """
    total_xg = home_xg + away_xg
    if total_xg > 0:
        share_home, share_away = home_xg / total_xg, away_xg / total_xg
    else:
        share_home = share_away = 0.5
    p_home_adv = p_home + p_draw * share_home
    p_away_adv = p_away + p_draw * share_away
    return p_home_adv, 0.0, p_away_adv


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


def predict_match_outcomes(
    fixtures: pd.DataFrame,
    run_id: str | None = None,
    score_run_id: str | None = None,
) -> list[dict]:
    """
    Return match-outcome probabilities for each fixture row.

    Output: one dict per fixture with home_team, away_team, p_home_win,
    p_draw, p_away_win. Reusable by other pipelines (e.g. predict_knockout).

    Knockout-stage fixtures (competition_stage != "group") cannot end in a
    draw — a level match goes to extra time then penalties. For those rows
    p_draw is redistributed onto p_home_win/p_away_win by expected-goals
    share (see _apply_knockout_redistribution), so p_draw is always 0.0 and
    the two win probabilities are effectively advance probabilities.
    """
    run_dir = _resolve_run_dir(run_id)

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

    if "competition_stage" in fixtures.columns:
        knockout_mask = (
            fixtures["competition_stage"].fillna("group").astype(str)
            .str.strip().str.lower() != "group"
        ).tolist()
    else:
        knockout_mask = [False] * len(fixtures)

    xg_by_row: dict[int, tuple[float, float]] = {}
    if any(knockout_mask):
        # Lazy import: predict_scores imports from this module at load time,
        # so importing it eagerly at module scope would be circular.
        from ml.pipeline.predict_scores import score_fixtures
        scores = score_fixtures(fixtures, run_id=score_run_id)
        xg_by_row = {i: (s["home_xg"], s["away_xg"]) for i, s in enumerate(scores)}

    predictions = []
    for i, (f, p) in enumerate(zip(fixtures.itertuples(), proba)):
        # Null-safe guard: a degenerate / all-zero feature row can yield NaN
        # from the calibrated model. Coerce any None/NaN probability to 0.0.
        probs = [0.0 if (v is None or math.isnan(float(v))) else float(v) for v in p]
        pmap = dict(zip(classes, probs))

        p_home = round(float(pmap.get(TARGET_ENCODE["H"], 0.0)), 4)
        p_draw = round(float(pmap.get(TARGET_ENCODE["D"], 0.0)), 4)
        p_away = round(float(pmap.get(TARGET_ENCODE["A"], 0.0)), 4)

        # If both teams are unknown (all-zero feature vector) the model has no
        # signal — emit a uniform distribution instead of NaN/degenerate output.
        all_zero = all(v == 0.0 for v in rows[i].values())
        if all_zero or (p_home + p_draw + p_away) == 0.0:
            p_home = p_draw = p_away = 0.333
        elif knockout_mask[i]:
            home_xg, away_xg = xg_by_row[i]
            p_home, p_draw, p_away = _apply_knockout_redistribution(
                p_home, p_draw, p_away, home_xg, away_xg,
            )
            p_home, p_draw, p_away = round(p_home, 4), round(p_draw, 4), round(p_away, 4)
        else:
            p_home, p_draw, p_away = _apply_draw_calibration(
                p_home, p_draw, p_away,
                DRAW_CALIBRATION_THRESHOLD, DRAW_CALIBRATION_ALPHA,
            )
            p_home, p_draw, p_away = round(p_home, 4), round(p_draw, 4), round(p_away, 4)

        predictions.append({
            "home_team":  f.home_team,
            "away_team":  f.away_team,
            "p_home_win": p_home,
            "p_draw":     p_draw,
            "p_away_win": p_away,
        })
    return predictions


def load_fixtures(path_str: str) -> pd.DataFrame:
    """Read a fixtures CSV and validate the required columns."""
    fix_path = Path(path_str)
    if not fix_path.exists():
        logger.error(f"Fixtures file not found: {fix_path}")
        sys.exit(1)
    fixtures = pd.read_csv(fix_path, comment="#")
    if not REQUIRED_FIXTURE_COLS.issubset(fixtures.columns):
        logger.error(f"Fixtures CSV must contain at least: {REQUIRED_FIXTURE_COLS}")
        sys.exit(1)
    return fixtures


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict WC fixtures")
    parser.add_argument("--fixtures", required=True, help="CSV of fixtures to predict")
    parser.add_argument("--run-id", default=None, help="Run ID (default: latest)")
    parser.add_argument("--score-run-id", default=None,
                        help="Score run ID for knockout-fixture xG redistribution "
                             "(default: latest)")
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures)
    predictions = predict_match_outcomes(
        fixtures, run_id=args.run_id, score_run_id=args.score_run_id,
    )
    print(json.dumps(predictions, indent=2))


if __name__ == "__main__":
    main()
