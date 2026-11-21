"""
Regression tests: knockout matches cannot end in a draw.

A level knockout match goes to extra time, then penalties, and someone
advances — so it must never be scored as a plain "draw". These tests lock
in two halves of that fix:

  1. ml.pipeline.predict._apply_knockout_redistribution redistributes the
     model's draw probability onto the two teams by xG share (pure math).
  2. data-pipeline/scripts/05_evaluate_wc2026.py's annotate() credits the
     team that actually advanced on penalties (from the persisted `winner`
     column) by default, scoped to knockout-stage rows only.

The shootout-credited test uses the real GER vs PAR round-of-32 fixture:
regulation ended 1-1 (result="D") but PAR advanced on penalties.
"""

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from ml.pipeline.predict import _apply_knockout_redistribution

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_SCRIPT = PROJECT_ROOT / "data-pipeline" / "scripts" / "05_evaluate_wc2026.py"
ACTUAL_CSV = PROJECT_ROOT / "data-pipeline" / "data" / "wc2026_actual_results.csv"
PRED_JSON = PROJECT_ROOT / "data-pipeline" / "data" / "wc2026_predictions.json"

_spec = importlib.util.spec_from_file_location("evaluate_wc2026", EVAL_SCRIPT)
evaluate_wc2026 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluate_wc2026)


class TestApplyKnockoutRedistribution:
    def test_redistributes_draw_mass_by_xg_share(self):
        p_home, p_draw, p_away = _apply_knockout_redistribution(
            p_home=0.50, p_draw=0.30, p_away=0.20, home_xg=1.5, away_xg=0.5,
        )
        assert p_draw == 0.0
        assert p_home == pytest.approx(0.50 + 0.30 * 0.75)
        assert p_away == pytest.approx(0.20 + 0.30 * 0.25)
        assert p_home + p_draw + p_away == pytest.approx(1.0)

    def test_even_split_when_total_xg_is_zero(self):
        p_home, p_draw, p_away = _apply_knockout_redistribution(
            p_home=0.40, p_draw=0.20, p_away=0.40, home_xg=0.0, away_xg=0.0,
        )
        assert p_draw == 0.0
        assert p_home == pytest.approx(0.50)
        assert p_away == pytest.approx(0.50)


def _load_ger_par_row() -> dict:
    """Real GER vs PAR round-of-32 fixture: 1-1 in regulation, PAR advanced
    on penalties. Sourced from the tracked wc2026_actual_results.csv /
    wc2026_predictions.json (not the gitignored raw martj42 shootouts.csv)."""
    actual = pd.read_csv(ACTUAL_CSV)
    row = actual[(actual.home_team == "GER") & (actual.away_team == "PAR")].iloc[0]
    assert row.result == "D" and row.winner == "PAR", (
        "GER vs PAR fixture data changed — update this test's assumptions"
    )

    preds = json.loads(PRED_JSON.read_text(encoding="utf-8"))
    pred = next(p for p in preds if p["home_team"] == "GER" and p["away_team"] == "PAR")

    return {
        "home_team": "GER",
        "away_team": "PAR",
        "competition_stage": row.competition_stage,
        "result": row.result,
        "winner": row.winner,
        "p_home_win": pred["p_home_win"],
        "p_draw": pred["p_draw"],
        "p_away_win": pred["p_away_win"],
    }


class TestShootoutCreditedScoring:
    def test_credits_shootout_winner_by_default(self):
        df = evaluate_wc2026.annotate(pd.DataFrame([_load_ger_par_row()]))
        actual_outcome = df.iloc[0].actual_outcome
        assert actual_outcome == "away"   # PAR (away team) won on penalties
        assert actual_outcome != "draw"

    def test_opt_out_falls_back_to_goals_based_draw(self):
        df = evaluate_wc2026.annotate(
            pd.DataFrame([_load_ger_par_row()]), credit_shootout=False,
        )
        assert df.iloc[0].actual_outcome == "draw"

    def test_group_stage_draw_is_never_credited(self):
        # Guard: a `winner` value must never override a genuine group-stage
        # draw — group ties have no shootout, so crediting must be scoped to
        # knockout-stage rows only.
        row = _load_ger_par_row()
        row["competition_stage"] = "group"
        df = evaluate_wc2026.annotate(pd.DataFrame([row]))
        assert df.iloc[0].actual_outcome == "draw"
