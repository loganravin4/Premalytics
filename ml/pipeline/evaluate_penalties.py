"""Penalty audit, rolling-origin evaluation of pre-kick predictors, and frontend aggregates.

Usage: python -m ml.pipeline.evaluate_penalties
"""

import json
import logging
from datetime import date, datetime

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ml.config import ARTIFACTS_DIR, EXPORTS_DIR, LOG_FORMAT, PENALTY_CSV, PENALTY_EVAL_START_DATE
from ml.models.penalty_baselines import (
    MIN_DISPLAY_N, PREKICK_FEATURES, add_prekick_features, conversion_table, make_predictors,
    shootout_summary, wilson_interval, zone_grid,
)
from ml.pipeline.evaluate_shots import paired_bootstrap_diff

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MIN_TRAIN_KICKS = 120
EPS = 1e-6


def load_penalties() -> pd.DataFrame:
    if not PENALTY_CSV.exists():
        raise FileNotFoundError(
            f"{PENALTY_CSV} missing. Build it with "
            f"python data-pipeline/scripts/penalties/01_build_penalty_csv.py")
    df = pd.read_csv(PENALTY_CSV)
    df["season_id"] = df["season_id"].astype(str)
    df["tournament"] = df["competition_id"] + "_" + df["season_id"]
    return add_prekick_features(df)


def scores(y, p) -> dict:
    p = np.clip(p, EPS, 1 - EPS)
    return {"n": int(len(y)), "brier_score": round(float(brier_score_loss(y, p)), 5),
            "log_loss": round(float(log_loss(y, p, labels=[0, 1])), 5)}


def audit(df: pd.DataFrame) -> dict:
    by_t = (df.groupby(["tournament", "tournament_start_date", "competition_gender", "phase"])
              .size().unstack("phase", fill_value=0).reset_index()
              .sort_values("tournament_start_date"))
    tournaments = []
    for r in by_t.itertuples(index=False):
        d = r._asdict()
        ig, so = int(d.get("in_game", 0)), int(d.get("shootout", 0))
        tournaments.append({"tournament": d["tournament"], "start_date": d["tournament_start_date"],
                            "gender": d["competition_gender"], "in_game": ig, "shootout": so,
                            "total": ig + so})
    coverage = {
        "end_location_y": float(df["end_y"].notna().mean()),
        "end_location_z": float(df["end_z"].notna().mean()),
        "placement_zone": float(df["placement_zone"].notna().mean()),
        "taker_foot_left_or_right": float(df["taker_foot"].isin(["left", "right"]).mean()),
        "keeper_id": float(df["keeper_id"].notna().mean()),
        "keeper_action_recorded": float((df["keeper_technique"] != "none_recorded").mean()),
        "keeper_dive_direction": 0.0,
    }
    return {
        "n_kicks": int(len(df)),
        "by_gender_phase": {f"{g}_{p}": int(n) for (g, p), n in
                            df.groupby(["competition_gender", "phase"]).size().items()},
        "outcomes": {k: int(v) for k, v in df["outcome"].value_counts().items()},
        "n_shootouts": int(df.loc[df["phase"] == "shootout", "match_id"].nunique()),
        "tournaments": tournaments,
        "field_coverage": {k: round(v, 4) for k, v in coverage.items()},
        "keeper_technique_counts": {k: int(v) for k, v in df["keeper_technique"].value_counts().items()},
    }


def rolling_origin_predictions(df: pd.DataFrame, min_train: int = MIN_TRAIN_KICKS) -> pd.DataFrame:
    starts = (df.groupby("tournament")["tournament_start_date"].first().sort_values())
    scored = []
    for tour, start in starts.items():
        # Train only on tournaments that started earlier, so no kick is scored by a model that saw it.
        train = df[df["tournament_start_date"] < start]
        test = df[df["tournament"] == tour]
        if len(train) < min_train or train["label"].nunique() < 2:
            continue
        out = test.copy()
        for pred in make_predictors():
            pred.fit(train)
            out[f"p_{pred.name}"] = pred.predict(test)
        out["n_train"] = len(train)
        scored.append(out)
    return pd.concat(scored, ignore_index=True)


def fixed_holdout(df: pd.DataFrame, eval_start: str = PENALTY_EVAL_START_DATE) -> dict:
    train = df[df["tournament_start_date"] < eval_start]
    test = df[df["tournament_start_date"] >= eval_start]
    res = {"eval_start_date": eval_start, "n_train": int(len(train)), "n_eval": int(len(test)),
           "eval_tournaments": sorted(test["tournament"].unique()), "models": {}}
    for pred in make_predictors():
        pred.fit(train)
        res["models"][pred.name] = scores(test["label"], pred.predict(test))
    return res


def evaluate_predictors(scored: pd.DataFrame) -> dict:
    names = [c[2:] for c in scored.columns if c.startswith("p_")]
    pooled = {n: scores(scored["label"], scored[f"p_{n}"].to_numpy()) for n in names}
    vs_constant = {}
    for n in names:
        if n == "constant":
            continue
        diff = paired_bootstrap_diff(scored, scored[f"p_{n}"].to_numpy(),
                                     scored["p_constant"].to_numpy())
        # Counts as beating the baseline only if the whole clustered-bootstrap 95% CI is below zero.
        diff["beats_constant"] = bool(diff["log_loss_diff_ci95"][1] < 0)
        vs_constant[n] = diff
    return {
        "n_scored": int(len(scored)),
        "tournaments_scored": sorted(scored["tournament"].unique()),
        "pooled": pooled,
        "vs_constant": vs_constant,
    }


