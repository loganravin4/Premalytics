"""
Central configuration for the Premalytics ML pipeline (World Cup pivot).

All paths, seeds, and split definitions live here so every script
behaves identically when run in isolation or as part of a pipeline.

Split strategy
--------------
Splits are competition- and date-based, never EPL season strings. The corpus
now spans the FBref WC/Euro CSVs plus the martj42 international_results
supplement (10k+ post-1990 matches across friendlies, qualifiers, and every
major tournament). The split is purely chronological at TRAIN_CUTOFF_DATE
(no shuffling):

  Training: all international matches before June 11, 2026.
  Eval:     WC 2026 group stage (June 11-27, 2026) — the real, completed
            48-team group phase (72 matches / 144 dual rows), used as a clean
            single-tournament holdout. EVAL_CUTOFF_DATE (July 2, 2026) closes
            the window before the Round of 32 (whose fixtures have NA scores
            and are dropped during normalization).
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR     = PROJECT_ROOT / "data-pipeline" / "data" / "raw"
STATIC_DIR   = PROJECT_ROOT / "data-pipeline" / "data" / "static"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 42

# ---------------------------------------------------------------------------
# Splits (competition- and date-based — never season strings, never shuffled)
# ---------------------------------------------------------------------------
# Competitions included in the training corpus. fifa_world_cup (2014/2018/
# 2022) and uefa_euro (2016/2020/2024) are on disk. copa_america is wired
# for when its custom-league FBref ingest is fixed (WC-01b); until then the
# loader skips the missing dir with a warning. uefa_nations_league is omitted
# until that data actually lands.
COMPETITIONS_TRAIN = ["fifa_world_cup", "uefa_euro", "copa_america"]

# Chronological boundary between the training and eval windows.
# Everything before June 11, 2026 trains; the WC 2026 group stage is the holdout.
TRAIN_CUTOFF_DATE = "2026-06-11"   # WC 2026 group stage start
EVAL_CUTOFF_DATE  = "2026-07-02"   # WC 2026 group stage end (last match Jun 27 + buffer)

# Down-weight friendlies when they enter the corpus (sample_weight multiplier).
FRIENDLY_WEIGHT = 0.3

# Intended per-competition training weights. NOTE: the sample_weight COLUMN in
# the normalized CSVs is already baked in by the ingest scripts (these are the
# values train.py actually feeds to fit() via home_sample_weight). This dict
# documents the intended scheme and is the reference for any future re-normalize
# or for overriding weights at fit time. Euro/Copa are boosted above 1.0 to
# strengthen their signal relative to the WC; minor comps are down-weighted.
TOURNAMENT_WEIGHTS = {
    "fifa_world_cup": 1.0,
    "uefa_euro": 1.5,       # up from 1.0 — boost Euro signal
    "copa_america": 1.5,    # up from 1.0
    "afcon": 1.2,
    "afc_asian_cup": 1.2,
    "concacaf_gold_cup": 1.0,
    "uefa_nations_league": 0.7,
    "qualifier": 0.5,
    "friendly": 0.3,
    "other_tournament": 0.6,
}

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------
ROLLING_WINDOWS = [3, 5, 10]      # Match rolling window sizes
MIN_MATCHES_REQUIRED = 1           # min_periods for rolling (allows early-tournament rows)

# ELO rating system
ELO_INITIAL  = 1500.0   # Starting ELO for every team before their first recorded match
ELO_K_FACTOR = 20.0     # Default/fallback update magnitude (unmapped competitions)

# Tournament-specific ELO K factors: a World Cup win should move ratings more
# than a friendly. compute_elo_features() looks up the row's competition_id
# here, falling back to ELO_K_FACTOR when absent. Higher K = faster rating
# response for higher-stakes competitions.
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

# ---------------------------------------------------------------------------
# Draw probability calibration (post-processing, applied in predict.py)
# ---------------------------------------------------------------------------
# The gradient boosting model systematically underweights draw probability
# when one team is a heavy favorite (a known ELO-based-model issue). When the
# favorite's raw probability exceeds DRAW_CALIBRATION_THRESHOLD, that much of
# its mass past the threshold is shifted to the draw, scaled by
# DRAW_CALIBRATION_ALPHA. These values were chosen by grid search over the
# WC 2026 holdout itself. Re-tuned walk-forward (tune_draw_calibration.py,
# ML-04) the rule gains ~0.0006 log loss, so it only applies to plain-GBM runs;
# runs with an ensemble.json (GBM + Dixon-Coles) skip it. See
# docs/ML_EXPERIMENTS.md.
DRAW_CALIBRATION_THRESHOLD = 0.75
DRAW_CALIBRATION_ALPHA = 0.60

# ---------------------------------------------------------------------------
# Model target
# ---------------------------------------------------------------------------
TARGET_COL     = "match_outcome"   # H / D / A  (Home win, Draw, Away win)
TARGET_CLASSES = ["H", "D", "A"]  # Label order used for probability outputs
TARGET_ENCODE  = {"H": 2, "D": 1, "A": 0}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# ---------------------------------------------------------------------------
# Shot xG (Track 2) — tournament-date splits, never shuffled
# ---------------------------------------------------------------------------
# A shot's split is decided by its tournament's first match date, so no
# tournament is ever split across train and eval.
#   train:      tournaments starting before SHOT_EVAL_START_DATE
#   validation: the train tournaments starting on/after SHOT_VALIDATION_START_DATE
#               (AFCON 2023, Women's World Cup 2023); used only to pick the
#               production model, then folded back into train
#   eval:       tournaments starting on/after SHOT_EVAL_START_DATE
#               (Euro 2024, Copa América 2024, Women's Euro 2025)
SHOT_VALIDATION_START_DATE = "2023-07-01"
SHOT_EVAL_START_DATE = "2024-06-01"
# Headline metrics are reported on this gender's eval shots (the site covers
# men's internationals); women's tournaments add training volume via is_womens.
SHOT_HEADLINE_GENDER = "male"
# Committed location for frontend-facing JSON (ml/artifacts/ is gitignored).
EXPORTS_DIR = PROJECT_ROOT / "ml" / "exports"

# ---------------------------------------------------------------------------
# Penalties (Track 3)
# ---------------------------------------------------------------------------
PENALTY_CSV = STATIC_DIR / "penalties" / "penalty_kicks_v0.csv"
# Kicks from tournaments starting on/after this date are the penalty eval set.
PENALTY_EVAL_START_DATE = "2024-06-01"
