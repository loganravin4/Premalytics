"""International pipeline importers.

football_data_importer and xg_importer are legacy EPL code kept for archive review, so they aren't exported.
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
