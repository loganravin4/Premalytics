"""
Load and validate match data from normalized CSVs.

All ML features are derived from match_logs_normalized.csv files produced
by data-pipeline/scripts/02_normalize_and_export.py.

The loader also attempts to enrich xG values from FBRef raw CSVs when
the Understat/Kaggle xG source is unavailable (common for 2023-24+).
"""

import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from ml.config import DATA_DIR, SEASONS_ALL, ARTIFACTS_DIR

logger = logging.getLogger(__name__)

# Expected columns and their types after loading
REQUIRED_COLS = [
    "match_id", "season_id", "team_id", "opponent_id",
    "match_date", "venue", "goals_for", "goals_against", "result",
]

# International contract (WC pivot) — present on new CSVs, absent on legacy EPL files.
# validate_data_contract() auto-detects international data when competition_id exists.
INTL_COLS = [
    "competition_id",       # e.g. fifa_world_cup
    "competition_stage",    # group | knockout | final | qualifier | friendly
    "is_neutral_venue",     # bool — most WC/Euro matches are neutral-site
    "sample_weight",        # training weight (friendlies down-weighted in ingest)
    "source",               # provenance: fbref, football_data_api, etc.
]

NUMERIC_COLS = [
    "goals_for", "goals_against",
    "shots_for", "shots_against",
    "shots_on_target_for", "shots_on_target_against",
    "corners_for", "corners_against",
    "fouls_for", "fouls_against",
    "yellow_cards", "red_cards",
    "xg_for", "xg_against",
]

VALID_RESULTS  = {"W", "D", "L"}
VALID_VENUES   = {"Home", "Away"}


# ---------------------------------------------------------------------------
# FBRef xG supplement
# ---------------------------------------------------------------------------

def _load_fbref_xg(data_dir: Path, seasons: list[str]) -> dict:
    """
    Build a lookup {(match_date, team_canonical, opponent_canonical): (xg_for, xg_against)}
    from FBRef match log CSVs.

    FBRef CSVs live at: data/raw/{season}/{TeamName}/match_logs_{timestamp}.csv
    They have real xG values and use FBRef team IDs in opponent_id.
    We key by (date, team_folder_name, opponent_name_in_csv) which we then
    reconcile with canonical team names via the TEAM_NAME_MAP below.
    """
    # Map FBRef CSV opponent field → canonical name used in normalized CSVs
    FBREF_TO_CANONICAL = {
        "Nott'ham Forest": "Nott'ham Forest",
        "Newcastle Utd":   "Newcastle Utd",
        "Manchester City": "Manchester City",
        "Manchester Utd":  "Manchester Utd",
        "Sheffield Utd":   "Sheffield Utd",
        "Tottenham":       "Tottenham",
        "Wolves":          "Wolves",
        "Brighton":        "Brighton",
        "Leicester City":  "Leicester City",
        "Leeds United":    "Leeds United",
        "West Ham":        "West Ham",
        "Ipswich Town":    "Ipswich Town",
        "Luton Town":      "Luton Town",
    }

    # Map FBRef folder names (Title-Case with hyphens) → canonical names.
    # Add an entry here whenever a new team folder appears that lacks xG coverage.
    FOLDER_TO_CANONICAL = {
        "Arsenal": "Arsenal",
        "Aston-Villa": "Aston Villa",
        "Bournemouth": "Bournemouth",
        "Brentford": "Brentford",
        "Brighton": "Brighton",
        "Burnley": "Burnley",
        "Chelsea": "Chelsea",
        "Crystal-Palace": "Crystal Palace",
        "Everton": "Everton",
        "Fulham": "Fulham",
        "Ipswich-Town": "Ipswich Town",
        "Leeds-United": "Leeds United",
        "Leicester-City": "Leicester City",
        "Liverpool": "Liverpool",
        "Luton-Town": "Luton Town",
        "Manchester-City": "Manchester City",
        "Manchester-Utd": "Manchester Utd",
        "Newcastle-Utd": "Newcastle Utd",
        "Nott'ham-Forest": "Nott'ham Forest",
        "Norwich-City": "Norwich City",
        "Sheffield-Utd": "Sheffield Utd",
        "Southampton": "Southampton",
        "Sunderland": "Sunderland",
        "Tottenham": "Tottenham",
        "Watford": "Watford",
        "West-Brom": "West Brom",
        "West-Ham": "West Ham",
        "Wolves": "Wolves",
        "Middlesbrough": "Middlesbrough",
    }

    lookup = {}
    attempted_teams = 0
    teams_with_xg = 0
    null_only_skipped = 0

    for season in seasons:
        season_dir = data_dir / season
        if not season_dir.exists():
            continue
        for team_dir in season_dir.iterdir():
            if not team_dir.is_dir():
                continue
            canonical_team = FOLDER_TO_CANONICAL.get(team_dir.name)
            if canonical_team is None:
                # Slugified or unrecognised dir — skip.
                # Add the folder name to FOLDER_TO_CANONICAL above to enable it.
                continue

            # Exclude match_logs_normalized.csv: it has no xG and sorts last alphabetically,
            # causing fbref_files[-1] to silently pick the wrong file.
            fbref_files = sorted(
                f for f in team_dir.glob("match_logs_*.csv")
                if f.name != "match_logs_normalized.csv"
            )
            if not fbref_files:
                continue

            attempted_teams += 1

            # Among available FBRef CSVs, pick the one with the most non-null xg_for rows.
            # Older scrapes (2025-10-19) consistently have xG; newer ones (2026-03-16) may not.
            best_df = None
            for f in fbref_files:
                try:
                    tmp = pd.read_csv(f, low_memory=False)
                except Exception as e:
                    logger.debug(f"FBRef read failed for {f}: {e}")
                    continue
                if "xg_for" not in tmp.columns or "xg_against" not in tmp.columns:
                    continue
                if "date" not in tmp.columns and "match_date" not in tmp.columns:
                    continue
                if not tmp["xg_for"].notna().any():
                    null_only_skipped += 1
                    continue
                if best_df is None or tmp["xg_for"].notna().sum() > best_df["xg_for"].notna().sum():
                    best_df = tmp

            if best_df is None:
                continue

            df = best_df
            teams_with_xg += 1
            date_col = "date" if "date" in df.columns else "match_date"
            df["_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y-%m-%d")

            for _, row in df.iterrows():
                date = row.get("_date")
                opp  = str(row.get("opponent", "")).strip()
                canonical_opp = FBREF_TO_CANONICAL.get(opp, opp)
                xgf = row.get("xg_for")
                xga = row.get("xg_against")

                if not date or not canonical_opp:
                    continue
                if pd.isna(xgf) and pd.isna(xga):
                    continue

                key = (date, canonical_team, canonical_opp)
                lookup[key] = (
                    float(xgf) if pd.notna(xgf) else None,
                    float(xga) if pd.notna(xga) else None,
                )

    logger.info(
        f"FBRef xG lookup: {len(lookup)} entries from {teams_with_xg}/{attempted_teams} team-seasons "
        f"({null_only_skipped} files skipped — no xG column/rows)"
    )
    return lookup