def aggregates_for(df: pd.DataFrame) -> dict:
    n = len(df)
    k = int(df["is_goal"].sum())
    lo, hi = wilson_interval(k, n)
    so = df[df["phase"] == "shootout"]
    ig = df[df["phase"] == "in_game"]
    return {
        "n_kicks": n,
        "overall": {"n": n, "goals": k, "conversion": round(k / n, 4) if n else None,
                    "ci95": [round(lo, 4), round(hi, 4)]},
        "by_phase": conversion_table(df, ["phase"]),
        "zones": zone_grid(df),
        "on_target_rate": round(float(df["on_target"].mean()), 4) if n else None,
        "save_rate_on_target": round(float((df.loc[df["on_target"] == True, "outcome"] == "saved").mean()), 4)
        if n else None,
        "by_foot": conversion_table(df, ["taker_foot"]),
        "foot_x_side": conversion_table(df.dropna(subset=["foot_side"]), ["taker_foot", "foot_side"]),
        "foot_x_col": conversion_table(df.dropna(subset=["placement_col"]), ["taker_foot", "placement_col"]),
        "shootout_order": conversion_table(so, ["order_bucket"]),
        "shootout_pressure": conversion_table(so, ["shootout_pressure"]),
        "in_game_state": conversion_table(ig, ["game_state"]),
        # keeper_technique is omitted: StatsBomb's keeper action mostly restates the outcome.
        "shootouts": shootout_summary(df),
    }


def build_aggregates(df: pd.DataFrame, evaluation: dict, run_id: str) -> dict:
    mens = df[df["competition_gender"] == "male"]
    pooled = evaluation["pooled"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "run_id": run_id,
        "label": "Experimental. Descriptive conversion rates from past tournament kicks, not a prediction.",
        "source": "StatsBomb open data (international tournaments)",
        "perspective": "Zones are from the taker's view: 'left' is the taker's left.",
        "min_display_n": MIN_DISPLAY_N,
        "default_scope": "mens",
        "scopes": {"mens": aggregates_for(mens), "all": aggregates_for(df)},
        "model_check": {
            "question": "Do pre-kick facts (phase, foot, shootout order and pressure) predict conversion "
                        "better than the overall rate?",
            "constant_log_loss": pooled["constant"]["log_loss"],
            "best_other": min(((n, m["log_loss"]) for n, m in pooled.items() if n != "constant"),
                              key=lambda t: t[1]),
            "any_beats_constant": any(v["beats_constant"] for v in evaluation["vs_constant"].values()),
            "n_scored_kicks": evaluation["n_scored"],
        },
    }


def main() -> None:
    run_id = f"penalties_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = ARTIFACTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    df = load_penalties()
    aud = audit(df)
    logger.info("Kicks: %d (%s); shootouts: %d", aud["n_kicks"], aud["by_gender_phase"], aud["n_shootouts"])

    scored = rolling_origin_predictions(df)
    evaluation = evaluate_predictors(scored)
    for name, m in evaluation["pooled"].items():
        logger.info("rolling-origin %-17s brier=%.4f log_loss=%.4f", name, m["brier_score"], m["log_loss"])
    holdout = fixed_holdout(df)

    gbm_ships = evaluation["vs_constant"]["gbm_prekick"]["beats_constant"]
    metrics = {
        "run_id": run_id,
        "run_date": date.today().isoformat(),
        "audit": aud,
        "prekick_features": PREKICK_FEATURES,
        "rolling_origin": {"min_train_kicks": MIN_TRAIN_KICKS, **evaluation},
        "fixed_holdout": holdout,
        "gbm_decision": {
            "ships": gbm_ships,
            "rule": "ship only if pooled rolling-origin log loss beats constant with the 95% CI below zero",
        },
    }
    aggregates = build_aggregates(df, evaluation, run_id)

    (run_dir / "penalty_metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
    payload = json.dumps(aggregates, indent=2, default=str)
    (run_dir / "penalty_aggregates.json").write_text(payload)
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (EXPORTS_DIR / "penalty_aggregates.json").write_text(payload)
    (ARTIFACTS_DIR / "latest_penalty_run.txt").write_text(run_id)

    print(json.dumps({"audit": {k: aud[k] for k in ("n_kicks", "by_gender_phase", "n_shootouts",
                                                    "field_coverage")},
                      "rolling_origin": evaluation["pooled"],
                      "vs_constant": {k: {kk: v[kk] for kk in ("log_loss_diff", "log_loss_diff_ci95",
                                                               "beats_constant")}
                                      for k, v in evaluation["vs_constant"].items()},
                      "fixed_holdout": holdout,
                      "gbm_ships": gbm_ships}, indent=2))
    logger.info("Wrote %s and ml/exports/penalty_aggregates.json", run_dir)


if __name__ == "__main__":
    main()
