# Premalytics Data Contract

## Overview

This document describes the canonical data sources, schemas, and field definitions
used by the ML pipeline. Any script that reads or writes data must conform to this contract.

## Canonical Data Sources

| Source | Type | Coverage | Used for |
|--------|------|----------|----------|
| football-data.co.uk | Match CSV | 2021-22 through 2025-26 | Match outcomes, shots, corners, fouls, cards, odds |
| Understat (Kaggle CSV, optional) | Match xG CSV | 2021-22 through 2022-23 | xG enrichment (fallback) |
| FBRef scraped CSVs (legacy) | Player/match CSV | 2021-22 through 2024-25 | xG (primary), player stats |

**Primary pipeline (canonical):**
```
01_download_match_data.py  →  02_normalize_and_export.py  →  03_load_to_db.py
```
All ML features are derived from the normalized CSVs produced by step 02.

## File: `match_logs_normalized.csv`

**Location:** `data-pipeline/data/raw/{season}/{team_slug}/match_logs_normalized.csv`

**One row per team per match** (dual-row format: each physical match appears twice).

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| match_id | str | No | `{yyyymmdd}_{home_slug}_{away_slug}`, globally unique per match |
| season_id | str | No | `YYYY-YYYY` format (e.g., `2021-2022`) |
| team_id | str | No | Canonical team name (e.g., `Arsenal`). **team_id = team_name** |
| opponent_id | str | No | Canonical opponent name |
| match_date | date | No | `YYYY-MM-DD` format |
| venue | str | No | `Home` or `Away` (from team_id's perspective) |
| goals_for | int | No | Goals scored by team_id |
| goals_against | int | No | Goals conceded by team_id |
| result | str | No | `W`, `D`, or `L` (from team_id's perspective) |
| shots_for | int | Yes | Shots taken by team_id |
| shots_against | int | Yes | Shots conceded by team_id |
| shots_on_target_for | int | Yes | Shots on target by team_id |
| shots_on_target_against | int | Yes | Shots on target conceded |
| corners_for | int | Yes | Corners won by team_id |
| corners_against | int | Yes | Corners conceded |
| fouls_for | int | Yes | Fouls committed by team_id |
| fouls_against | int | Yes | Fouls committed against team_id |
| yellow_cards | int | Yes | Yellow cards received by team_id |
| red_cards | int | Yes | Red cards received by team_id |
| xg_for | float | Yes | Expected goals for team_id (NULL if source unavailable) |
| xg_against | float | Yes | Expected goals against team_id (NULL if source unavailable) |

## Database Schema: `pl_data.matches`

**Schema:** `pl_data` (PostgreSQL)

All columns from `match_logs_normalized.csv` plus additional FBRef fields:

| Column | DB Type | Source |
|--------|---------|--------|
| match_team_id | SERIAL PK | Auto |
| match_id | VARCHAR(50) | CSV |
| season_id | VARCHAR(20) FK | CSV |
| team_id | VARCHAR(50) FK | CSV (**= canonical team name**) |
| match_date | DATE | CSV |
| venue | VARCHAR(10) | CSV |
| opponent_id | VARCHAR(50) FK | CSV |
| result | CHAR(1) | CSV |
| goals_for | INTEGER | CSV |
| goals_against | INTEGER | CSV |
| xg_for | DECIMAL(5,2) | CSV / FBRef |
| xg_against | DECIMAL(5,2) | CSV / FBRef |
| shots_for | INTEGER | CSV |
| shots_against | INTEGER | CSV |
| shots_on_target_for | INTEGER | CSV |
| shots_on_target_against | INTEGER | CSV |
| corners_for | INTEGER | CSV |
| corners_against | INTEGER | CSV |
| fouls_for | INTEGER | CSV |
| fouls_against | INTEGER | CSV |
| yellow_cards | INTEGER | CSV |
| red_cards | INTEGER | CSV |

## Team ID Convention

**team_id is the canonical team name string.** Not a hash, not an integer.

Examples: `Arsenal`, `Manchester City`, `Nott'ham Forest`, `Newcastle Utd`

The canonical names are defined in `football_data_importer.py::TEAM_NAME_MAP`.
Any script that looks up teams must use these exact strings.

## Season ID Convention

Format: `YYYY-YYYY` (e.g., `2021-2022`, `2024-2025`).

Short forms (`2021-22`) are only used internally in the downloader — they are
always converted to the full form before storage.

## Match ID Convention

Format: `{yyyymmdd}_{home_slug}_{away_slug}`

- `yyyymmdd`: match date compact
- `home_slug`: lowercase, underscored home team name (e.g., `manchester_city`)
- `away_slug`: lowercase, underscored away team name

Example: `20231202_arsenal_wolves`

This is a **stable, deterministic identifier** — running the pipeline twice
for the same raw data always produces the same match_ids.

## ML Data Splits

| Split | Seasons | Purpose |
|-------|---------|---------|
| Train | 2021-2022, 2022-2023 | Model fitting |
| Validation | 2023-2024 | Hyperparameter tuning, model selection |
| Test (holdout) | 2024-2025 | Final honest evaluation — never used during development |

**Critical:** The holdout set must never influence any model decision.
Test metrics are reported once, at the end.

## Assumptions

1. A team relegated in year N does not appear in the dataset in year N+1.
2. xG data may be NULL for some matches (especially recent seasons). Models must handle this.
3. The first N matches of a team in a season have fewer prior matches for rolling features.
   `min_periods=1` is used so features are never dropped, but they are less reliable early.
4. Matches with missing `result`, `goals_for`, or `goals_against` are excluded entirely.
