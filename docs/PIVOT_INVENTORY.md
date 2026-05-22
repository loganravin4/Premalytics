# PIVOT-00 — EPL Baseline Inventory

Generated as part of the pivot to World Cup 2026 analytics.
**Archive tag:** `archive/epl-2025` (create before mass deletes — see git command below)

---

## Git archive command

Run this before touching any EPL-specific files:

```bash
git tag archive/epl-2025
git push origin archive/epl-2025   # if you want the tag remote
```

To create a branch instead (if you may want to continue EPL work):

```bash
git checkout -b archive/epl-2025
git push origin archive/epl-2025
git checkout main
```

---

## Path inventory

Each path is classified as one of:
- **REPLACE** — EPL-specific, remove from the default pipeline in this pivot
- **ADAPT** — Reusable logic, modify in place (no copy needed)
- **KEEP (archive only)** — Retain until ASSESS-01 decides whether EPL data helps WC models
- **KEEP (reusable)** — No EPL assumption, survives the pivot as-is

### Data pipeline

| Path | Classification | Notes |
|------|---------------|-------|
| `data-pipeline/scripts/01_download_match_data.py` | **DONE** (WC-03) | Now soccerdata → FBref; was football-data.co.uk E0 |
| `data-pipeline/scripts/02_normalize_and_export.py` | **DONE** (WC-03) | Now intl `{competition_id}/{season_id}/` CSVs |
| `data-pipeline/scripts/03_load_to_db.py` | **ADAPT** (WC-03) | Update target schema name from `pl_data` |
| `data-pipeline/soccer/importers/football_data_importer.py` | **KEEP (archive only)** | Contains `TEAM_NAME_MAP` (EPL clubs), `SEASON_URLS` pointing to E0 CSVs — do not wire into WC default pipeline; assess in ASSESS-01 |
| `data-pipeline/soccer/importers/xg_importer.py` | **KEEP (archive only)** | FBRef/Understat scraper for PL xG — assess in ASSESS-01 whether club-level shots help xG pretraining |
| `data-pipeline/soccer/importers/__init__.py` | **DONE** | Exports `FBrefInternationalImporter` only; EPL importers remain on disk |
| `data-pipeline/data/raw/` | **KEEP (archive only)** | Existing EPL CSVs; do not delete until ASSESS-01 closes |
| `data-pipeline/data/static/football_data_co_uk/` | **KEEP (archive only)** | Downloaded E0 CSVs |

### ML pipeline

| Path | Classification | Notes |
|------|---------------|-------|
| `ml/config.py` | **REPLACE** (WC-05) | `SEASONS_ALL/TRAIN/VALID/TEST` are EPL seasons; replace with tournament/date-based splits |
| `ml/features/engineering.py` | **ADAPT** (WC-05) | Core rolling/ELO logic is reusable; drop `venue`-as-home-advantage assumption and any league-table lookups |
| `ml/features/loader.py` | **ADAPT** (WC-05) | Update file path expectations to new raw layout |
| `ml/models/gradient_boost.py` | **ADAPT** | No EPL assumption — reuse as-is |
| `ml/models/baselines.py` | **ADAPT** | Reuse; rename target classes if needed |
| `ml/models/evaluation.py` | **ADAPT** | Reuse |
| `ml/pipeline/train.py` | **ADAPT** (WC-06) | Point at intl data; no EPL hardcoding |
| `ml/pipeline/evaluate.py` | **ADAPT** (WC-06) | Same |
| `ml/pipeline/predict.py` | **ADAPT** (WC-06) | Same |
| `ml/tests/test_validation.py` | **DONE** (WC-04) | Intl fixture + EPL synthetic rows |
| `ml/tests/test_features.py` | **ADAPT** (WC-05) | Update fixtures; leakage assertions survive |
| `ml/tests/test_enrichment.py` | **ADAPT** | Review for EPL-specific mocks |
| `ml/artifacts/` | **KEEP** | Gitignored run outputs; irrelevant to pivot |

### Database

| Path | Classification | Notes |
|------|---------------|-------|
| `database/schema/01_create_dimensions.sql` | **ADAPT** (WC-02 or later) | Schema named `pl_data`; rename to `soccer_data` or `wc_data` when committing to Postgres |
| `database/schema/02_create_matches.sql` | **ADAPT** | Same schema rename; add `competition_id`, `competition_stage`, `is_neutral_venue` columns |
| `database/schema/03_create_player_stats.sql` | **KEEP (archive only)** | EPL player stats; do not auto-migrate — ASSESS-01 decides |
| `database/schema/04_create_keeper_stats.sql` | **KEEP (archive only)** | Same |
| `database/schema/05_create_indexes.sql` | **ADAPT** | Update index targets after schema rename |
| `database/schema/06_add_match_stats.sql` | **ADAPT** | Review columns for international fit |

### Frontend

| Path | Classification | Notes |
|------|---------------|-------|
| `frontend/src/data/mockPredictions.ts` | **REPLACE** (FE-01) | EPL club matchups; replace with WC national team fixtures |
| `frontend/src/pages/Predictions.tsx` | **ADAPT** (FE-01) | Replace copy referencing "Premier League"; update mock → API wiring |
| `frontend/src/pages/Teams.tsx` | **REPLACE** (FE-01) | EPL club data |
| `frontend/src/pages/TeamDetail.tsx` | **REPLACE** (FE-01) | EPL club detail |
| `frontend/src/pages/Players.tsx` | **KEEP (archive only)** | Retain until player/squad feature scope (ASSESS-01) is resolved |
| `frontend/src/pages/PlayerDetail.tsx` | **KEEP (archive only)** | Same |
| `frontend/src/pages/Standings.tsx` | **REPLACE** (FE-01) | EPL league table; replace with WC group stage table |
| `frontend/src/pages/Dashboard.tsx` | **ADAPT** (FE-01) | Update headline copy and metrics for WC context |

### Docs + contract

| Path | Classification | Notes |
|------|---------------|-------|
| `DATA_CONTRACT.md` | **DONE** (WC-02) | Rewritten for international |
| `docs/LEGACY_EPL.md` | **KEEP** | Living list of EPL-era paths after WC-03 |
| `docs/WC_HANDOFF.md` | **KEEP** | Pivot roadmap — do not edit except to fill WC-00 table |

---

## ASSESS-01 candidates

These EPL assets are retained (not deleted) pending the ASSESS-01 data fitness review.
A source only enters the WC pipeline after ASSESS-01 assigns **Use** or **Experiment**.

| Asset | Potential use | Key risk |
|-------|--------------|----------|
| `football_data_importer.py` EPL match logs | Squad aggregate features for Track 1 | Club form ≠ international form; join to national squads is non-trivial |
| `xg_importer.py` FBRef/Understat club shots | Pretrain Track 2 xG model | Domain shift: PL shot distribution ≠ WC; requires documented calibration |
| `03_create_player_stats.sql` PL player stats | Squad depth / fatigue signals | Player ID join to national squads; `as_of` timing risk |
| `04_create_keeper_stats.sql` PL keeper stats | Keeper quality feature | Same join risk; limited WC impact signal proven |
| `data/raw/` EPL CSVs | Any of the above | Do not delete until ASSESS-01 verdict |
