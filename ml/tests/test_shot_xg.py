"""Shot xG models, leakage guard, tournament-date split, freeze-frame geometry, evaluation helpers, and grid export on synthetic shots."""

import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.models.shot_xg import (
    ASSIST_CATEGORIES, BODY_PART_CATEGORIES, FEATURE_SETS, FORBIDDEN_FEATURES,
    LOGISTIC_FEATURES, MODEL_FACTORIES, SITUATION_CATEGORIES, TECHNIQUE_CATEGORIES,
    add_derived_features, p_goal,
)
from ml.pipeline.evaluate_shots import (
    calibration_buckets, paired_bootstrap_diff, per_match_totals, wilson_interval,
)
from ml.pipeline.export_xg_grid import on_pitch, pitch_to_polar
from ml.pipeline.train_shots import selection_split, split_shots

ROOT = Path(__file__).resolve().parents[2]
EXPORTER = ROOT / "data-pipeline" / "scripts" / "shots" / "01_export_statsbomb_shots.py"

TOURNAMENTS = [
    # (tournament, start date, gender)
    ("fifa_world_cup_2018", "2018-06-14", "male"),
    ("uefa_euro_2020", "2021-06-11", "male"),
    ("womens_world_cup_2023", "2023-07-20", "female"),
    ("afcon_2023", "2024-01-13", "male"),
    ("uefa_euro_2024", "2024-06-14", "male"),
    ("copa_america_2024", "2024-06-20", "male"),
]


