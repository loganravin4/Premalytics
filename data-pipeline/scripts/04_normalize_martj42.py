"""
04_normalize_martj42.py — normalize martj42 results.csv to DATA_CONTRACT.md.

Reads the cached martj42 results.csv (see 03_download_martj42.py) and writes a
single normalized, dual-row match CSV that conforms to DATA_CONTRACT.md. This
file is a *supplement* to the FBref competition-split files and therefore lives
in its own flat source directory (not under {competition_id}/{season_id}/).

Normalization steps (see WC_SPEC.md / DATA_CONTRACT.md):
  1. Drop pre-1990 matches (modern-ELO relevance) and rows without a final score
     (future/cancelled fixtures).
  2. Map tournament -> (competition_id, sample_weight).
  3. Map team display names -> FIFA 3-letter codes via team_map_intl.csv;
     unmapped names are logged and their rows skipped.
  4. Emit two contract rows per match (home + away perspective).

Venue note (DECISION):
  The task brief asked for venue="Neutral" on neutral-site rows, but
  DATA_CONTRACT.md locks venue to {Home, Away} and validate_data_contract()
  (which Part 3 must pass, and which ml/tests/test_validation.py asserts) treats
  "Neutral" as an invalid venue. We therefore keep venue=Home/Away from the
  fixture's designated home/away teams and record neutrality in
  is_neutral_venue=True — identical to the FBref importer's convention.

Output:
    data-pipeline/data/raw/martj42/match_logs_normalized.csv

Usage:
    python data-pipeline/scripts/04_normalize_martj42.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent          # .../data-pipeline/scripts/
PIPELINE_DIR = SCRIPT_DIR.parent                      # .../data-pipeline/
PROJECT_ROOT = PIPELINE_DIR.parent                    # .../premalytics/

RAW_DIR = PIPELINE_DIR / "data" / "raw" / "martj42"
RESULTS_CSV = RAW_DIR / "results.csv"
OUT_CSV = RAW_DIR / "match_logs_normalized.csv"
TEAM_MAP_CSV = PIPELINE_DIR / "data" / "static" / "team_map_intl.csv"

MIN_DATE = "1990-01-01"

# tournament (exact upstream string) -> (competition_id, sample_weight).
# Both the WC_SPEC names and the dataset's actual strings are included where
# they differ (e.g. "African Cup of Nations" vs the spec's "Africa Cup of
# Nations"; "Gold Cup" vs "CONCACAF Gold Cup") so the intended competition_id
# is assigned regardless. See "Decisions worth your review".
COMPETITION_MAP: dict[str, tuple[str, float]] = {
    "FIFA World Cup": ("fifa_world_cup", 1.0),
    "UEFA Euro": ("uefa_euro", 1.0),
    "Copa América": ("copa_america", 1.0),
    "Africa Cup of Nations": ("afcon", 0.9),       # WC_SPEC spelling
    "African Cup of Nations": ("afcon", 0.9),      # martj42 dataset spelling
    "AFC Asian Cup": ("afc_asian_cup", 0.9),
    "UEFA Nations League": ("uefa_nations_league", 0.7),
    "CONCACAF Gold Cup": ("concacaf_gold_cup", 0.7),  # WC_SPEC spelling
    "Gold Cup": ("concacaf_gold_cup", 0.7),           # martj42 dataset spelling
    "Friendly": ("friendly", 0.3),
}

# Many martj42 team names carry diacritics (Gǎgǎuzia, Ryūkyū, São Tomé …).
# Force UTF-8 on stdout so the unmapped-name dump never hits the Windows cp1252
# console encoder.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover — non-reconfigurable stream
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def classify_tournament(tournament: str) -> tuple[str, float]:
    """Map a tournament name to (competition_id, sample_weight)."""
    if tournament in COMPETITION_MAP:
        return COMPETITION_MAP[tournament]
    low = tournament.lower()
    # Covers both "qualifier" and "qualification" wording.
    if "qualif" in low:
        return ("qualifier", 0.5)
    return ("other_tournament", 0.6)


def stage_for(competition_id: str) -> str:
    """Contract competition_stage from competition_id (no round info upstream)."""
    if competition_id == "friendly":
        return "friendly"
    if competition_id == "qualifier":
        return "qualifier"
    # All real tournaments: martj42 has no round detail, so default to "group".
    return "group"


def load_team_map(path: Path) -> dict[str, str]:
    """alias -> FIFA 3-letter code, from team_map_intl.csv."""
    df = pd.read_csv(path)
    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        alias = str(row["alias"]).strip()
        code = str(row["team_id"]).strip().upper()
        if alias and code:
            mapping[alias] = code
    return mapping


def normalize() -> None:
    if not RESULTS_CSV.exists():
        logger.error("Missing %s — run 03_download_martj42.py first", RESULTS_CSV)
        sys.exit(1)

    team_map = load_team_map(TEAM_MAP_CSV)
    logger.info("Loaded %d team aliases from %s", len(team_map), TEAM_MAP_CSV.name)

    df = pd.read_csv(RESULTS_CSV)
    n_input = len(df)
    logger.info("Read %d input rows from results.csv", n_input)

    # --- 1a. Post-1990 filter ---
    df["_date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["_date"] >= pd.Timestamp(MIN_DATE)]
    n_post_1990 = len(df)
    logger.info("After 1990 filter: %d rows (dropped %d pre-1990/undated)",
                n_post_1990, n_input - n_post_1990)

    # --- 1b. Drop rows without a final score (future/cancelled fixtures) ---
    df["home_score"] = pd.to_numeric(df["home_score"], errors="coerce")
    df["away_score"] = pd.to_numeric(df["away_score"], errors="coerce")
    df = df[df["home_score"].notna() & df["away_score"].notna()]
    n_scored = len(df)
    logger.info("After score filter: %d rows (dropped %d without final score)",
                n_scored, n_post_1990 - n_scored)

    rows: list[dict] = []
    unmapped: dict[str, int] = {}   # name -> count of skipped rows mentioning it
    skipped_unmapped = 0

    for _, m in df.iterrows():
        home_name = str(m["home_team"]).strip()
        away_name = str(m["away_team"]).strip()
        home_id = team_map.get(home_name)
        away_id = team_map.get(away_name)

        if home_id is None or away_id is None:
            if home_id is None:
                unmapped[home_name] = unmapped.get(home_name, 0) + 1
            if away_id is None:
                unmapped[away_name] = unmapped.get(away_name, 0) + 1
            skipped_unmapped += 1
            continue

        date_str = m["_date"].strftime("%Y-%m-%d")
        date_compact = date_str.replace("-", "")
        season_id = str(m["_date"].year)

        comp_id, weight = classify_tournament(str(m["tournament"]).strip())
        stage = stage_for(comp_id)
        neutral = bool(m["neutral"])

        home_goals = int(m["home_score"])
        away_goals = int(m["away_score"])
        match_id = f"{date_compact}_{home_id.lower()}_{away_id.lower()}"

        base = {
            "match_id": match_id,
            "competition_id": comp_id,
            "season_id": season_id,
            "competition_stage": stage,
            "match_date": date_str,
            "is_neutral_venue": neutral,
            "sample_weight": weight,
            "source": "martj42",
        }

        rows.append({
            **base,
            "team_id": home_id,
            "opponent_id": away_id,
            "venue": "Home",
            "goals_for": home_goals,
            "goals_against": away_goals,
            "result": "W" if home_goals > away_goals else ("D" if home_goals == away_goals else "L"),
        })
        rows.append({
            **base,
            "team_id": away_id,
            "opponent_id": home_id,
            "venue": "Away",
            "goals_for": away_goals,
            "goals_against": home_goals,
            "result": "W" if away_goals > home_goals else ("D" if away_goals == home_goals else "L"),
        })

    if not rows:
        logger.error("No rows normalized — aborting without writing output")
        sys.exit(1)

    out = pd.DataFrame(rows, columns=[
        "match_id", "competition_id", "season_id", "competition_stage",
        "match_date", "team_id", "opponent_id", "venue",
        "goals_for", "goals_against", "result",
        "is_neutral_venue", "sample_weight", "source",
    ])

    # Guard against the same fixture appearing twice in the source (same date,
    # same home/away). Keeps the dual-row invariant (one row per team per match).
    before = len(out)
    out = out.drop_duplicates(subset=["match_id", "team_id"])
    if len(out) < before:
        logger.info("Dropped %d duplicate (match_id, team_id) rows", before - len(out))

    out = out.sort_values(["match_date", "match_id", "team_id"]).reset_index(drop=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False, encoding="utf-8")

    # --- Logging summary ---
    logger.info("=" * 64)
    logger.info("NORMALIZE SUMMARY")
    logger.info("  input rows                 : %d", n_input)
    logger.info("  after 1990 filter          : %d", n_post_1990)
    logger.info("  after score filter         : %d", n_scored)
    logger.info("  matches skipped (unmapped) : %d", skipped_unmapped)
    logger.info("  output rows (dual)         : %d  (%d matches)", len(out), len(out) // 2)
    logger.info("  wrote %s", OUT_CSV)

    logger.info("-" * 64)
    logger.info("Competition breakdown (matches):")
    comp_counts = (out.drop_duplicates("match_id")["competition_id"]
                   .value_counts().sort_values(ascending=False))
    for comp_id, n in comp_counts.items():
        logger.info("  %-22s %5d", comp_id, n)

    logger.info("-" * 64)
    logger.info("UNMAPPED team names (%d distinct):", len(unmapped))
    if unmapped:
        for name in sorted(unmapped):
            logger.info("  UNMAPPED  %-40s (%d matches)", name, unmapped[name])
    else:
        logger.info("  (none)")
    logger.info("=" * 64)


if __name__ == "__main__":
    normalize()