# ---------------------------------------------------------------------------
# Primary loader
# ---------------------------------------------------------------------------

def load_raw_matches(
    seasons: Optional[list[str]] = None,
    data_dir: Path = DATA_DIR,
    enrich_xg: bool = True,
) -> pd.DataFrame:
    """
    Load all normalized match CSVs and return a combined DataFrame.

    One row per team per match (dual-row format). The caller is responsible
    for pivoting to single-row-per-match format for model training.

    Args:
        seasons:   List of season IDs to load (default: all).
        data_dir:  Root of the raw data directory.
        enrich_xg: If True, fill NULL xg_for/xg_against from FBRef CSVs.

    Returns:
        DataFrame with standardized dtypes and validated rows.
    """
    if seasons is None:
        seasons = SEASONS_ALL

    dfs = []
    for season in seasons:
        season_dir = data_dir / season
        if not season_dir.exists():
            logger.warning(f"Season directory not found: {season_dir}")
            continue

        for team_dir in sorted(season_dir.iterdir()):
            if not team_dir.is_dir():
                continue
            csv_path = team_dir / "match_logs_normalized.csv"
            if not csv_path.exists():
                continue

            try:
                df = pd.read_csv(csv_path, low_memory=False)
                dfs.append(df)
            except Exception as e:
                logger.warning(f"Failed to read {csv_path}: {e}")

    if not dfs:
        raise RuntimeError(f"No match data found in {data_dir} for seasons {seasons}")

    df = pd.concat(dfs, ignore_index=True)
    logger.info(f"Loaded {len(df)} raw rows from {len(dfs)} team-season CSVs")

    df = _clean_and_validate(df)

    if enrich_xg:
        xg_lookup = _load_fbref_xg(data_dir, seasons)
        if xg_lookup:
            df = _fill_xg_from_lookup(df, xg_lookup)
        else:
            logger.warning("[xG] FBRef lookup is empty — xG will remain NULL for all rows")

    _log_xg_coverage(df)
    return df


