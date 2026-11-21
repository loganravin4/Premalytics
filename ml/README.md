# Neutral Ground ML pipeline

Match outcome, shot xG, and penalty models for international football, evaluated without leakage.
Results and decisions: [`docs/ML_EXPERIMENTS.md`](../docs/ML_EXPERIMENTS.md) (match model),
[`docs/XG_MODEL.md`](../docs/XG_MODEL.md) (shot xG), [`docs/PENALTY_LIMITATIONS.md`](../docs/PENALTY_LIMITATIONS.md) (penalties).

## Setup

Everything runs from the repo root in the `data-pipeline/venv` Python 3.12 venv (see `docs/VENV.md`). No database is needed.

```bash
py -3.12 -m venv data-pipeline/venv
data-pipeline/venv/Scripts/pip install -r requirements.txt -r ml/requirements.txt
python -m pytest ml/tests -q
```

## Match model

The served model is a blend: 0.2 × gradient-boosted classifier + 0.8 × Dixon-Coles score model, then temperature scaling.
Blend weight and temperature are fit only on tournaments that finished before the prediction cutoff.

```bash
python -m ml.pipeline.train            # GBM + logistic on everything before TRAIN_CUTOFF_DATE (ml/config.py)
python -m ml.pipeline.backtest         # walk-forward over every major tournament since 2014 (~9 min)
python -m ml.pipeline.train_ensemble --run-id <run> --variant blend_temp   # attach the blend to a run
python -m ml.pipeline.predict --fixtures data-pipeline/data/wc2026_full_fixtures.csv --as-of 2026-06-11 --include-raw
python data-pipeline/scripts/05_evaluate_wc2026.py
```

- **Splits are by date, never random.** Training stops at `TRAIN_CUTOFF_DATE` (11 June 2026, the WC 2026 opener).
- **`--as-of`** freezes every team's form at that date; use the tournament start for retrospectives, or knockout fixtures read form from earlier rounds.
- **Fixtures CSV:** `match_date,home_team,away_team,is_neutral_venue,competition_id,competition_stage`, teams as three-letter codes from `data-pipeline/data/static/team_map_intl.csv` (see `data-pipeline/data/static/examples/wc_fixtures.csv`).
- **Output:** JSON on stdout, one object per fixture with `p_home_win`, `p_draw`, `p_away_win` (plus raw columns with `--include-raw`).

### Features (GBM)

123 columns per fixture, all from matches strictly before it: Elo and its gap, rolling form over 3/5/10 matches (points, wins, goals, xG, shots, shots on target, corners, possession, passing), head-to-head over the last five meetings, rest days, confederation, and neutral venue. `ml/tests/test_features.py` checks for leakage.

### Metrics

Ranked probability score (primary), log loss, Brier, accuracy, draw recall, and per-class reliability. Knockouts are reported two ways, always side by side: **raw** (a shootout counts as a draw) and **shootout-credited** (draw mass split between the teams, shootout winner scored as the result).

## Shot xG

```bash
python data-pipeline/scripts/shots/01_export_statsbomb_shots.py   # all StatsBomb open international shots
python -m ml.pipeline.train_shots
python -m ml.pipeline.evaluate_shots
python -m ml.pipeline.export_xg_grid                               # ml/exports/xg_grid.json for the frontend
python -m ml.pipeline.predict_shot --distance 12 --angle 35 --body-part right_foot
```

## Penalties

```bash
python data-pipeline/scripts/penalties/01_build_penalty_csv.py
python -m ml.pipeline.evaluate_penalties                           # ml/exports/penalty_aggregates.json
```

Descriptive only: no pre-kick predictor beats the overall conversion rate.

## Artifacts

Gitignored, under `ml/artifacts/`. `latest_run.txt` and `latest_shot_run.txt` name the runs that `predict`, `predict_shot`, and `ml/serve` load.

```
ml/artifacts/
├── <match run>/          gradient_boosting.joblib, logistic_regression.joblib, features.joblib, feature_cols.json,
│                         metrics.json, and after train_ensemble: ensemble.json, dixon_coles.joblib, reliability.json
├── backtest_<timestamp>/ metrics.json, predictions.csv, reliability.json, summary.md
└── shot_xg_<timestamp>/  shot models and evaluation output
```

## Serving

`ml/serve/` is a FastAPI app that loads the latest runs once at startup; the Spring backend calls it. See `backend/README.md`.

## Open work

Tracked in [`docs/ROADMAP.md`](../docs/ROADMAP.md): feature ablation (ML-06), tournament simulator (ML-07), confidence intervals (ML-08), and deduplicating the 18 tournament matches that appear in both FBref and martj42 with home/away swapped (`ml/features/loader.py`).
