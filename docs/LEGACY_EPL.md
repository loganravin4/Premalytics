# Legacy EPL assets (post WC-03 ingest)

Premalytics pivoted to **international** data on `main`. These paths are **EPL-era** — still in the repo for reference, archive tag `archive/epl-2025`, and **ASSESS-01** review. They are **not** the default pipeline after WC-03.

**Do not wire legacy importers into scripts 01/02.** Do not delete raw EPL CSVs until ASSESS-01 closes.

---

## Replaced on main (no longer EPL default)

| Path | Now |
|------|-----|
| `data-pipeline/scripts/01_download_match_data.py` | soccerdata → FBref international |
| `data-pipeline/scripts/02_normalize_and_export.py` | Writes `raw/{competition_id}/{season_id}/match_logs_normalized.csv` |
| `data-pipeline/soccer/importers/__init__.py` | Exports `FBrefInternationalImporter` only |
| `DATA_CONTRACT.md` | International schema |
| `ml/tests/test_validation.py` | International fixture + EPL synthetic rows |

---

## Legacy code (still in repo, not exported / not wired)

| Path | Role |
|------|------|
| `data-pipeline/soccer/importers/football_data_importer.py` | Download/normalize **Premier League** CSVs from football-data.co.uk (`E0.csv`, club `TEAM_NAME_MAP`) |
| `data-pipeline/soccer/importers/xg_importer.py` | Merge **Understat/Kaggle** xG into EPL-shaped rows; FBref EPL folder lookup in `loader.py` |

---

## Legacy data on disk (gitignored or archive)

| Path | Role |
|------|------|
| `data-pipeline/data/static/football_data_co_uk/` | Downloaded EPL season CSVs (`2023-24_E0.csv`, etc.) |
| `data-pipeline/data/raw/2021-2022/` … `2025-2026/` | **Per-club** EPL layout: `raw/{season}/{team_slug}/match_logs_normalized.csv` |
| `data-pipeline/data/static/xg/` | Understat EPL xG CSV (if present) |

International output uses a **different** layout:

```
data-pipeline/data/raw/{competition_id}/{season_id}/match_logs_normalized.csv
```

---

## ML still EPL-oriented (WC-05+)

| Path | EPL assumption |
|------|----------------|
| `ml/config.py` | `SEASONS_*` = 2021–2025 Premier League seasons |
| `ml/features/loader.py` | `load_raw_matches()` walks `raw/{season}/{team}/`; FBref xG supplement uses EPL folder names |
| `ml/features/engineering.py` | Club/home-advantage and league-table style features |
| `ml/pipeline/train.py`, `evaluate.py`, `predict.py` | Point at EPL config/paths |
| `ml/tests/test_features.py` | EPL fixtures and leakage tests |
| `ml/tests/test_enrichment.py` | EPL/xG enrichment mocks |

Reusable without EPL-specific logic: `ml/models/` (baselines, gradient boost, evaluation helpers).

---

## Database (EPL schema)

| Path | Role |
|------|------|
| `database/schema/01_create_dimensions.sql` | `pl_data` dimensions |
| `database/schema/02_create_matches.sql` | EPL-style matches |
| `database/schema/03_create_player_stats.sql` | PL player season stats |
| `database/schema/04_create_keeper_stats.sql` | PL keeper stats |
| `database/schema/05_create_indexes.sql`, `06_add_match_stats.sql` | Indexes/columns for above |
| `data-pipeline/scripts/03_load_to_db.py` | Loads into `pl_data` (not updated for intl yet) |

---

## Frontend (EPL product UI)

| Path | Role |
|------|------|
| `frontend/src/data/mockPredictions.ts` | Mock EPL fixtures/predictions |
| `frontend/src/pages/Predictions.tsx` | Premier League copy |
| `frontend/src/pages/Teams.tsx`, `TeamDetail.tsx` | EPL clubs |
| `frontend/src/pages/Standings.tsx` | EPL league table |
| `frontend/src/pages/Players.tsx`, `PlayerDetail.tsx` | PL player browsing |
| `frontend/src/pages/Dashboard.tsx` | EPL-oriented dashboard |

Target replacement: **FE-01** (WC national teams).

---

## Docs and tags

| Item | Role |
|------|------|
| Git tag `archive/epl-2025` | Snapshot before pivot (create if missing — see `docs/PIVOT_INVENTORY.md`) |
| `docs/PIVOT_INVENTORY.md` | Original REPLACE/ADAPT/KEEP classification |
| `docs/DATA_ASSESSMENT.md` | Not written yet — gates any PL data in WC models |

---

## Quick check: is this file legacy?

- **Legacy:** club names as `team_id` (`Arsenal`), seasons like `2023-2024`, paths under `football_data_co_uk`, `pl_data` schema, EPL frontend mocks.
- **Current:** FIFA codes (`BRA`), `competition_id` (`fifa_world_cup`), single CSV per tournament year, `source=fbref`.
