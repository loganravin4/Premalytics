"""
Tests for the penalty dataset builder (zone mapping, shootout state, pre-kick
context) and the penalty baselines / evaluation (no post-kick features,
rolling origin trains only on earlier tournaments).
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.models.penalty_baselines import (
    POSTKICK_COLUMNS, PREKICK_FEATURES, ZONES, ConstantRate, GroupRate,
    add_prekick_features, conversion_table, make_predictors, order_bucket, zone_grid,
)
from ml.pipeline.evaluate_penalties import aggregates_for, rolling_origin_predictions

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / "data-pipeline" / "scripts" / "penalties" / "01_build_penalty_csv.py"


@pytest.fixture(scope="module")
def b():
    spec = importlib.util.spec_from_file_location("penalty_builder", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Zone mapping
# ---------------------------------------------------------------------------

class TestZoneMapping:
    @pytest.mark.parametrize("y,z,zone", [
        (37.0, 0.3, "low_left"),      # taker's left = smaller y
        (40.0, 0.3, "low_center"),
        (43.0, 0.3, "low_right"),
        (37.0, 1.2, "mid_left"),
        (40.0, 2.5, "high_center"),
        (43.5, 2.0, "high_right"),
    ])
    def test_three_by_three(self, b, y, z, zone):
        assert b.placement_zone(y, z) == zone

    def test_edges(self, b):
        assert b.placement_col(38.66) == "left"
        assert b.placement_col(38.67) == "center"
        assert b.placement_col(41.34) == "right"
        assert b.placement_row(0.88) == "low"
        assert b.placement_row(0.89) == "mid"

    def test_misses_map_to_nearest_edge_zone(self, b):
        assert b.placement_zone(33.0, 0.5) == "low_left"     # wide of the left post
        assert b.placement_zone(40.0, 3.5) == "high_center"  # over the bar
        assert b.is_on_target(33.0, 0.5) is False
        assert b.is_on_target(40.0, 3.5) is False
        assert b.is_on_target(40.0, 1.0) is True

    def test_missing_end_location(self, b):
        assert b.placement_zone(None, None) is None
        assert b.placement_zone(40.0, float("nan")) is None

    def test_all_zone_ids_are_known(self, b):
        ys = np.linspace(35, 45, 21)
        zs = np.linspace(0, 3, 13)
        seen = {b.placement_zone(y, z) for y in ys for z in zs}
        assert seen == set(ZONES)

    @pytest.mark.parametrize("foot,col,side", [
        ("right", "left", "natural"), ("right", "right", "across"),
        ("left", "right", "natural"), ("left", "left", "across"),
        ("right", "center", "center"), ("other", "left", None),
    ])
    def test_foot_side(self, b, foot, col, side):
        assert b.foot_side(foot, col) == side


# ---------------------------------------------------------------------------
# Shootout state
# ---------------------------------------------------------------------------

class TestShootoutState:
    def test_decided_in_regulation(self, b):
        assert b.shootout_decided(3, 3, 0, 3) == "a"     # B can reach at most 2
        assert b.shootout_decided(3, 4, 2, 4) is None
        assert b.shootout_decided(4, 5, 3, 5) == "a"

    def test_sudden_death(self, b):
        assert b.shootout_decided(6, 6, 5, 6) == "a"
        assert b.shootout_decided(6, 6, 5, 5) is None    # B still to kick

    def test_pressure_euro2020_final(self, b):
        # Italy 3-2 England after four kicks each.
        assert b.shootout_pressure(3, 4, 2, 4) == "can_win"     # Jorginho
        assert b.shootout_pressure(2, 4, 3, 5) == "must_score"  # Saka
        assert b.shootout_pressure(0, 0, 0, 0) == "neutral"

    def test_sudden_death_first_kicker_is_neutral(self, b):
        assert b.shootout_pressure(5, 5, 5, 5) == "neutral"
        assert b.shootout_pressure(5, 5, 6, 6) == "must_score"
        assert b.shootout_pressure(5, 5, 5, 6) == "can_win"


# ---------------------------------------------------------------------------
# Builder: pre-kick context comes from earlier events only
# ---------------------------------------------------------------------------

def _shot(i, team, period, minute, ptype, outcome, foot="Right Foot", end=(120, 37.0, 0.5)):
    return {"id": f"e{i}", "index": i, "period": period, "minute": minute,
            "type": {"name": "Shot"}, "team": {"name": team}, "player": {"id": i, "name": f"P{i}"},
            "shot": {"type": {"name": ptype}, "outcome": {"name": outcome},
                     "body_part": {"name": foot}, "end_location": list(end)}}


class TestKicksFromMatch:
    def test_score_state_and_shootout_order(self, b):
        events = [
            _shot(1, "A", 1, 10, "Open Play", "Goal"),
            {"id": "e2", "index": 2, "period": 1, "minute": 20, "type": {"name": "Own Goal For"},
             "team": {"name": "B"}},
            _shot(3, "B", 2, 70, "Penalty", "Saved"),               # in-game, level 1-1
            _shot(4, "A", 5, 120, "Penalty", "Goal"),               # shootout kick 1
            _shot(5, "B", 5, 120, "Penalty", "Off T", end=(120, 33.0, 0.4)),
            _shot(6, "A", 5, 120, "Penalty", "Goal", foot="Left Foot", end=(120, 43.0, 2.0)),
        ]
        ctx = {"competition_id": "x", "season_id": "2024", "competition_gender": "male",
               "tournament_start_date": "2024-06-01", "match_id": "m", "match_date": "2024-06-02"}
        rows = b.kicks_from_match(events, ctx, {"A": "AAA", "B": "BBB"})
        assert len(rows) == 4
        ig = rows[0]
        assert ig["phase"] == "in_game"
        assert (ig["team_score_before"], ig["opp_score_before"]) == (1, 1)
        assert ig["game_state"] == "level"
        assert ig["outcome"] == "saved"

        so = rows[1:]
        assert [r["shootout_kick_number"] for r in so] == [1, 2, 3]
        assert [r["team_kick_number"] for r in so] == [1, 1, 2]
        assert so[0]["team_kicked_first"] is True and so[1]["team_kicked_first"] is False
        # Third kick: A leads 1-0, both state values come from before the kick.
        assert (so[2]["team_score_before"], so[2]["opp_score_before"]) == (1, 0)
        assert so[1]["placement_zone"] == "low_left" and so[1]["on_target"] is False
        assert so[2]["placement_zone"] == "high_right" and so[2]["foot_side"] == "natural"

    def test_schema_has_source_column(self, b):
        assert "source" in b.SCHEMA_COLS
        assert b.SOURCE == "statsbomb_open"


# ---------------------------------------------------------------------------
# Baselines and evaluation
# ---------------------------------------------------------------------------

def _synth_kicks(seed: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    tours = [("t1", "2018-06-01"), ("t2", "2020-06-01"), ("t3", "2022-06-01"), ("t4", "2024-06-01")]
    frames = []
    for t, start in tours:
        n = 80
        phase = rng.choice(["in_game", "shootout"], n)
        tkn = np.where(phase == "shootout", rng.randint(1, 8, n), np.nan)
        frames.append(pd.DataFrame({
            "tournament": t, "tournament_start_date": start, "competition_gender": "male",
            "match_id": [f"{t}_m{i % 10}" for i in range(n)],
            "phase": phase, "taker_foot": rng.choice(["left", "right"], n),
            "team_kick_number": tkn,
            "shootout_kick_number": np.where(phase == "shootout", np.arange(n), np.nan),
            "team_id": rng.choice(["AAA", "BBB"], n),
            "shootout_pressure": np.where(phase == "shootout",
                                          rng.choice(["neutral", "must_score", "can_win"], n), None),
            "game_state": rng.choice(["level", "leading", "trailing"], n),
            "placement_zone": rng.choice(ZONES, n),
            "placement_col": rng.choice(["left", "center", "right"], n),
            "foot_side": rng.choice(["natural", "across", "center"], n),
            "outcome": rng.choice(["goal", "saved", "post", "off_target"], n, p=[.7, .2, .05, .05]),
            "on_target": True,
        }))
    df = pd.concat(frames, ignore_index=True)
    df["is_goal"] = df["outcome"] == "goal"
    return add_prekick_features(df)


class TestBaselines:
    def test_prekick_features_exclude_post_kick(self):
        assert not set(PREKICK_FEATURES) & POSTKICK_COLUMNS
        assert "placement_zone" in POSTKICK_COLUMNS

    def test_order_bucket(self):
        assert order_bucket(np.nan) == "in_game"
        assert order_bucket(3) == "3"
        assert order_bucket(7) == "6+"

    def test_group_rate_shrinks_toward_overall(self):
        df = pd.DataFrame({"g": ["a"] * 2 + ["b"] * 98, "label": [1, 1] + [0] * 49 + [1] * 49})
        m = GroupRate(["g"], "x", k=20).fit(df)
        p_a = m.predict(pd.DataFrame({"g": ["a"]}))[0]
        assert m.p0_ < p_a < 1.0                    # pulled well below the raw 100%
        assert m.predict(pd.DataFrame({"g": ["zzz"]}))[0] == pytest.approx(m.p0_)

    @pytest.mark.parametrize("pred", make_predictors(), ids=lambda p: p.name)
    def test_predictors_output_probabilities(self, pred):
        df = _synth_kicks()
        p = pred.fit(df).predict(df)
        assert p.shape == (len(df),)
        assert ((p > 0) & (p < 1)).all()

    def test_rolling_origin_uses_only_earlier_tournaments(self):
        df = _synth_kicks()
        scored = rolling_origin_predictions(df, min_train=100)
        # t1 has only 80 kicks of history (none), t2 has 80 -> both skipped.
        assert set(scored["tournament"]) == {"t3", "t4"}
        assert scored.loc[scored["tournament"] == "t3", "n_train"].iloc[0] == 160
        assert scored.loc[scored["tournament"] == "t4", "n_train"].iloc[0] == 240
        assert {"p_constant", "p_gbm_prekick"} <= set(scored.columns)

    def test_constant_rate_is_training_mean(self):
        df = _synth_kicks()
        m = ConstantRate().fit(df)
        assert m.rate_ == pytest.approx(df["label"].mean())


class TestAggregates:
    def test_zone_grid_counts(self):
        df = _synth_kicks()
        grid = zone_grid(df)
        assert grid["perspective"] == "taker"
        cells = [c for row in grid["cells"] for c in row]
        assert len(cells) == 9
        assert sum(c["n"] for c in cells) == len(df)
        assert sum(c["share"] for c in cells) == pytest.approx(1.0, abs=1e-3)

    def test_conversion_table_intervals(self):
        df = _synth_kicks()
        for row in conversion_table(df, ["phase"]):
            assert row["ci95"][0] <= row["conversion"] <= row["ci95"][1]

    def test_aggregates_omit_keeper_action(self):
        agg = aggregates_for(_synth_kicks())
        assert "keeper_technique" not in agg
        assert {"zones", "foot_x_side", "shootout_order", "shootout_pressure"} <= set(agg)
