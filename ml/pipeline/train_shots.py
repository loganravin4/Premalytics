"""Train the shot xG models, pick the production model on a time-ordered validation fold, and save the run.

Usage: python -m ml.pipeline.train_shots
"""

import json
import logging
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ml.config import (
    ARTIFACTS_DIR, DATA_DIR, LOG_FORMAT, RANDOM_SEED,
    SHOT_EVAL_START_DATE, SHOT_VALIDATION_START_DATE,
)
from ml.models.shot_xg import (
    FEATURE_SETS, MODEL_FACTORIES, add_derived_features, p_goal,
)

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)
np.random.seed(RANDOM_SEED)

SHOT_DIR = DATA_DIR / "shots"
LABEL_COL = "is_goal"
SELECTION_CANDIDATES = ["logistic_full", "gbm_full"]
SELECTION_TIE_TOLERANCE = 0.001


def load_shots() -> pd.DataFrame:
    paths = sorted(SHOT_DIR.glob("*_shots_*.csv"))
    if not paths:
        raise FileNotFoundError(
            f"No shot data in {SHOT_DIR}. Regenerate with "
            f"python data-pipeline/scripts/shots/01_export_statsbomb_shots.py"
        )
    df = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    df["season_id"] = df["season_id"].astype(str)
    df["tournament"] = df["competition_id"] + "_" + df["season_id"]

    # "other" is outside the body_part enum; penalties are modeled separately.
    df = df[df["body_part"] != "other"]
    df = df[~df["is_penalty"].astype(bool)]

    df = add_derived_features(df)
    df["label"] = df[LABEL_COL].astype(int)
    return df.reset_index(drop=True)


def split_shots(df: pd.DataFrame, eval_start: str = SHOT_EVAL_START_DATE):
    # Split on tournament start, not match date, so each tournament stays whole on one side.
    start = df["tournament_start_date"].astype(str)
    return df[start < eval_start], df[start >= eval_start]


def selection_split(train: pd.DataFrame, val_start: str = SHOT_VALIDATION_START_DATE):
    return split_shots(train, eval_start=val_start)


def conversion_rate(df: pd.DataFrame) -> float:
    return float(df["label"].mean()) if len(df) else 0.0


def tournament_summary(df: pd.DataFrame) -> list[dict]:
    g = df.groupby(["tournament", "tournament_start_date", "competition_gender"])
    out = g.agg(n_shots=("label", "size"), goals=("label", "sum")).reset_index()
    out = out.sort_values("tournament_start_date")
    return [
        {"tournament": r.tournament, "start_date": r.tournament_start_date,
         "gender": r.competition_gender, "n_shots": int(r.n_shots), "goals": int(r.goals)}
        for r in out.itertuples()
    ]


def score(y, p) -> dict:
    return {"brier_score": float(brier_score_loss(y, p)),
            "log_loss": float(log_loss(y, p, labels=[0, 1])),
            "n": int(len(y))}


def select_production_model(train_df: pd.DataFrame) -> dict:
    # Selection uses an inner time-ordered fold, so the eval tournaments are never seen here.
    inner_train, val = selection_split(train_df)
    logger.info("Model selection: inner_train=%d shots, validation=%d shots (%s)",
                len(inner_train), len(val), sorted(val["tournament"].unique()))
    results = {}
    for name in SELECTION_CANDIDATES:
        feats = FEATURE_SETS[name]
        model = MODEL_FACTORIES[name]()
        model.fit(inner_train[feats], inner_train["label"])
        results[name] = score(val["label"], p_goal(model, val[feats]))
        logger.info("  validation %s: brier=%.4f log_loss=%.4f", name,
                    results[name]["brier_score"], results[name]["log_loss"])

    lg, gb = results["logistic_full"]["log_loss"], results["gbm_full"]["log_loss"]
    # Near-ties go to the logistic: simpler and monotone in distance.
    winner = "gbm_full" if gb < lg - SELECTION_TIE_TOLERANCE else "logistic_full"
    return {
        "production_model": winner,
        "rule": f"lower validation log loss; ties within {SELECTION_TIE_TOLERANCE} go to logistic_full",
        "validation_tournaments": sorted(val["tournament"].unique()),
        "n_inner_train": int(len(inner_train)),
        "n_validation": int(len(val)),
        "validation_metrics": results,
    }


def main() -> None:
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = ARTIFACTS_DIR / f"shot_xg_{run_ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    df = load_shots()
    train_df, eval_df = split_shots(df)
    logger.info("n_train=%d  n_eval=%d  train_conversion=%.3f  eval_conversion=%.3f",
                len(train_df), len(eval_df), conversion_rate(train_df), conversion_rate(eval_df))

    selection = select_production_model(train_df)
    logger.info("Production model: %s", selection["production_model"])

    for name, factory in MODEL_FACTORIES.items():
        feats = FEATURE_SETS[name]
        model = factory()
        model.fit(train_df[feats], train_df["label"])
        joblib.dump(model, run_dir / f"{name}.joblib")
        logger.info("Saved %s (%d features)", name, len(feats))

    split = {
        "rule": "tournament_start_date < SHOT_EVAL_START_DATE -> train, else eval",
        "eval_start_date": SHOT_EVAL_START_DATE,
        "validation_start_date": SHOT_VALIDATION_START_DATE,
        "train": tournament_summary(train_df),
        "eval": tournament_summary(eval_df),
        "n_train": int(len(train_df)),
        "n_eval": int(len(eval_df)),
    }
    (run_dir / "split.json").write_text(json.dumps(split, indent=2))
    (run_dir / "shot_feature_cols.json").write_text(json.dumps(FEATURE_SETS, indent=2))
    (run_dir / "production_model.json").write_text(json.dumps(selection, indent=2))
    (ARTIFACTS_DIR / "latest_shot_run.txt").write_text(run_dir.name)

    logger.info("Shot xG training complete. Artifacts in %s", run_dir)
    logger.info("Next: python -m ml.pipeline.evaluate_shots")


if __name__ == "__main__":
    main()
