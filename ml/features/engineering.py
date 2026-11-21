"""
Leakage-safe feature engineering for match outcome prediction.
Every feature for a match on date T uses only matches strictly before T (the shift(1) pattern), then dual rows pivot to one row per match.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from ml.config import (
    ROLLING_WINDOWS, MIN_MATCHES_REQUIRED, ELO_INITIAL, ELO_K_FACTOR, STATIC_DIR,
    K_FACTORS, DATA_DIR,
)

logger = logging.getLogger(__name__)

TEAM_MAP_CSV = STATIC_DIR / "team_map_intl.csv"

API_FOOTBALL_DIR = DATA_DIR / "api_football"


def _load_team_code_map() -> dict[str, str]:
    """Lower-cased provider name (alias or full_name) -> FIFA 3-letter code."""
    if not TEAM_MAP_CSV.exists():
        return {}
    tm = pd.read_csv(TEAM_MAP_CSV)
    mapping: dict[str, str] = {}
    for _, row in tm.iterrows():
        code = str(row.get("team_id", "")).strip().upper()
        if not code:
            continue
        for col in ("alias", "full_name"):
            name = str(row.get(col, "")).strip().lower()
            if name and name != "nan":
                mapping.setdefault(name, code)
    return mapping


def _load_possession() -> pd.DataFrame:
    cols = ["_dstr", "team_id", "possession_pct", "passes_accuracy"]
    if not API_FOOTBALL_DIR.exists():
        return pd.DataFrame(columns=cols)
    files = sorted(API_FOOTBALL_DIR.glob("*/*/possession_stats.csv"))
    if not files:
        return pd.DataFrame(columns=cols)

    name2code = _load_team_code_map()
    frames = [pd.read_csv(f) for f in files]
    allp = pd.concat(frames, ignore_index=True)
    allp["team_id"] = (allp["team_name"].astype(str).str.strip().str.lower()
                       .map(name2code))
    unmapped = allp["team_id"].isna().sum()
    if unmapped:
        logger.info("Possession: %d rows with unmapped team names skipped", int(unmapped))
    allp = allp.dropna(subset=["team_id"])
    allp["_dstr"] = allp["match_date"].astype(str).str[:10]
    allp["possession_pct"] = pd.to_numeric(allp["possession_pct"], errors="coerce")
    allp["passes_accuracy"] = pd.to_numeric(allp["passes_accuracy"], errors="coerce")
    allp = allp.drop_duplicates(subset=["_dstr", "team_id"])
    return allp[cols]


def _load_confederation_map() -> dict[str, str]:
    if not TEAM_MAP_CSV.exists():
        logger.warning("team_map_intl.csv not found at %s — confederation "
                       "defaults to OTHER for all teams", TEAM_MAP_CSV)
        return {}
    tm = pd.read_csv(TEAM_MAP_CSV)
    mapping: dict[str, str] = {}
    for _, row in tm.iterrows():
        code = str(row.get("team_id", "")).strip().upper()
        conf = str(row.get("confederation", "")).strip().upper()
        if code and conf and conf != "NAN":
            mapping.setdefault(code, conf)
    return mapping


def _compute_team_rolling(team_df: pd.DataFrame) -> pd.DataFrame:
    df = team_df.sort_values("match_date").copy()

    df["_pts"] = df["result"].map({"W": 3, "D": 1, "L": 0})

    df["_win"] = (df["result"] == "W").astype(float)

    for N in ROLLING_WINDOWS:
        mp = MIN_MATCHES_REQUIRED
        suffix = f"_{N}"

        # shift(1) keeps the current match out of its own feature.
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

    df["_season_pts_cum"] = df.groupby("season_id")["_pts"].transform(
        lambda s: s.shift(1).expanding().sum()
    )
    df["_season_matches"] = df.groupby("season_id")["_pts"].transform(
        lambda s: s.shift(1).expanding().count()
    )
    df["season_pts_rate"] = df["_season_pts_cum"] / df["_season_matches"].replace(0, np.nan)

    df["rest_days"] = df["match_date"].diff().dt.days

    # at_home_ avoids colliding with the home_ prefix the pivot adds.
    home_mask = df["venue"] == "Home"
    df["_home_win"] = np.where(home_mask, df["_win"], np.nan)
    df["at_home_win_rate_5"] = (
        df["_home_win"]
        .shift(1)
        .rolling(5, min_periods=1)
        .mean()
    )

    away_mask = df["venue"] == "Away"
    df["_away_win"] = np.where(away_mask, df["_win"], np.nan)
    df["at_away_win_rate_5"] = (
        df["_away_win"]
        .shift(1)
        .rolling(5, min_periods=1)
        .mean()
    )

    drop_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=drop_cols)

    return df


def _compute_h2h(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("match_date").reset_index(drop=True)

    h2h_win_3 = []
    h2h_win_5 = []
    h2h_draws_5 = []
    h2h_away_wins_5 = []
    h2h_total_goals_avg_5 = []

    for i, row in df.iterrows():
        team     = row["team_id"]
        opponent = row["opponent_id"]
        date     = row["match_date"]

        # Strictly earlier dates, so the match itself and same-day results never leak in.
        past = df[
            (df["team_id"] == team) &
            (df["opponent_id"] == opponent) &
            (df["match_date"] < date)
        ].sort_values("match_date")

        has_history = len(past) >= 1
        wins = (past["result"] == "W").astype(float)
        last5 = past.tail(5)

        h2h_win_3.append(wins.tail(3).mean() if has_history else np.nan)
        h2h_win_5.append(wins.tail(5).mean() if has_history else np.nan)

        # From this row's perspective, L means the opponent won.
        h2h_draws_5.append(
            (last5["result"] == "D").astype(float).mean() if has_history else np.nan)
        h2h_away_wins_5.append(
            (last5["result"] == "L").astype(float).mean() if has_history else np.nan)
        h2h_total_goals_avg_5.append(
            (last5["goals_for"] + last5["goals_against"]).mean() if has_history else np.nan)

    df["h2h_win_3"] = h2h_win_3
    df["h2h_win_5"] = h2h_win_5
    df["h2h_draws_5"] = h2h_draws_5
    df["h2h_away_wins_5"] = h2h_away_wins_5
    df["h2h_total_goals_avg_5"] = h2h_total_goals_avg_5
    return df


def compute_elo_features(df: pd.DataFrame) -> pd.DataFrame:
    """Attaches each team's pre-match ELO to every row of the dual-row frame."""
    df = df.copy()

    # Never reset between seasons: team quality persists.
    elos: dict = {}
    pre_match_elo: dict = {}

    for date, day_df in df.sort_values(["match_date", "match_id"]).groupby("match_date"):
        # Start-of-day snapshot, so the order of same-day matches can't leak results.
        snapshot: dict = {}
        for team in day_df["team_id"].unique():
            snapshot[team] = elos.get(team, ELO_INITIAL)

        for mid, tid in zip(day_df["match_id"], day_df["team_id"]):
            pre_match_elo[(mid, tid)] = snapshot[tid]

        # Home rows only, so each physical match updates once.
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

            k = K_FACTORS.get(row.get("competition_id"), ELO_K_FACTOR)
            elos[home_team] = h_elo + k * (actual_home - expected_home)
            elos[away_team] = a_elo + k * ((1.0 - actual_home) - (1.0 - expected_home))

    df["elo"] = [
        pre_match_elo.get((mid, tid), ELO_INITIAL)
        for mid, tid in zip(df["match_id"], df["team_id"])
    ]
    return df


