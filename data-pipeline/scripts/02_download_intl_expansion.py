"""
02_download_intl_expansion.py — expand the international training corpus.

Fetches major international tournaments via soccerdata/FBref and writes
contract CSVs, growing the corpus beyond the two World Cups already on disk
(WC 2018 / WC 2022). Targets ~800-1200 normalized rows for retraining.

All normalization (score parsing, FIFA-code mapping, dual-row layout,
stage/group inference, sample weights) is REUSED from
data-pipeline/soccer/importers/fbref_soccerdata_importer.py — this script
only adds the competition/season matrix, the skip-if-exists guard, a
group-stage filter for the Nations League, and resilient per-season logging.

Output (one CSV per tournament year, per DATA_CONTRACT.md):
    data-pipeline/data/raw/{competition_id}/{season_id}/match_logs_normalized.csv

Usage:
    python data-pipeline/scripts/02_download_intl_expansion.py [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "data-pipeline"))

from soccer.importers.fbref_soccerdata_importer import FBrefInternationalImporter

# Use a dedicated handler with propagate=False so soccerdata's rich root-log
# handler (installed at import time) doesn't reformat/truncate our messages.
logger = logging.getLogger("intl_expansion")
logger.setLevel(logging.INFO)
logger.propagate = False
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
logger.addHandler(_handler)


# ---------------------------------------------------------------------------
# Competition / season matrix
# ---------------------------------------------------------------------------
# competition_id -> soccerdata FBref params.
#   league  : soccerdata league id (built-in, or custom via league_dict.json
#             written by setup_soccerdata_env — Copa & Nations League)
#   seasons : tournament years; each is both the soccerdata season and the
#             season_id path segment
#   weight  : default sample_weight (1.0 majors, 0.5 Nations League)
#   group_stage_only : keep only competition_stage == "group" rows
COMPETITIONS: dict[str, dict] = {
    "fifa_world_cup": {
        "league": "INT-World Cup",
        "seasons": [2014, 2018, 2022],          # 2018/2022 already on disk -> skipped
        "weight": 1.0,
    },
    "uefa_euro": {
        "league": "INT-European Championship",
        "seasons": [2016, 2020, 2024],          # Euro 2020 played 2021; season_id "2020"
        "weight": 1.0,
    },
    "copa_america": {
        "league": "INT-Copa America",            # custom league (league_dict.json)
        "seasons": [2016, 2019, 2021, 2024],
        "weight": 1.0,
    },
    "uefa_nations_league": {
        "league": "INT-Nations League",          # custom; group/league phase only
        "seasons": [2022, 2024],
        "weight": 0.5,
        "group_stage_only": True,
    },
}

POLITE_SLEEP_SECONDS = 5.0
RAW_DIR = PROJECT_ROOT / "data-pipeline" / "data" / "raw"


def _normalize_schedule(importer, schedule: pd.DataFrame, comp_id: str,
                        season_id: str, weight: float, group_only: bool):
    """
    Turn an FBref schedule DataFrame into contract rows via the importer's
    per-match normalizer. Returns (rows, unmapped_team_names, skipped_count).
    """
    rows: list[dict] = []
    unmapped: set[str] = set()
    skipped = 0

    for _, match in schedule.iterrows():
        try:
            pair = importer._match_to_rows(
                match,
                competition_id=comp_id,
                season_id=season_id,
                default_weight=weight,
            )
            if group_only:
                pair = [r for r in pair if r["competition_stage"] == "group"]
            rows.extend(pair)
        except KeyError as e:
            unmapped.add(str(e).strip("'\""))
            skipped += 1
        except Exception as e:  # missing score, bad date, etc.
            skipped += 1
            logger.debug("  skip match %s vs %s: %s",
                         match.get("home_team"), match.get("away_team"), e)

    return rows, unmapped, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand intl training corpus via FBref")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be fetched without scraping or writing")
    args = parser.parse_args()

    # Instantiating the importer runs setup_soccerdata_env(): it writes
    # league_dict.json (registering Copa & Nations League) and sets
    # SOCCERDATA_DIR — both must happen before soccerdata is imported.
    importer = FBrefInternationalImporter(PROJECT_ROOT, headless=True)
    sd = None if args.dry_run else importer._import_soccerdata()

    summary = {"written": [], "skipped": [], "failed": []}

    for comp_id, cfg in COMPETITIONS.items():
        league = cfg["league"]
        weight = cfg["weight"]
        group_only = cfg.get("group_stage_only", False)

        for season in cfg["seasons"]:
            season_id = str(season)
            out_path = RAW_DIR / comp_id / season_id / "match_logs_normalized.csv"
            tag = f"{comp_id}/{season_id}"

            if out_path.exists():
                logger.info("SKIP  %s — already on disk", tag)
                summary["skipped"].append(tag)
                continue

            if args.dry_run:
                logger.info("DRY-RUN would fetch %s  (league=%r, weight=%.1f%s)",
                            tag, league, weight,
                            ", group-only" if group_only else "")
                continue

            try:
                logger.info("FETCH %s  (league=%r) ...", tag, league)
                fb = sd.FBref(leagues=league, seasons=[season], headless=True)
                schedule = fb.read_schedule().reset_index()

                rows, unmapped, skipped = _normalize_schedule(
                    importer, schedule, comp_id, season_id, weight, group_only
                )

                if not rows:
                    reason = f"0 rows (unmapped={sorted(unmapped)})" if unmapped else "0 rows"
                    logger.warning("FAIL  %s — %s", tag, reason)
                    summary["failed"].append(f"{tag} [{reason}]")
                    continue

                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_df = pd.DataFrame(rows).sort_values(["match_date", "match_id", "team_id"])
                out_df.to_csv(out_path, index=False, encoding="utf-8")

                note = f" (skipped {skipped} matches, unmapped={sorted(unmapped)})" if unmapped else ""
                logger.info("OK    %s — wrote %d rows%s", tag, len(out_df), note)
                summary["written"].append(f"{tag} ({len(out_df)} rows)")

            except Exception as e:
                logger.error("FAIL  %s — %s: %s", tag, type(e).__name__, str(e)[:300])
                summary["failed"].append(f"{tag} [{type(e).__name__}]")
            finally:
                if not args.dry_run:
                    time.sleep(POLITE_SLEEP_SECONDS)

    logger.info("=" * 64)
    logger.info("INGEST SUMMARY")
    logger.info("  written (%d): %s", len(summary["written"]), summary["written"] or "none")
    logger.info("  skipped (%d): %s", len(summary["skipped"]), summary["skipped"] or "none")
    logger.info("  failed  (%d): %s", len(summary["failed"]), summary["failed"] or "none")
    logger.info("=" * 64)


if __name__ == "__main__":
    main()
