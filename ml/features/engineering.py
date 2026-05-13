"""
Leakage-safe feature engineering for match outcome prediction.

For every match on date T:
  - Team rolling stats use ONLY matches played strictly before T.
  - No post-match information (shots/xG from the match itself) is used.
  - Features are computed from the dual-row DataFrame, then pivoted to
    single-row-per-match (home team vs away team) for model training.

Leakage check: features for match i are derived from df.iloc[:i] only
               (time-sorted), guaranteed by the shift(1) pattern.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from ml.config import ROLLING_WINDOWS, MIN_MATCHES_REQUIRED, ELO_INITIAL, ELO_K_FACTOR

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Single-team rolling features
# ---------------------------------------------------------------------------

def _compute_team_rolling(team_df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a DataFrame for ONE team (all matches, sorted by date),
    compute rolling statistics using only past matches (shift(1) = exclude current).

    Returns the same DataFrame with new feature columns added.
    """
    df = team_df.sort_values("match_date").copy()

    # Points per match (W=3, D=1, L=0)
    df["_pts"] = df["result"].map({"W": 3, "D": 1, "L": 0})

    # Win indicator
    df["_win"] = (df["result"] == "W").astype(float)

    # For each rolling window, compute past-N rolling stats
    for N in ROLLING_WINDOWS:
        mp = MIN_MATCHES_REQUIRED
        suffix = f"_{N}"

        # Shift(1) so the current match is NOT included in its own feature
        df[f"form_pts{suffix}"]  = df["_pts"].shift(1).rolling(N, min_periods=mp).mean()
        df[f"form_win{suffix}"]  = df["_win"].shift(1).rolling(N, min_periods=mp).mean()
        df[f"gf_avg{suffix}"]    = df["goals_for"].shift(1).rolling(N, min_periods=mp).mean()
        df[f"ga_avg{suffix}"]    = df["goals_against"].shift(1).rolling(N, min_periods=mp).mean()

        if "xg_for" in df.columns:
            df[f"xgf_avg{suffix}"] = df["xg_for"].shift(1).rolling(N, min_periods=mp).mean()
            df[f"xga_avg{suffix}"] = df["xg_against"].shift(1).rolling(N, min_periods=mp).mean()

        if "shots_for" in df.columns:
            df[f"shots_avg{suffix}"]     = df["shots_for"].shift(1).rolling(N, min_periods=mp).mean()
            df[f"shots_ag_avg{suffix}"]  = df["shots_against"].shift(1).rolling(N, min_periods=mp).mean()

        if "shots_on_target_for" in df.columns:
            df[f"sot_avg{suffix}"]       = df["shots_on_target_for"].shift(1).rolling(N, min_periods=mp).mean()
            df[f"sot_ag_avg{suffix}"]    = df["shots_on_target_against"].shift(1).rolling(N, min_periods=mp).mean()

        if "corners_for" in df.columns:
            df[f"corners_avg{suffix}"]   = df["corners_for"].shift(1).rolling(N, min_periods=mp).mean()

    # Cumulative season points rate (points / matches played so far)
    df["_season_pts_cum"] = df.groupby("season_id")["_pts"].transform(
        lambda s: s.shift(1).expanding().sum()
    )
    df["_season_matches"] = df.groupby("season_id")["_pts"].transform(
        lambda s: s.shift(1).expanding().count()
    )
    df["season_pts_rate"] = df["_season_pts_cum"] / df["_season_matches"].replace(0, np.nan)

    # Rest days since last match (within any season)
    df["rest_days"] = df["match_date"].diff().dt.days

    # Home-specific rolling form (last 5 home matches)
    # Named with 'at_home_' prefix to avoid collision when pivot renames features
    home_mask = df["venue"] == "Home"
    df["_home_win"] = np.where(home_mask, df["_win"], np.nan)
    df["at_home_win_rate_5"] = (
        df["_home_win"]
        .shift(1)
        .rolling(5, min_periods=1)
        .mean()
    )

    # Away-specific rolling form (last 5 away matches)
    away_mask = df["venue"] == "Away"
    df["_away_win"] = np.where(away_mask, df["_win"], np.nan)
    df["at_away_win_rate_5"] = (
        df["_away_win"]
        .shift(1)
        .rolling(5, min_periods=1)
        .mean()
    )

    # Drop internal columns
    drop_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=drop_cols)

    return df


