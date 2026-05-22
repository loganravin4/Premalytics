# Premalytics Data Contract — International (WC pivot)

## Overview

Canonical schemas for **national-team** match data used by the World Cup pivot.
Any script that reads or writes pipeline data must conform to this contract.

**Ingest sources** (see `docs/WC_SOURCES.md`):

| Priority | Source | Typical use |
|----------|--------|-------------|
| Primary (when scrape works) | soccerdata → FBref | Schedules, scores, xG aggregates, lineups |
| Fallback | football-data.org API (free tier) | WC + Euro match results |
| Track 2 shots | StatsBomb open data | Shot-level xG (separate table) |
| Assess only | Archived EPL assets | Squad/club form per ASSESS-01 |

**Primary pipeline:**

```
01_download_match_data.py  →  02_normalize_and_export.py  →  (optional) 03_load_to_db.py
```

Uses `soccerdata` → FBref via `data-pipeline/soccer/importers/fbref_soccerdata_importer.py`.

Normalized output: **`match_logs_normalized.csv`** (same grain as legacy EPL contract).

---

## File: `match_logs_normalized.csv`

**Location:**

```
data-pipeline/data/raw/{competition_id}/{season_id}/match_logs_normalized.csv
```

| Path segment | Example | Notes |
|--------------|---------|-------|
| `competition_id` | `fifa_world_cup`, `uefa_euro`, `copa_america` | Stable snake_case slug — see table below |
| `season_id` | `2018`, `2022`, `2024` | Tournament year (single year); not `YYYY-YYYY` club format |

**Grain:** one row per **team per match** (dual-row: each fixture appears twice).

### Example rows (JSON)

Same physical match: Brazil 2–0 Serbia, 2022-11-24, group stage.

```json
{
  "match_id": "20221124_bra_srb",
  "competition_id": "fifa_world_cup",
  "season_id": "2022",
  "competition_stage": "group",
  "group_name": "G",
  "matchday": 1,
  "team_id": "BRA",
  "opponent_id": "SRB",
  "match_date": "2022-11-24",
  "venue": "Home",
  "is_neutral_venue": true,
  "goals_for": 2,
  "goals_against": 0,
  "result": "W",
  "xg_for": 1.8,
  "xg_against": 0.4,
  "shots_for": 14,
  "shots_against": 5,
  "sample_weight": 1.0
}
```

```json
{
  "match_id": "20221124_bra_srb",
  "competition_id": "fifa_world_cup",
  "season_id": "2022",
  "competition_stage": "group",
  "group_name": "G",
  "matchday": 1,
  "team_id": "SRB",
  "opponent_id": "BRA",
  "match_date": "2022-11-24",
  "venue": "Away",
  "is_neutral_venue": true,
  "goals_for": 0,
  "goals_against": 2,
  "result": "L",
  "xg_for": 0.4,
  "xg_against": 1.8,
  "shots_for": 5,
  "shots_against": 14,
  "sample_weight": 1.0
}
```

### Column definitions

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| match_id | str | No | See **Match ID** below |
| competition_id | str | No | Slug, e.g. `fifa_world_cup` |
| season_id | str | No | Tournament year, e.g. `2022` |
| competition_stage | str | No | `group`, `knockout`, `qualifier`, `friendly`, `final` |
| group_name | str | Yes | e.g. `G`; NULL for knockouts / friendlies |
| matchday | int | Yes | Round or matchday number when known |
| team_id | str | No | **FIFA 3-letter code** (e.g. `BRA`, `ENG`) |
| opponent_id | str | No | FIFA 3-letter code |
| match_date | date | No | `YYYY-MM-DD` (UTC calendar date of kickoff) |
| venue | str | No | `Home` or `Away` from `team_id` perspective |
| is_neutral_venue | bool | No | `true` for most WC/Euro neutral-site games |
| goals_for | int | No | Goals scored by `team_id` |
| goals_against | int | No | Goals conceded by `team_id` |
| result | str | No | `W`, `D`, or `L` from `team_id` perspective |
| xg_for | float | Yes | Team xG when source provides it |
| xg_against | float | Yes | Opponent xG |
| shots_for | int | Yes | |
| shots_against | int | Yes | |
| shots_on_target_for | int | Yes | |
| shots_on_target_against | int | Yes | |
| corners_for | int | Yes | |
| corners_against | int | Yes | |
| fouls_for | int | Yes | |
| fouls_against | int | Yes | |
| yellow_cards | int | Yes | |
| red_cards | int | Yes | |
| sample_weight | float | No | Default `1.0`; use `0.3` for friendlies when configured |
| source | str | No | `fbref`, `football_data_api`, etc. |
| source_match_key | str | Yes | Provider fixture id for joins / debugging |