def _load_exporter():
    spec = importlib.util.spec_from_file_location("shots_exporter", EXPORTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _synth_shots(n_per: int = 80, seed: int = 0) -> pd.DataFrame:
    rng = np.random.RandomState(seed)
    frames = []
    for i, (tour, start, gender) in enumerate(TOURNAMENTS):
        n = n_per
        distance = rng.uniform(2, 35, n)
        angle = rng.uniform(0, 85, n)
        p = 1.0 / (1.0 + np.exp(0.18 * distance + 0.03 * angle - 2.0))
        ff = rng.uniform(0, 1, n) > 0.1
        start_ts = pd.Timestamp(start)
        frames.append(pd.DataFrame({
            "shot_id": [f"{tour}_{k}" for k in range(n)],
            # 8 matches per tournament, all on or after its start date
            "match_id": [f"{tour}_m{k % 8}" for k in range(n)],
            "match_date": [(start_ts + pd.Timedelta(days=k % 8)).date().isoformat() for k in range(n)],
            "tournament": tour,
            "tournament_start_date": start,
            "competition_gender": gender,
            "team_id": rng.choice(["AAA", "BBB"], n),
            "distance_m": distance,
            "angle_deg": angle,
            "body_part": rng.choice(BODY_PART_CATEGORIES, n),
            "situation": rng.choice(SITUATION_CATEGORIES, n),
            "technique": rng.choice(TECHNIQUE_CATEGORIES, n),
            "assist_type": rng.choice(ASSIST_CATEGORIES, n),
            "under_pressure": rng.randint(0, 2, n).astype(bool),
            "first_time": rng.randint(0, 2, n).astype(bool),
            "ff_available": ff,
            "n_def_in_cone": np.where(ff, rng.randint(0, 4, n), np.nan),
            "nearest_def_m": np.where(ff, rng.uniform(0.3, 8, n), np.nan),
            "gk_dist_to_goal_m": np.where(ff, rng.uniform(0, 6, n), np.nan),
            "gk_dist_to_shooter_m": np.where(ff, rng.uniform(1, 30, n), np.nan),
            "gk_angle_offset_deg": np.where(ff, rng.uniform(0, 30, n), np.nan),
            "sb_xg_benchmark": p,
            "label": (rng.uniform(0, 1, n) < p).astype(int),
        }))
    return add_derived_features(pd.concat(frames, ignore_index=True))


@pytest.fixture(scope="module")
def synth():
    return _synth_shots()



class TestModels:
    @pytest.mark.parametrize("name", list(MODEL_FACTORIES))
    def test_fits_and_predicts_probabilities(self, synth, name):
        feats = FEATURE_SETS[name]
        model = MODEL_FACTORIES[name]().fit(synth[feats], synth["label"])
        proba = model.predict_proba(synth[feats])
        assert proba.shape == (len(synth), 2)
        assert (proba >= 0).all() and (proba <= 1).all()
        assert np.allclose(proba.sum(axis=1), 1.0)

    @pytest.mark.parametrize("name", ["logistic_full", "gbm_full"])
    def test_handles_missing_freeze_frame(self, synth, name):
        feats = FEATURE_SETS[name]
        model = MODEL_FACTORIES[name]().fit(synth[feats], synth["label"])
        row = synth[feats].iloc[[0]].copy()
        for col in ("n_def_in_cone", "nearest_def_m", "gk_dist_to_goal_m",
                    "gk_dist_to_shooter_m", "gk_angle_offset_deg"):
            row[col] = np.nan
        row["ff_available"] = 0
        p = p_goal(model, row)
        assert 0 < p[0] < 1

    def test_unknown_category_does_not_crash(self, synth):
        feats = FEATURE_SETS["logistic_full"]
        model = MODEL_FACTORIES["logistic_full"]().fit(synth[feats], synth["label"])
        row = synth[feats].iloc[[0]].copy()
        row["technique"] = "scorpion_kick"
        assert 0 < p_goal(model, row)[0] < 1

    def test_logistic_baseline_is_distance_angle(self):
        # data-pipeline/scripts/06_backfill_xg.py loads logistic_xg with these inputs.
        assert LOGISTIC_FEATURES == ["distance_m", "angle_deg"]
        assert FEATURE_SETS["logistic_xg"] == LOGISTIC_FEATURES

    def test_grid_model_uses_only_lab_inputs(self):
        assert set(FEATURE_SETS["grid_xg"]) == {"distance_m", "angle_deg", "log_distance",
                                                "body_part", "situation"}



class TestNoForbiddenColumns:
    @pytest.mark.parametrize("name", list(FEATURE_SETS))
    def test_feature_sets_exclude_forbidden(self, name):
        assert not set(FEATURE_SETS[name]) & FORBIDDEN_FEATURES

    def test_forbidden_list_covers_post_shot_columns(self):
        for col in ("is_goal", "sb_xg_benchmark", "statsbomb_xg", "end_location",
                    "keeper_dive_direction", "rebound_outcome", "hit_post", "var_outcome"):
            assert col in FORBIDDEN_FEATURES

    def test_exporter_schema_has_no_post_shot_feature(self):
        exporter = _load_exporter()
        all_features = set().union(*FEATURE_SETS.values())
        # Every model input must be a contract column or a documented derived column.
        derived = {"log_distance", "is_womens"}
        assert all_features - derived <= set(exporter.SCHEMA_COLS)
        assert "end_location" not in exporter.SCHEMA_COLS



class TestTournamentDateSplit:
    def test_eval_tournaments_start_after_train(self, synth):
        train, eval_ = split_shots(synth, eval_start="2024-06-01")
        assert len(train) and len(eval_)
        assert train["tournament_start_date"].max() < eval_["tournament_start_date"].min()
        assert set(eval_["tournament"]) == {"uefa_euro_2024", "copa_america_2024"}

    def test_no_tournament_on_both_sides(self, synth):
        train, eval_ = split_shots(synth, eval_start="2024-06-01")
        assert not set(train["tournament"]) & set(eval_["tournament"])

    def test_split_uses_tournament_start_not_match_date(self, synth):
        # Cutoff falls inside Euro 2024 by match date; the whole tournament must stay in eval.
        train, eval_ = split_shots(synth, eval_start="2024-06-16")
        euro = synth[synth["tournament"] == "uefa_euro_2024"]
        assert euro["match_date"].min() < "2024-06-16" < euro["match_date"].max()
        # Euro 2024 started 2024-06-14, before the cutoff, so every one of its shots trains.
        assert (train["tournament"] == "uefa_euro_2024").sum() == len(euro)
        assert "uefa_euro_2024" not in set(eval_["tournament"])

    def test_selection_split_stays_inside_train(self, synth):
        train, eval_ = split_shots(synth, eval_start="2024-06-01")
        inner, val = selection_split(train, val_start="2023-07-01")
        assert set(val["tournament"]) == {"womens_world_cup_2023", "afcon_2023"}
        assert not set(val["shot_id"]) & set(eval_["shot_id"])
        assert inner["tournament_start_date"].max() < val["tournament_start_date"].min()



class TestFreezeFrameGeometry:
    @pytest.fixture(scope="class")
    def exp(self):
        return _load_exporter()

    def test_distance_angle_central(self, exp):
        d, a = exp.distance_angle([108.0, 40.0])
        assert d == pytest.approx(12 * 0.9144, abs=0.01)
        assert a == 0.0

    def test_cone_membership(self, exp):
        shooter = (100.0, 40.0)
        assert exp.in_shooting_cone((110.0, 40.0), shooter)
        assert not exp.in_shooting_cone((110.0, 50.0), shooter)
        assert not exp.in_shooting_cone((95.0, 40.0), shooter)

    def test_freeze_frame_features(self, exp):
        frame = [
            {"location": [110.0, 40.0], "teammate": False, "position": {"name": "Center Back"}},
            {"location": [104.0, 46.0], "teammate": False, "position": {"name": "Right Back"}},
            {"location": [101.0, 40.0], "teammate": True, "position": {"name": "Center Forward"}},
            {"location": [118.0, 40.0], "teammate": False, "position": {"name": "Goalkeeper"}},
        ]
        f = exp.freeze_frame_features(frame, [100.0, 40.0])
        assert f["ff_available"] is True
        # Keeper and teammates are excluded
        assert f["n_def_in_cone"] == 1
        assert f["nearest_def_m"] == pytest.approx(math.hypot(4, 6) * 0.9144, abs=0.01)
        assert f["gk_dist_to_goal_m"] == pytest.approx(2 * 0.9144, abs=0.01)
        assert f["gk_angle_offset_deg"] == pytest.approx(0.0, abs=0.1)

    def test_missing_freeze_frame_is_nan(self, exp):
        f = exp.freeze_frame_features(None, [100.0, 40.0])
        assert f["ff_available"] is False
        assert math.isnan(f["n_def_in_cone"])



class TestEvaluationHelpers:
    def test_calibration_buckets_cover_every_shot(self, synth):
        p = synth["sb_xg_benchmark"].to_numpy()
        cal = calibration_buckets(synth["label"], p)
        assert sum(b["n"] for b in cal["bins"]) == len(synth)
        assert 0 <= cal["ece"] <= 1

    def test_wilson_interval_contains_rate(self):
        lo, hi = wilson_interval(10, 100)
        assert lo < 0.10 < hi

    def test_per_match_totals_sum(self, synth):
        res = per_match_totals(synth, synth["sb_xg_benchmark"].to_numpy())
        assert res["summary"]["total_goals"] == int(synth["label"].sum())
        assert res["summary"]["total_xg"] == pytest.approx(synth["sb_xg_benchmark"].sum(), abs=0.05)
        assert len(res["rows"]) == res["summary"]["n_team_matches"]

    def test_paired_bootstrap_sign(self, synth):
        good = synth["sb_xg_benchmark"].to_numpy()
        bad = np.full(len(synth), 0.5)
        res = paired_bootstrap_diff(synth, good, bad, n_boot=200)
        assert res["log_loss_diff"] < 0
        assert res["log_loss_diff_ci95"][1] < 0



class TestGrid:
    def test_on_pitch(self):
        assert on_pitch(10, 0)
        # About 43.6 yd wide of the goal center
        assert not on_pitch(40, 85)

    def test_pitch_to_polar_matches_exporter(self):
        exp = _load_exporter()
        for x, y in [(108, 40), (100, 30), (119, 5)]:
            d, a = pitch_to_polar(x, y)
            d2, a2 = exp.distance_angle([x, y])
            assert d == pytest.approx(d2, abs=0.01)
            assert a == pytest.approx(a2, abs=0.1)
