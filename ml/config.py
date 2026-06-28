"""
Central configuration for the Premalytics ML pipeline (World Cup pivot).

All paths, seeds, and split definitions live here so every script
behaves identically when run in isolation or as part of a pipeline.

Split strategy
--------------
Splits are competition- and date-based, never EPL season strings. The corpus
on disk spans FIFA World Cup 2014/2018/2022 and UEFA Euro 2016/2020/2024
(copa_america is wired in COMPETITIONS_TRAIN but not yet ingested). The split
is purely chronological at TRAIN_CUTOFF_DATE (no shuffling): match_date <
cutoff trains (WC 2014, WC 2018, Euro 2016, Euro 2020); match_date >= cutoff
is eval (WC 2022, Euro 2024), with EVAL_CUTOFF_DATE marking the WC 2022 final.
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
# WC 2018 (Jun-Jul 2018) falls before the cutoff -> training.
# WC 2022 (Nov-Dec 2022) falls on/after the cutoff -> eval.
TRAIN_CUTOFF_DATE = "2022-11-01"   # everything before Nov 2022 is training (WC 2018)
EVAL_CUTOFF_DATE  = "2022-12-18"   # WC 2022 final — end of eval window

# Down-weight friendlies when they enter the corpus (sample_weight multiplier).
FRIENDLY_WEIGHT = 0.3

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