# ---------------------------------------------------------------------------
# Head-to-head features
# ---------------------------------------------------------------------------

def _compute_h2h(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each match, compute head-to-head win rate from the HOME team's perspective
    across the last 3 and 5 previous meetings between the two teams.

    Uses only matches strictly before the current date.
    Operates on the full (dual-row) dataset.
    """
    df = df.sort_values("match_date").reset_index(drop=True)

    h2h_win_3 = []
    h2h_win_5 = []

    for i, row in df.iterrows():
        team     = row["team_id"]
        opponent = row["opponent_id"]
        date     = row["match_date"]

        # Past meetings from team's perspective (strictly before this match's date)
        past = df[
            (df["team_id"] == team) &
            (df["opponent_id"] == opponent) &
            (df["match_date"] < date)
        ].sort_values("match_date")

        wins = (past["result"] == "W").astype(float)

        h2h_win_3.append(wins.tail(3).mean() if len(past) >= 1 else np.nan)
        h2h_win_5.append(wins.tail(5).mean() if len(past) >= 1 else np.nan)

    df["h2h_win_3"] = h2h_win_3
    df["h2h_win_5"] = h2h_win_5
    return df


# ---------------------------------------------------------------------------
# ELO ratings
# ---------------------------------------------------------------------------

def compute_elo_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attach a pre-match ELO rating to every row in the dual-row DataFrame.

    Temporal safety guarantees:
      - ELO for match T reflects only results from matches strictly before T.
      - Same-day matches all receive start-of-day ELOs; the ordering of matches
        within a single date cannot introduce leakage.
      - ELO carries across seasons (intentional — team quality is persistent).

    Formula:
        E_home = 1 / (1 + 10^((elo_away - elo_home) / 400))
        new_elo = elo + K * (actual - E)
        actual: W=1.0, D=0.5, L=0.0
    """
    df = df.copy()

    elos: dict = {}                 # team_id → current ELO (updated after each match)
    pre_match_elo: dict = {}        # (match_id, team_id) → ELO before this match

    for date, day_df in df.sort_values(["match_date", "match_id"]).groupby("match_date"):
        # Step 1: snapshot every team's ELO at the start of this date
        snapshot: dict = {}
        for team in day_df["team_id"].unique():
            snapshot[team] = elos.get(team, ELO_INITIAL)

        # Step 2: record pre-match ELO for all rows today
        for mid, tid in zip(day_df["match_id"], day_df["team_id"]):
            pre_match_elo[(mid, tid)] = snapshot[tid]

        # Step 3: update ELOs using home-team rows (each physical match processed once)
        for _, row in day_df[day_df["venue"] == "Home"].iterrows():
            home_team = row["team_id"]
            away_team = row["opponent_id"]

            h_elo = snapshot.get(home_team, ELO_INITIAL)
            a_elo = snapshot.get(away_team, ELO_INITIAL)

            expected_home = 1.0 / (1.0 + 10.0 ** ((a_elo - h_elo) / 400.0))

            if row["result"] == "W":
                actual_home = 1.0
            elif row["result"] == "D":
                actual_home = 0.5
            else:
                actual_home = 0.0

            elos[home_team] = h_elo + ELO_K_FACTOR * (actual_home - expected_home)
            elos[away_team] = a_elo + ELO_K_FACTOR * ((1.0 - actual_home) - (1.0 - expected_home))

    df["elo"] = [
        pre_match_elo.get((mid, tid), ELO_INITIAL)
        for mid, tid in zip(df["match_id"], df["team_id"])
    ]
    return df


# ---------------------------------------------------------------------------
# Opponent-relative differential features (post-pivot)
# ---------------------------------------------------------------------------

def _add_diff_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add home-minus-away differential features to the single-row-per-match DataFrame.

    All inputs are derived from already-leakage-safe per-team features, so no
    additional temporal constraints are introduced here.
    """
    diff_bases = [
        "form_pts_3", "form_pts_5", "form_pts_10",
        "form_win_5",
        "gf_avg_5", "ga_avg_5",
        "xgf_avg_5", "xga_avg_5",
        "season_pts_rate",
        "elo",
    ]
    for base in diff_bases:
        home_col = f"home_{base}"
        away_col = f"away_{base}"
        if home_col in df.columns and away_col in df.columns:
            df[f"diff_{base}"] = df[home_col] - df[away_col]
    return df


# ---------------------------------------------------------------------------
# Main feature builder
# ---------------------------------------------------------------------------

def build_team_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-team rolling features for every match row.

    Returns the same dual-row DataFrame enriched with feature columns.
    Each row's features reflect the team's historical stats BEFORE this match.
    """
    logger.info("Computing team rolling features...")

    parts = []
    for team_id, team_df in df.groupby("team_id"):
        enriched = _compute_team_rolling(team_df)
        parts.append(enriched)

    result = pd.concat(parts, ignore_index=False).sort_index()
    logger.info(f"Team features computed. Shape: {result.shape}")
    return result


def build_h2h_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute head-to-head features. Slow for large datasets — cached by pipeline.
    """
    logger.info("Computing head-to-head features...")
    return _compute_h2h(df)


def pivot_to_match_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert dual-row format → single-row-per-match for model training.

    Uses the Home team's row as the base. The Away team's features are
    joined in with an 'away_' prefix. The target is match_outcome:
      H = home win, D = draw, A = away win (from the Home team's result).

    Returns a DataFrame where each row = one physical match.
    """
    # Home perspective rows only
    home = df[df["venue"] == "Home"].copy()
    home["match_outcome"] = home["result"].map({"W": "H", "D": "D", "L": "A"})

    # Away perspective rows — rename columns with 'away_' prefix for features
    away = df[df["venue"] == "Away"].copy()

    # Feature columns are everything except metadata
    meta_cols = {
        "match_id", "season_id", "team_id", "opponent_id",
        "match_date", "venue", "result", "goals_for", "goals_against",
        "xg_for", "xg_against", "shots_for", "shots_against",
        "shots_on_target_for", "shots_on_target_against",
        "corners_for", "corners_against", "fouls_for", "fouls_against",
        "yellow_cards", "red_cards", "match_outcome",
    }
    away_feature_cols = [c for c in away.columns if c not in meta_cols]

    away_renamed = away[["match_id", "team_id"] + away_feature_cols].rename(
        columns={c: f"away_{c}" for c in away_feature_cols}
    )

    # Merge on match_id (home row has away team as opponent_id)
    # The away team's team_id matches the home row's opponent_id
    home = home.merge(
        away_renamed.rename(columns={"team_id": "away_team_id"}),
        left_on=["match_id", "opponent_id"],
        right_on=["match_id", "away_team_id"],
        how="inner",
    )

    # Rename home feature cols with 'home_' prefix
    home_feature_cols = [c for c in away_feature_cols]  # same set
    rename_map = {c: f"home_{c}" for c in home_feature_cols if c in home.columns}
    home = home.rename(columns=rename_map)

    # Clean up redundant columns
    home = home.drop(columns=["away_team_id"], errors="ignore")

    # Rename identifying columns for clarity
    home = home.rename(columns={
        "team_id":     "home_team",
        "opponent_id": "away_team",
    })

    home = home.sort_values(["match_date", "match_id"]).reset_index(drop=True)
    logger.info(f"Pivoted to {len(home)} single-row matches. Columns: {home.shape[1]}")
    return home


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """
    Return the list of model feature columns.

    After pivot_to_match_rows(), all pre-match features have a 'home_' or
    'away_' prefix. Only those columns are valid features; everything else is
    metadata, post-match stats, or the target label.
    """
    _id_cols = {"home_team", "away_team"}
    return [
        c for c in df.columns
        if (c.startswith("home_") or c.startswith("away_") or c.startswith("diff_"))
        and c not in _id_cols
    ]


def build_features(
    df: pd.DataFrame,
    include_h2h: bool = True,
) -> pd.DataFrame:
    """
    Full feature engineering pipeline:
      1. Compute rolling team features (leakage-free via shift(1))
      2. Optionally compute head-to-head features
      3. Pivot to single-row-per-match

    Args:
        df:          Raw dual-row match DataFrame from loader.
        include_h2h: Whether to compute H2H features (adds latency).

    Returns:
        Single-row-per-match DataFrame ready for model training.
    """
    df = build_team_features(df)
    df = compute_elo_features(df)

    if include_h2h:
        df = build_h2h_features(df)

    df = pivot_to_match_rows(df)
    return _add_diff_features(df)
