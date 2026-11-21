"""
Central config for the Neutral Ground ML pipeline.
Every script reads paths, seeds and splits from here so isolated runs match pipeline runs.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR     = PROJECT_ROOT / "data-pipeline" / "data" / "raw"
STATIC_DIR   = PROJECT_ROOT / "data-pipeline" / "data" / "static"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 42

# copa_america has no data yet (WC-01b); the loader skips the missing dir with a warning.
COMPETITIONS_TRAIN = ["fifa_world_cup", "uefa_euro", "copa_america"]

# Splits are purely chronological, never shuffled: everything before this trains.
TRAIN_CUTOFF_DATE = "2026-06-11"
# Eval is the WC 2026 group stage; this closes it before the Round of 32, whose fixtures have NA scores.
EVAL_CUTOFF_DATE  = "2026-07-02"

FRIENDLY_WEIGHT = 0.3

# Reference only: the sample_weight column is already baked into the normalized CSVs by ingest.
TOURNAMENT_WEIGHTS = {
    "fifa_world_cup": 1.0,
    "uefa_euro": 1.5,
    "copa_america": 1.5,
    "afcon": 1.2,
    "afc_asian_cup": 1.2,
    "concacaf_gold_cup": 1.0,
    "uefa_nations_league": 0.7,
    "qualifier": 0.5,
    "friendly": 0.3,
    "other_tournament": 0.6,
}

ROLLING_WINDOWS = [3, 5, 10]
# Rolling min_periods of 1 keeps early-tournament rows instead of dropping them.
MIN_MATCHES_REQUIRED = 1

ELO_INITIAL  = 1500.0
ELO_K_FACTOR = 20.0

# Higher stakes move ratings more; unmapped competitions fall back to ELO_K_FACTOR.
K_FACTORS = {
    "fifa_world_cup":      60,
    "uefa_euro":           50,
    "copa_america":        50,
    "afcon":               45,
    "afc_asian_cup":       45,
    "concacaf_gold_cup":   40,
    "uefa_nations_league": 35,
    "qualifier":           30,
    "friendly":            15,
    "other_tournament":    25,
}

# Tuned on the WC 2026 holdout itself; walk-forward it only gains ~0.0006 log loss, so ensemble runs skip it.
DRAW_CALIBRATION_THRESHOLD = 0.75
DRAW_CALIBRATION_ALPHA = 0.60

TARGET_COL     = "match_outcome"
# Column order of every probability output.
TARGET_CLASSES = ["H", "D", "A"]
TARGET_ENCODE  = {"H": 2, "D": 1, "A": 0}

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Shots split by their tournament's first match date so no tournament straddles train and eval.
# Validation tournaments only pick the production model, then fold back into train.
SHOT_VALIDATION_START_DATE = "2023-07-01"
SHOT_EVAL_START_DATE = "2024-06-01"
# The site covers men's internationals; women's shots only add training volume.
SHOT_HEADLINE_GENDER = "male"
# Committed, unlike ml/artifacts/ which is gitignored.
EXPORTS_DIR = PROJECT_ROOT / "ml" / "exports"

PENALTY_CSV = STATIC_DIR / "penalties" / "penalty_kicks_v0.csv"
PENALTY_EVAL_START_DATE = "2024-06-01"