**Display names** (e.g. `Brazil`) live in `data-pipeline/data/static/team_map_intl.csv`, not in `team_id`.

---

## Competition IDs

| competition_id | Description | soccerdata league (if used) |
|----------------|-------------|-----------------------------|
| `fifa_world_cup` | FIFA World Cup | `INT-World Cup` |
| `uefa_euro` | UEFA European Championship | `INT-European Championship` |
| `copa_america` | Copa América | `INT-Copa America` (custom `league_dict.json`) |
| `wcq_uefa` | UEFA World Cup qualifiers | `INT-WCQ UEFA` (custom) |
| `wcq_conmebol` | CONMEBOL World Cup qualifiers | `INT-WCQ CONMEBOL` (custom) |
| `uefa_nations_league` | UEFA Nations League | `INT-Nations League` (custom) |
| `international_friendly` | Friendlies | TBD — often **Defer** |

---

## Team ID convention

**`team_id` = FIFA 3-letter country code** (uppercase).

Examples: `BRA`, `ENG`, `USA`, `GER`, `CIV`

- Aliases and display names: `data-pipeline/data/static/team_map_intl.csv`
- Columns: `alias`, `team_id`, `team_name`
- Importers must normalize provider names to codes before writing CSVs

---

## Season ID convention

**Single tournament year** as string: `"2018"`, `"2022"`, `"2024"`.

- Euro 2020 played in 2021 → `season_id` = `"2020"` (tournament name year), with optional `calendar_year` in raw ingest only
- Do not use club-style `YYYY-YYYY` in this contract

---

## Match ID convention

Format:

```
{yyyymmdd}_{home_team_id}_{away_team_id}
```

- `yyyymmdd`: kickoff date in UTC (or documented local date if UTC unavailable)
- `home_team_id` / `away_team_id`: FIFA codes of designated home/away teams in the **fixture**
- For neutral venues, home/away follows the provider’s designation (consistent per source)

Example: `20221124_BRA_SRB` — store lowercase slugs in filenames if desired: `20221124_bra_srb`

**Stability:** same source fixture + same home/away assignment → same `match_id`.

---

## ML data splits

Use **chronological** boundaries by `match_date`, not random rows.

| Split | Suggested scope | Purpose |
|-------|-----------------|---------|
| Train | WC 2018 + Euro 2020 + Copa 2021 + qualifiers (weighted) | Fit |
| Validation | WC 2022 + Euro 2024 (or last full tournament before holdout) | Tune |
| Test (holdout) | Reserved tournament slice or post-2024 friendlies only | One-shot eval |

Exact dates live in `ml/config.py` after WC-05. **Holdout must never leak into feature engineering.**

**Sample weights:**

| competition_stage | Default weight |
|-------------------|----------------|
| `group`, `knockout`, `final` | 1.0 |
| `qualifier` | 0.5 (experiment — tune in config) |
| `friendly` | 0.3 (`FRIENDLY_WEIGHT` in config) |

---

## Shot-level data (Track 2 — separate contract)

Not stored in `match_logs_normalized.csv`. See `docs/DATA_CONTRACT_SHOTS.md` (XG-01) when added.

StatsBomb open data: one row per shot; join to matches on `source_match_key` or derived `match_id`.

---

## Database (optional, deferred)

Legacy schema `pl_data` is EPL-specific. International load will use a new schema name (e.g. `intl_data`) in a later ticket — do not write new rows to `pl_data.matches`.

---

## Assumptions

1. Dual-row: each match_id appears exactly twice (once per team).
2. `result` must agree with `goals_for` / `goals_against` for that row.
3. Rows with missing `goals_for`, `goals_against`, or `result` are dropped.
4. xG and shot columns may be NULL; models must tolerate NULLs.
5. Features use only information available **before kickoff** unless a later ticket defines lineup-aware prediction time.
6. EPL archives are **not** part of this contract until ASSESS-01 approves joins.

---

## Legacy EPL contract

Archived on git tag `archive/epl-2025`. Previous `match_logs_normalized` EPL paths and `pl_data` docs are historical only.
