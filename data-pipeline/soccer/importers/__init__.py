"""
=============================================================================
Package: soccer/importers
Description: Data entry points for the international (WC pivot) pipeline
=============================================================================

WHAT IS EXPORTED HERE:
  - FBrefInternationalImporter  →  primary ingest (soccerdata → FBref)
  - COMPETITIONS                →  registry of competition_id slugs + seasons
  - setup_soccerdata_env        →  configure .soccerdata cache before import

LEGACY (not exported):
  football_data_importer.py  — EPL match CSVs from football-data.co.uk
  xg_importer.py             — Understat xG merge for EPL rows

Those remain in the repo for archive/epl-2025 and ASSESS-01 review only.
Scripts 01/02 on main no longer import them.
=============================================================================
"""

from .fbref_soccerdata_importer import (
    COMPETITIONS,
    FBrefInternationalImporter,
    setup_soccerdata_env,
)

__all__ = [
    "COMPETITIONS",
    "FBrefInternationalImporter",
    "setup_soccerdata_env",
]
