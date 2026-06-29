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
ELO_K_FACTOR = 20.0     # Update magnitude per match (standard football value)

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
