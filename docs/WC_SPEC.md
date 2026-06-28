# WC_SPEC.md
### The Premalytics World Cup Pivot Constitution
> Every Claude Code task must reference this file. Claude Code implements specs — it does not make design decisions.

---

## 0. Task Completion Protocol

Every Claude Code task response must end with the following, in this order:

**Summary** — bullet list of everything created or modified, with one sentence on each decision worth noting.

**Decisions worth your review** — flag any ambiguity, spec conflict, or implementation choice that deviated from the task prompt. Be explicit. Do not bury these.

**Verification** — confirm the relevant quality gate commands passed. Paste the actual output or a summary of it.

**Draft commit message** — always included, formatted as a conventional commit. Subject line under 72 characters. Body lists the concrete file-level changes. Footer notes any open issues or flags. Format:

```
<type>(<scope>): <subject>

<body — what changed and why, file by file>

<footer — open issues, flags, follow-ups>
```

Types: feat, fix, refactor, chore, test, data. Scope is the layer touched (e.g. config, features, pipeline, data, frontend, tests).

---

## 1. What this repo is

Premalytics is a full-stack soccer analytics platform pivoting from EPL to **World Cup 2026**. The stack:

| Layer | Tech |
|-------|------|
| Frontend | React + TypeScript + Vite + Tailwind + Framer Motion |
| Backend | Spring Boot (Java) |
| ML pipeline | Python — scikit-learn, XGBoost, pandas |
| Data pipeline | Python — soccerdata/FBref importers, normalize scripts |
| Database | PostgreSQL |

The pivot is **in-place**. There is no `ml/wc/` sidecar tree. EPL code is archived at `archive/epl-2025`.

---

## 2. Non-goals (do not implement these)

- No parallel EPL pipeline on `main`
- No random train/test split on any time-series data — chronological splits only
- No feature that leaks same-match information (all rolling stats use strictly prior matches via `shift(1)`)
- No PL/player columns wired into WC features without an ASSESS-01 verdict of **Use** or **Experiment**
- No betting advice or high-confidence penalty "predictions"
- No `ml/wc/` tree — feature branches only

---

## 3. Data contract (locked — do not change schema)

The canonical output of the data pipeline is:

```
data-pipeline/data/raw/{competition_id}/{season_id}/match_logs_normalized.csv
```

**Grain:** one row per team per match (dual-row — each fixture appears twice).

**Key columns:** `match_id`, `competition_id`, `season_id`, `competition_stage`, `match_date`, `team_id`, `opponent_id`, `venue`, `goals_for`, `goals_against`, `result`, `is_neutral_venue`, `sample_weight`, `source`

Full schema in `DATA_CONTRACT.md`. Do not add columns not in the contract without noting it as a decision to review.

**Working data on disk (already downloaded):**
- `data-pipeline/data/raw/fifa_world_cup/2018/match_logs_normalized.csv` (WC 2018, 128 rows)
- `data-pipeline/data/raw/fifa_world_cup/2022/match_logs_normalized.csv` (WC 2022, 128 rows)

These are the training inputs for WC-05 and WC-06. Do not re-download or re-normalize them.

---

## 4. ML pipeline conventions

- **Config lives in `ml/config.py`** — all paths, seeds, splits, feature knobs
- **Splits are date-based or competition-based, never season strings like "2021-2022"**
- **Leakage rule:** features for match i use only rows with `match_date < match_date[i]`. Verified by `python -m pytest ml/tests/test_features.py -q`
- **Artifacts** go in `ml/artifacts/` (gitignored)
- **Quality gates:** `python -m pytest ml/tests -q` must be green before any task is complete
- **ELO config:** `ELO_INITIAL = 1500.0`, `ELO_K_FACTOR = 20.0` — do not change without flagging

---

## 5. Competition registry (locked)

| competition_id | soccerdata league | seasons in training | weight |
|----------------|-------------------|---------------------|--------|
| `fifa_world_cup` | `INT-World Cup` | 2018, 2022 | 1.0 |
| `uefa_euro` | `INT-European Championship` | 2020, 2024 | 1.0 |
| friendlies | custom / TBD | TBD | 0.3 (down-weight) |

Only `fifa_world_cup` data is currently on disk. `uefa_euro` ingest is a future task.

---

## 6. Frontend conventions

- Framework: React + TypeScript + Vite + Tailwind
- All EPL mock data lives in `frontend/src/data/` — **replace, do not extend**
- New pages go in `frontend/src/pages/`
- Env var for backend URL: `VITE_PREDICTIONS_URL`
- Build must pass `npm run build` with zero TypeScript errors

---

## 7. Branch naming (locked)

- `wc/foundation` — WC-02 through WC-04 (already merged)
- `wc/match` — WC-05 through WC-07
- `wc/xg` — XG-01 through XG-04
- `wc/penalties` — PEN-01 through PEN-03
- `wc/frontend` — FE-01 through FE-03

---

## 8. Files Claude Code must read before starting any task

1. This file (`docs/WC_SPEC.md`)
2. `docs/WC_HANDOFF.md` — full ticket specs and dependency graph
3. `DATA_CONTRACT.md` — canonical schema
4. The specific files named in the task prompt

Do not read and summarize — read, then implement. Questions go in "Decisions worth your review."
