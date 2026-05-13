"""
Central configuration for the Premalytics ML pipeline.

All paths, seeds, and split definitions live here so every script
behaves identically when run in isolation or as part of a pipeline.
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
# Season definitions (chronological order — never shuffle)
# ---------------------------------------------------------------------------
SEASONS_ALL   = ["2021-2022", "2022-2023", "2023-2024", "2024-2025"]
SEASONS_TRAIN = ["2021-2022", "2022-2023"]
SEASONS_VALID = ["2023-2024"]
SEASONS_TEST  = ["2024-2025"]

# ---------------------------------------------------------------------------
# Feature engineering
# ---------------------------------------------------------------------------
ROLLING_WINDOWS = [3, 5, 10]      # Match rolling window sizes
MIN_MATCHES_REQUIRED = 1           # min_periods for rolling (allows early-season rows)

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
