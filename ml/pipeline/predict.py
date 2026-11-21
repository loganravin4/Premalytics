"""Predict home/draw/away probabilities for a fixtures CSV, printed as JSON.

Usage: python -m ml.pipeline.predict --fixtures wc_fixtures.csv [--run-id RUN_ID] [--as-of YYYY-MM-DD]
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
    """Move alpha * (p_favorite - threshold) from the favorite to the draw, then renormalize."""
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
    """Split the draw mass by xG share, turning win probabilities into advance probabilities."""
    # Must stay identical to ml.pipeline.predict_knockout's formula.
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


def _team_latest_vector(features: pd.DataFrame, feature_cols: list[str], team: str,
                        before: pd.Timestamp | None = None) -> dict:
    # features.joblib is the whole corpus; without this cutoff a retrospective reads the fixture's own result.
    if before is not None:
        features = features[pd.to_datetime(features["match_date"]) < before]
    appearances = []
    home_rows = features[features["home_team"] == team]
    away_rows = features[features["away_team"] == team]
    if not home_rows.empty:
        # build_features sorts chronologically, so iloc[-1] is the latest appearance.
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


def _load_ensemble(run_dir: Path) -> dict | None:
    path = run_dir / "ensemble.json"
    return json.loads(path.read_text()) if path.exists() else None


def _ensemble_proba(ensemble: dict, run_dir: Path, gbm_proba, fixtures: pd.DataFrame):
    """Blend GBM with Dixon-Coles and apply the walk-forward calibration, in model class order (A, D, H)."""
    import numpy as np
    from ml.models.calibration import _power
    from ml.models.metrics import from_model_proba, normalize

    dc = joblib.load(run_dir / "dixon_coles.joblib")
    if "is_neutral_venue" in fixtures.columns:
        neutral = (fixtures["is_neutral_venue"].astype(str).str.strip().str.lower()
                   .isin(["true", "1", "1.0", "yes"])).to_numpy()
    else:
        neutral = np.ones(len(fixtures), dtype=bool)
    p_dc = dc.predict_outcome_proba(fixtures["home_team"], fixtures["away_team"], neutral)
    p_gbm = from_model_proba(np.nan_to_num(np.asarray(gbm_proba, dtype=float)))
    w = float(ensemble["blend_weight_gbm"])
    p = normalize(w * p_gbm + (1.0 - w) * p_dc)
    p = _power(p, float(ensemble.get("temperature", 1.0)), float(ensemble.get("draw_bias", 0.0)))
    return p[:, [2, 1, 0]]


def fixture_cutoffs(fixtures: pd.DataFrame, as_of: str | None = None) -> list:
    """Per-fixture feature cutoff: match_date capped at as_of; None when neither is known."""
    cap = pd.Timestamp(as_of) if as_of else None
    dates = (pd.to_datetime(fixtures["match_date"], errors="coerce")
             if "match_date" in fixtures.columns else pd.Series([pd.NaT] * len(fixtures)))
    out = []
    for d in dates:
        d = None if pd.isna(d) else pd.Timestamp(d)
        if cap is not None:
            d = cap if d is None else min(d, cap)
        out.append(d)
    return out


def _fixture_feature_row(features: pd.DataFrame, feature_cols: list[str],
                         home_team: str, away_team: str,
                         before: pd.Timestamp | None = None) -> dict:
    home_vec = _team_latest_vector(features, feature_cols, home_team, before)
    away_vec = _team_latest_vector(features, feature_cols, away_team, before)

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
            # Venue and competition columns are metadata only, never model inputs here.
            row[c] = 0.0
    return row


def predict_match_outcomes(
    fixtures: pd.DataFrame,
    run_id: str | None = None,
    score_run_id: str | None = None,
    as_of: str | None = None,
    include_raw: bool = False,
) -> list[dict]:
    run_dir = _resolve_run_dir(run_id)

    model = joblib.load(run_dir / "gradient_boosting.joblib")
    feature_cols = json.loads((run_dir / "feature_cols.json").read_text())
    features = joblib.load(run_dir / "features.joblib")
    logger.info(f"Loaded {len(fixtures)} fixtures; predicting with run {run_dir.name}")

    cutoffs = fixture_cutoffs(fixtures, as_of)
    rows = [
        _fixture_feature_row(features, feature_cols, f.home_team, f.away_team, cut)
        for f, cut in zip(fixtures.itertuples(), cutoffs)
    ]
    X = pd.DataFrame(rows, columns=feature_cols).fillna(0.0).astype(float)

    proba = model.predict_proba(X)
    classes = list(model.classes_)

    ensemble = _load_ensemble(run_dir)
    if ensemble is not None:
        proba = _ensemble_proba(ensemble, run_dir, proba, fixtures)
        logger.info("Serving ensemble %s (gbm weight %.2f)",
                    ensemble["variant"], ensemble["blend_weight_gbm"])

    # Knockouts can't end level (extra time, then penalties), so their p_draw is redistributed to 0.
    if "competition_stage" in fixtures.columns:
        knockout_mask = (
            fixtures["competition_stage"].fillna("group").astype(str)
            .str.strip().str.lower() != "group"
        ).tolist()
    else:
        knockout_mask = [False] * len(fixtures)

    xg_by_row: dict[int, tuple[float, float]] = {}
    if any(knockout_mask):
        # Imported here because predict_scores imports this module (circular import).
        from ml.pipeline.predict_scores import score_fixtures
        scores = score_fixtures(fixtures, run_id=score_run_id, as_of=as_of)
        xg_by_row = {i: (s["home_xg"], s["away_xg"]) for i, s in enumerate(scores)}

    predictions = []
    for i, (f, p) in enumerate(zip(fixtures.itertuples(), proba)):
        # A degenerate all-zero feature row can make the calibrated model return NaN.
        probs = [0.0 if (v is None or math.isnan(float(v))) else float(v) for v in p]
        pmap = dict(zip(classes, probs))

        p_home = round(float(pmap.get(TARGET_ENCODE["H"], 0.0)), 4)
        p_draw = round(float(pmap.get(TARGET_ENCODE["D"], 0.0)), 4)
        p_away = round(float(pmap.get(TARGET_ENCODE["A"], 0.0)), 4)
        raw = (p_home, p_draw, p_away)

        # Both teams unknown means no signal, so fall back to uniform.
        all_zero = all(v == 0.0 for v in rows[i].values())
        if all_zero or (p_home + p_draw + p_away) == 0.0:
            p_home = p_draw = p_away = 0.333
        elif knockout_mask[i]:
            home_xg, away_xg = xg_by_row[i]
            p_home, p_draw, p_away = _apply_knockout_redistribution(
                p_home, p_draw, p_away, home_xg, away_xg,
            )
            p_home, p_draw, p_away = round(p_home, 4), round(p_draw, 4), round(p_away, 4)
        elif ensemble is None:
            # The ensemble is already calibrated walk-forward; this threshold rule is for plain GBM only.
            p_home, p_draw, p_away = _apply_draw_calibration(
                p_home, p_draw, p_away,
                DRAW_CALIBRATION_THRESHOLD, DRAW_CALIBRATION_ALPHA,
            )
            p_home, p_draw, p_away = round(p_home, 4), round(p_draw, 4), round(p_away, 4)

        pred = {
            "home_team":  f.home_team,
            "away_team":  f.away_team,
            "p_home_win": p_home,
            "p_draw":     p_draw,
            "p_away_win": p_away,
        }
        if include_raw:
            if all_zero or sum(raw) == 0.0:
                raw = (0.333, 0.333, 0.333)
            pred.update({"p_home_win_raw": raw[0], "p_draw_raw": raw[1],
                         "p_away_win_raw": raw[2]})
        predictions.append(pred)
    return predictions


def load_fixtures(path_str: str) -> pd.DataFrame:
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
    parser.add_argument("--as-of", default=None,
                        help="Freeze team form at this date (YYYY-MM-DD); rows on/after "
                             "it are ignored. Use the tournament start for retrospectives.")
    parser.add_argument("--include-raw", action="store_true",
                        help="Also emit pre-calibration p_*_raw probabilities")
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures)
    predictions = predict_match_outcomes(
        fixtures, run_id=args.run_id, score_run_id=args.score_run_id,
        as_of=args.as_of, include_raw=args.include_raw,
    )
    print(json.dumps(predictions, indent=2))


if __name__ == "__main__":
    main()