def _add_diff_features(df: pd.DataFrame) -> pd.DataFrame:
    diff_bases = [
        "form_pts_3", "form_pts_5", "form_pts_10",
        "form_win_5",
        "gf_avg_5", "ga_avg_5",
        "xgf_avg_5", "xga_avg_5",
        "season_pts_rate",
        "elo",
        "possession_avg_5",
    ]
    for base in diff_bases:
        home_col = f"home_{base}"
        away_col = f"away_{base}"
        if home_col in df.columns and away_col in df.columns:
            df[f"diff_{base}"] = df[home_col] - df[away_col]
    return df


def build_team_features(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing team rolling features...")

    parts = []
    for team_id, team_df in df.groupby("team_id"):
        enriched = _compute_team_rolling(team_df)
        parts.append(enriched)

    result = pd.concat(parts, ignore_index=False).sort_index()

    # Static per-team metadata, so it can't leak.
    conf_map = _load_confederation_map()
    result["confederation"] = (
        result["team_id"].map(conf_map).fillna("OTHER").astype(str)
    )

    # Only fetched competitions have possession; the rest stays NaN until train.build_xy fills 0.0.
    poss = _load_possession()
    result["_dstr"] = result["match_date"].dt.strftime("%Y-%m-%d")
    if not poss.empty:
        result = result.merge(poss, on=["_dstr", "team_id"], how="left")
        logger.info("Possession: joined %d team-match observations", int(poss.shape[0]))
    else:
        result["possession_pct"] = np.nan
        result["passes_accuracy"] = np.nan
        logger.info("Possession: no API-Football data found — features will be NULL")

    result = result.sort_values(["team_id", "match_date"])
    grp = result.groupby("team_id", sort=False)
    for N in (3, 5):
        result[f"possession_avg_{N}"] = grp["possession_pct"].transform(
            lambda s: s.shift(1).rolling(N, min_periods=1).mean())
        result[f"passes_acc_avg_{N}"] = grp["passes_accuracy"].transform(
            lambda s: s.shift(1).rolling(N, min_periods=1).mean())
    # Same-match possession is post-match info and must never be a feature.
    result = result.drop(columns=["possession_pct", "passes_accuracy", "_dstr"])
    result = result.sort_values(["match_date", "match_id", "team_id"]).reset_index(drop=True)

    logger.info(f"Team features computed. Shape: {result.shape}")
    return result


def build_h2h_features(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing head-to-head features...")
    # Quadratic scan; the pipeline caches the result.
    return _compute_h2h(df)


def pivot_to_match_rows(df: pd.DataFrame) -> pd.DataFrame:
    home = df[df["venue"] == "Home"].copy()
    home["match_outcome"] = home["result"].map({"W": "H", "D": "D", "L": "A"})

    away = df[df["venue"] == "Away"].copy()

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

    # The away row's team_id is the home row's opponent_id.
    home = home.merge(
        away_renamed.rename(columns={"team_id": "away_team_id"}),
        left_on=["match_id", "opponent_id"],
        right_on=["match_id", "away_team_id"],
        how="inner",
    )

    home_feature_cols = [c for c in away_feature_cols]
    rename_map = {c: f"home_{c}" for c in home_feature_cols if c in home.columns}
    home = home.rename(columns=rename_map)

    home = home.drop(columns=["away_team_id"], errors="ignore")

    home = home.rename(columns={
        "team_id":     "home_team",
        "opponent_id": "away_team",
    })

    home = home.sort_values(["match_date", "match_id"]).reset_index(drop=True)
    logger.info(f"Pivoted to {len(home)} single-row matches. Columns: {home.shape[1]}")
    return home


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    _id_cols = {"home_team", "away_team"}
    # Only prefixed columns are pre-match features; the rest is metadata, post-match stats or the target.
    return [
        c for c in df.columns
        if (c.startswith("home_") or c.startswith("away_") or c.startswith("diff_"))
        and c not in _id_cols
    ]


def build_features(
    df: pd.DataFrame,
    include_h2h: bool = True,
) -> pd.DataFrame:
    df = build_team_features(df)
    df = compute_elo_features(df)

    if include_h2h:
        df = build_h2h_features(df)

    df = pivot_to_match_rows(df)
    return _add_diff_features(df)
