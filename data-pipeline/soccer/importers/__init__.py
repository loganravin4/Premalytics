"""
=============================================================================
Package: soccer/importers
Description: Static dataset importers for Premalytics data pipeline

This package replaces the old FBRef/API scraping approach with a stable,
no-scraping strategy using free public datasets:

  1. football_data_importer.py  →  Match results from football-data.co.uk
  2. xg_importer.py             →  xG (expected goals) from Kaggle/Understat CSV

These importers are the ONLY data entry point into the pipeline.
No scraping, no anti-bot workarounds, no fragile HTML parsing.
=============================================================================
"""

# Make the two importer classes importable directly from the package
# e.g.: from soccer.importers import FootballDataImporter, XGImporter
from .football_data_importer import FootballDataImporter
from .xg_importer import XGImporter

# Define what is exported when someone does: from soccer.importers import *
__all__ = ["FootballDataImporter", "XGImporter"]