def _clean_and_validate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize dtypes, drop invalid rows, and validate data contract.
    """
    # Parse dates
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")

    # Drop rows missing required fields
    before = len(df)
    df = df.dropna(subset=["match_id", "season_id", "team_id", "opponent_id",
                            "match_date", "venue", "result"])
    df = df[df["result"].isin(VALID_RESULTS)]
    df = df[df["venue"].isin(VALID_VENUES)]
    dropped = before - len(df)
    if dropped:
        logger.warning(f"Dropped {dropped} rows with missing/invalid required fields")

    # Cast numeric columns
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Validate non-negative goals
    invalid_goals = df[(df["goals_for"] < 0) | (df["goals_against"] < 0)]
    if len(invalid_goals):
        logger.warning(f"Found {len(invalid_goals)} rows with negative goals — dropping")
        df = df[~((df["goals_for"] < 0) | (df["goals_against"] < 0))]

    # Validate result consistency
    result_consistent = (
        ((df["result"] == "W") & (df["goals_for"] > df["goals_against"])) |
        ((df["result"] == "D") & (df["goals_for"] == df["goals_against"])) |
        ((df["result"] == "L") & (df["goals_for"] < df["goals_against"]))
    )
    bad_results = ~result_consistent
    if bad_results.sum():
        logger.warning(f"Dropped {bad_results.sum()} rows with inconsistent result/goals")
        df = df[result_consistent]

    # Deduplicate (same CSV loaded from multiple paths in some cases)
    before = len(df)
    df = df.drop_duplicates(subset=["match_id", "team_id"])
    if len(df) < before:
        logger.info(f"Removed {before - len(df)} duplicate (match_id, team_id) rows")

    # Sort chronologically
    df = df.sort_values(["match_date", "match_id", "team_id"]).reset_index(drop=True)

    _log_data_quality(df)
    return df


def _fill_xg_from_lookup(df: pd.DataFrame, lookup: dict) -> pd.DataFrame:
    """Fill NULL xg_for/xg_against from FBRef lookup without overwriting existing values."""
    date_str = df["match_date"].dt.strftime("%Y-%m-%d")
    filled = 0
    attempted = 0
    unmatched = 0

    xgf = df["xg_for"].copy() if "xg_for" in df.columns else pd.Series(np.nan, index=df.index)
    xga = df["xg_against"].copy() if "xg_against" in df.columns else pd.Series(np.nan, index=df.index)

    for i in df.index:
        need_xgf = pd.isna(xgf[i])
        need_xga = pd.isna(xga[i])
        if not need_xgf and not need_xga:
            continue  # both already populated — never overwrite
        attempted += 1
        key = (date_str[i], df.at[i, "team_id"], df.at[i, "opponent_id"])
        val = lookup.get(key)
        if val is None:
            unmatched += 1
            continue
        newly_filled = False
        if need_xgf and val[0] is not None:
            xgf[i] = val[0]
            newly_filled = True
        if need_xga and val[1] is not None:
            xga[i] = val[1]
            newly_filled = True
        if newly_filled:
            filled += 1

    df["xg_for"]     = xgf
    df["xg_against"] = xga
    logger.info(
        f"FBRef xG enrichment: {filled} rows filled, "
        f"{unmatched}/{attempted} attempted rows had no lookup match"
    )
    return df


def _log_data_quality(df: pd.DataFrame) -> None:
    """Log a concise data quality summary (pre-enrichment)."""
    total = len(df)
    logger.info(f"Data quality summary ({total} rows):")
    for season, grp in df.groupby("season_id"):
        n = len(grp)
        teams = grp["team_id"].nunique()
        logger.info(f"  {season}: {n} rows, {teams} teams")

    for col in ["shots_for"]:
        if col in df.columns:
            null_rate = df[col].isna().mean()
            if null_rate > 0.5:
                logger.warning(f"  Column {col!r} is >50% NULL ({null_rate:.0%})")


def _log_xg_coverage(df: pd.DataFrame) -> dict:
    """
    Log per-season xG coverage after enrichment and persist a JSON artifact.

    Returns a dict keyed by season_id with coverage metrics.
    """
    coverage: dict = {}
    logger.info("[xG] Post-enrichment coverage by season:")
    for season, grp in df.groupby("season_id"):
        n = len(grp)
        xg_rows = int(grp["xg_for"].notna().sum()) if "xg_for" in grp.columns else 0
        pct = round(xg_rows / n * 100, 1) if n else 0.0
        teams_with_xg = int(grp[grp["xg_for"].notna()]["team_id"].nunique()) if "xg_for" in grp.columns else 0
        teams_total = int(grp["team_id"].nunique())
        coverage[str(season)] = {
            "rows": n,
            "xg_rows": xg_rows,
            "coverage_pct": pct,
            "teams_with_xg": teams_with_xg,
            "teams_total": teams_total,
        }
        status = "OK" if pct >= 80 else ("PARTIAL" if pct > 0 else "NONE")
        logger.info(
            f"  [{status}] {season}: {xg_rows}/{n} rows ({pct:.0f}%), "
            f"{teams_with_xg}/{teams_total} teams"
        )
        if pct < 80:
            logger.warning(
                f"  [xG] {season} coverage is low ({pct:.0f}%). "
                f"Run 02_normalize_and_export.py with Kaggle xG CSV to improve, "
                f"or verify FBRef CSVs in data/raw/{season}/."
            )

    try:
        artifact_path = ARTIFACTS_DIR / "xg_coverage_report.json"
        with open(artifact_path, "w") as fh:
            json.dump(coverage, fh, indent=2)
        logger.info(f"[xG] Coverage report written to {artifact_path}")
    except Exception as e:
        logger.debug(f"[xG] Could not write coverage artifact: {e}")

    return coverage


def validate_data_contract(df: pd.DataFrame) -> dict:
    """
    Run DATA_CONTRACT.md checks and return a summary dict.

    Supports two shapes:
      - International (WC pivot): competition_id column, FIFA team_id codes
      - Legacy EPL: club names as team_id, ~38 matches per team per season

    Raises ValueError if critical checks fail (missing columns, bad codes, etc.).
    Warnings (sparse seasons, high NULL xG) do not fail validation.

    Returns:
        dict with keys: passed, total_rows, warnings, errors
    """
    errors   = []
    warnings = []

    # --- 1. Required columns (same for EPL and international) ---
    for col in REQUIRED_COLS:
        if col not in df.columns:
            errors.append(f"Missing required column: {col!r}")

    if errors:
        raise ValueError(f"Data contract violations: {errors}")

    # --- 2. Row counts — different expectations per data shape ---
    is_intl = "competition_id" in df.columns
    if is_intl:
        # Each match_id should appear exactly twice (home row + away row)
        for (comp, season), grp in df.groupby(["competition_id", "season_id"]):
            n_matches = grp["match_id"].nunique()
            n_rows = len(grp)
            expected = n_matches * 2
            if n_rows < expected:
                warnings.append(
                    f"{comp}/{season}: {n_rows} rows but expected {expected} "
                    f"({n_matches} matches × 2)"
                )
        # International team_id must be FIFA 3-letter codes (BRA, ENG, …)
        bad_codes = df[
            ~df["team_id"].astype(str).str.fullmatch(r"[A-Z]{3}", na=False)
        ]
        if len(bad_codes):
            errors.append(f"{len(bad_codes)} rows with non-FIFA team_id codes")
    else:
        # EPL: ~20 teams × 38 matches ≈ 760 rows per season (dual-row)
        for season, grp in df.groupby("season_id"):
            n_teams = grp["team_id"].nunique()
            n_rows = len(grp)
            expected = n_teams * 38
            if n_rows < expected * 0.8:
                warnings.append(
                    f"{season}: only {n_rows} rows for {n_teams} teams "
                    f"(expected ~{expected})"
                )

    # 3. Duplicate match-team combinations
    dupes = df.duplicated(subset=["match_id", "team_id"]).sum()
    if dupes:
        errors.append(f"{dupes} duplicate (match_id, team_id) combinations")

    # 4. Impossible values
    neg_goals = (df["goals_for"] < 0).sum() + (df["goals_against"] < 0).sum()
    if neg_goals:
        errors.append(f"{neg_goals} rows with negative goals")

    # 5. Invalid result/venue
    bad_result = (~df["result"].isin(VALID_RESULTS)).sum()
    bad_venue  = (~df["venue"].isin(VALID_VENUES)).sum()
    if bad_result:
        errors.append(f"{bad_result} rows with invalid result")
    if bad_venue:
        errors.append(f"{bad_venue} rows with invalid venue")

    # 5b. Result must match goals_for / goals_against on each row
    result_consistent = (
        ((df["result"] == "W") & (df["goals_for"] > df["goals_against"])) |
        ((df["result"] == "D") & (df["goals_for"] == df["goals_against"])) |
        ((df["result"] == "L") & (df["goals_for"] < df["goals_against"]))
    )
    if (~result_consistent).sum():
        errors.append(f"{(~result_consistent).sum()} rows with inconsistent result/goals")

    # 6. xG range sanity
    if "xg_for" in df.columns:
        xg_valid = df["xg_for"].dropna()
        if (xg_valid < 0).any():
            errors.append("Negative xg_for values found")
        if (xg_valid > 15).any():
            warnings.append("xg_for > 15 in some rows — check data")

    # 7. NULL rate warnings
    for col in ["xg_for", "shots_for"]:
        if col in df.columns:
            null_rate = df[col].isna().mean()
            if null_rate > 0.3:
                warnings.append(f"{col} is {null_rate:.0%} NULL")

    if errors:
        raise ValueError(f"Data contract violations: {errors}")

    return {
        "passed": True,
        "total_rows": len(df),
        "warnings": warnings,
        "errors": [],
    }
