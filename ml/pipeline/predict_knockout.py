"""
Knockout-stage prediction.

Draws are not final outcomes in knockout football — a level match is decided
in extra time / penalties. This wrapper combines the match-outcome model
(ml.pipeline.predict) with the score model (ml.pipeline.predict_scores) and
redistributes the draw probability onto the two teams in proportion to their
expected goals, yielding advance probabilities.

    total_xg = home_xg + away_xg
    p_home_advances = p_home_win + p_draw * (home_xg / total_xg)
    p_away_advances = p_away_win + p_draw * (away_xg / total_xg)
    (50/50 split of the draw mass when total_xg == 0)

Usage:
    python -m ml.pipeline.predict_knockout \
        --fixtures path/to/fixtures.csv --stage round_of_32
"""

import argparse
import json
import logging

from ml.config import LOG_FORMAT
from ml.pipeline.predict import predict_match_outcomes, load_fixtures
from ml.pipeline.predict_scores import score_fixtures

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

KNOCKOUT_STAGES = ["round_of_32", "round_of_16", "quarter_final", "semi_final", "final"]
DRAW_NOTE = "Draw likely — decided by extra time / penalties"


def predict_knockout(fixtures, stage: str, run_id: str | None = None,
                     score_run_id: str | None = None) -> list[dict]:
    """Advance probabilities + predicted score for each knockout fixture."""
    outcomes = predict_match_outcomes(fixtures, run_id=run_id)
    scores = score_fixtures(fixtures, run_id=score_run_id)

    results = []
    for oc, sc in zip(outcomes, scores):
        p_home_win = oc["p_home_win"]
        p_draw = oc["p_draw"]
        p_away_win = oc["p_away_win"]
        home_xg = sc["home_xg"]
        away_xg = sc["away_xg"]

        total_xg = home_xg + away_xg
        if total_xg <= 0:
            share_home = share_away = 0.5
        else:
            share_home = home_xg / total_xg
            share_away = away_xg / total_xg

        p_home_adv = p_home_win + p_draw * share_home
        p_away_adv = p_away_win + p_draw * share_away

        # A level predicted scoreline means the tie would go to ET/pens.
        is_level = sc["predicted_home_goals"] == sc["predicted_away_goals"]
        if is_level:
            note = DRAW_NOTE
        else:
            favored = oc["home_team"] if p_home_adv >= p_away_adv else oc["away_team"]
            note = f"{favored} favored to advance in regulation"

        results.append({
            "home_team": oc["home_team"],
            "away_team": oc["away_team"],
            "stage": stage,
            "p_home_advances": round(p_home_adv, 4),
            "p_away_advances": round(p_away_adv, 4),
            "predicted_score": sc["most_likely_score"],
            "note": note,
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Predict knockout-stage advancement")
    parser.add_argument("--fixtures", required=True, help="CSV of fixtures to predict")
    parser.add_argument("--stage", required=True, choices=KNOCKOUT_STAGES,
                        help="Knockout stage label to apply to these fixtures")
    parser.add_argument("--run-id", default=None, help="Match run ID (default: latest)")
    parser.add_argument("--score-run-id", default=None, help="Score run ID (default: latest)")
    args = parser.parse_args()

    fixtures = load_fixtures(args.fixtures)
    results = predict_knockout(fixtures, args.stage,
                               run_id=args.run_id, score_run_id=args.score_run_id)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
