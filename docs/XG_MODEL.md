# Shot xG Model (Track 2)

Covers XG-05 (more shots), XG-06 (better features), XG-07 (calibration and
validation), and XG-04 (inference contract and `xg_grid.json`). Data schema:
`docs/DATA_CONTRACT_SHOTS.md`.

## Run it

```powershell
.\data-pipeline\venv\Scripts\python.exe data-pipeline\scripts\shots\01_export_statsbomb_shots.py
.\data-pipeline\venv\Scripts\python.exe -m ml.pipeline.train_shots
.\data-pipeline\venv\Scripts\python.exe -m ml.pipeline.evaluate_shots
.\data-pipeline\venv\Scripts\python.exe -m ml.pipeline.export_xg_grid
```

Outputs go to `ml/artifacts/shot_xg_{ts}/`: `*.joblib`, `split.json`,
`production_model.json`, `shot_xg_metrics.json`, `xg_grid.json`.
`ml/exports/xg_grid.json` is the tracked copy for the frontend.

## Data and split (XG-05)

12,759 non-penalty shots from 16 international tournaments in StatsBomb open
data (after dropping 74 `body_part == other` shots). The split is by
tournament start date, so no tournament is divided:

| Set | Tournaments | Shots |
|---|---|---|
| Train | WC 1958–1990 (19 matches), WC 2018, WWC 2019, Euro 2020, WEuro 2022, WC 2022, WWC 2023, AFCON 2023 | **9,868** (6,131 men's, 3,737 women's) |
| ↳ validation fold | WWC 2023, AFCON 2023 (model selection only, then refit on all train) | 2,755 |
| Eval, headline | Euro 2024, Copa América 2024 (men's) | 2,033 |
| Eval, reported separately | Women's Euro 2025 | 858 |

Before XG-05 the model trained on WC 2018 only (1,624 shots) and was scored on
WC 2022 (1,417).

**Why women's shots are in training.** The men's pre-2024 shots total 6,131,
short of the 8,000 target. Women's tournaments add 3,737 shots with an
`is_womens` flag. Ablation: refitting the production model on men's shots only
gives men's eval log loss 0.2375 vs 0.2379 with women's shots included. The
extra data neither helps nor hurts the men's numbers; it is kept for the larger
training set and so the model can score women's matches.

## Features (XG-06)

All at the moment of the strike (`DATA_CONTRACT_SHOTS.md`):

- location: `distance_m`, `angle_deg`, `log_distance`
- `body_part` (right foot / left foot / head), `technique`, `situation`
- `first_time`, `under_pressure`, `assist_type` (cut-back, cross, through ball, pass, none)
- freeze frame: `n_def_in_cone`, `nearest_def_m`, `gk_dist_to_goal_m`,
  `gk_dist_to_shooter_m`, `gk_angle_offset_deg`, `ff_available`
- `is_womens`

Largest standardized logistic coefficients: overhead kick (−1.27), header
(−1.04), lob (+0.98), log distance (−0.81), backheel (−0.68), through-ball
assist (+0.59), nearest defender distance (+0.43), defenders in the cone (−0.40),
angle (−0.35). `under_pressure` drops to ~0 once the freeze-frame distances are in.

## Models

| Name | Inputs | Role |
|---|---|---|
| `logistic_xg` | distance, angle | Baseline. Kept for `06_backfill_xg.py`, which loads it by name. |
| `logistic_full` | all features above | **Production** |
| `gbm_full` | all features above, XGBoost depth 3 | Challenger |
| `grid_xg` | distance, angle, body part, situation | Powers `xg_grid.json` and the default CLI |

**Selection rule (set before looking at eval):** fit both full models on the
tournaments before the validation fold, score the validation fold, and pick the
lower log loss; a tie within 0.001 goes to the logistic. Validation:
logistic_full LL 0.2406 (Brier 0.0666), gbm_full LL 0.2417 (Brier 0.0667).
A sweep of six XGBoost settings (depth 2–5, 300–1,000 trees, isotonic/sigmoid/no
calibration) never beat the logistic by more than 0.0004 on validation.
Isotonic and sigmoid wrappers made the GBM worse, so it ships uncalibrated.

**Logistic is retained as production.** On the eval tournaments the GBM is
slightly ahead (below), but the match-clustered bootstrap interval of the gap
includes zero, so the eval set does not overturn the validation choice.

## Metrics: before and after

Headline = men's eval shots (Euro 2024 + Copa América 2024, n = 2,033, goal
rate 7.9%).

| Model | Brier | Log loss | ROC AUC |
|---|---|---|---|
| **Before:** v1 setup (distance + angle, trained on WC 2018 only) | 0.0697 | 0.2581 | 0.700 |
| `logistic_xg` (distance + angle, new training set) | 0.0701 | 0.2591 | 0.700 |
| `grid_xg` (location + body part + situation) | 0.0683 | 0.2500 | 0.733 |
| **After:** `logistic_full` (production) | **0.0660** | **0.2379** | **0.777** |
| `gbm_full` | 0.0655 | 0.2358 | 0.781 |
| StatsBomb xG on the same shots (reference only) | 0.0635 | 0.2305 | 0.789 |

Paired, match-clustered bootstrap (83 matches, 2,000 resamples), difference in
mean per-shot loss:

| Comparison | Δ log loss (95% CI) | Δ Brier (95% CI) |
|---|---|---|
| logistic_full − v1 | −0.0202 (−0.0295, −0.0112) | −0.0037 (−0.0066, −0.0011) |
| gbm_full − logistic_full | −0.0021 (−0.0074, +0.0031) | −0.0005 (−0.0023, +0.0012) |

More shots alone did nothing for the two-feature model (0.2591 vs 0.2581). The
gain comes from the new features, mostly freeze-frame context and technique.
The remaining gap to StatsBomb's own model is ~0.007 log loss.

Old v1 numbers (Brier 0.0870, LL 0.300) were measured on WC 2022, a different
eval set, and are not comparable to the table above.

Women's Euro 2025 (n = 858): logistic_full Brier 0.0863, LL 0.3015, AUC 0.762.
The model under-predicts there: mean xG 0.091 vs 11.1% observed.

## Calibration and per-match validation (XG-07)

Production model, men's eval shots. ECE 0.012 (0.008 on all eval shots).

| Predicted bin | Shots | Mean xG | Observed | 95% CI |
|---|---|---|---|---|
| 0–0.02 | 303 | 0.013 | 0.010 | 0.003–0.029 |
| 0.02–0.05 | 696 | 0.033 | 0.034 | 0.023–0.051 |
| 0.05–0.10 | 516 | 0.071 | 0.050 | 0.035–0.073 |
| 0.10–0.20 | 320 | 0.140 | 0.150 | 0.115–0.193 |
| 0.20–0.30 | 89 | 0.244 | 0.213 | 0.141–0.310 |
| 0.30–0.50 | 85 | 0.379 | 0.365 | 0.270–0.471 |
| 0.50–1.00 | 24 | 0.605 | 0.375 | 0.212–0.573 |

The top bin over-predicts (24 shots, 0.61 predicted vs 0.38 observed, outside
the interval). Treat xG above 0.5 as "very good chance", not a literal 60%.

Per-match totals (all 228 eval team-matches, men's and women's): summed xG
255.2 vs 255 non-penalty goals; mean bias +0.001 per team-match; MAE 0.71
(StatsBomb xG: 0.66); Pearson r between team-match xG and goals 0.58. The full
per-team-match list is in `shot_xg_metrics.json` → `per_match.rows`.

## Inference (XG-04)

`python -m ml.pipeline.predict_shot --distance 14.2 --angle 22.5`

- Default `--model grid` uses `grid_xg`, the same model as `xg_grid.json`, so the
  backend endpoint and the frontend lab agree. Optional `--body-part`,
  `--situation`.
- `--model full` uses the production model; freeze-frame flags
  (`--n-def-in-cone`, `--nearest-def`, `--gk-dist-to-goal`, …) are imputed when
  omitted.
- Default stdout is exactly `{p_goal, model, distance_m, angle_deg}`: the
  backend's strict `ObjectMapper` rejects extra keys. `--verbose` adds inputs
  and `latency_ms`.
- Latency: model load + prediction is **~6 ms** in-process. A CLI call takes
  ~1.5 s wall time, almost all Python start-up and the sklearn import; BE-05's
  long-lived service removes that.
- The `model` string changed from `shot_xg_logistic` to `shot_xg_grid` (or
  `shot_xg_logistic_full`).

## `xg_grid.json` schema

Path: `ml/exports/xg_grid.json` (tracked) and `ml/artifacts/{run}/xg_grid.json`.
Compact JSON, ~120 KB. Values are P(goal) for a non-penalty shot in a men's match
from `grid_xg`, rounded to 4 decimals.

```jsonc
{
  "schema_version": 1,
  "generated": "2026-11-21",
  "run_id": "shot_xg_20261121_142857",
  "model": "grid_xg",
  "label": "Model estimate, not official xG",       // show this in the UI
  "description": "…",
  "inputs": {
    "body_part": ["right_foot", "left_foot", "head"],
    "situation": ["open_play", "set_piece", "counter"]
  },
  "distance_angle": {
    "distance_m": [1, 2, …, 40],                      // 40 values
    "angle_deg":  [0, 5, …, 85],                      // 18 values; 0 = central
    "index_order": "values[body_part][situation][distance_index][angle_index]",
    "values": { "right_foot": { "open_play": [[0.9226, …], …] } },  // null = off the pitch
    "n_train_shots": [[20, 45, …], …]                 // [distance_index][angle_index], all body parts
  },
  "pitch": {
    "coordinate_system": "StatsBomb yards: 120 x 80 pitch, attacking toward x=120, goal center (120, 40)",
    "cell_size_yd": 2,
    "x": [61, 63, …, 119],                            // 30 cell centers
    "y": [1, 3, …, 79],                               // 40 cell centers
    "index_order": "values[body_part][situation][x_index][y_index]",
    "values": { "head": { "set_piece": [[…], …] } }
  },
  "metrics": {
    "grid_xg_eval": { "n": 2033, "brier_score": 0.06832, "log_loss": 0.25001, "roc_auc": 0.7333, … },
    "production_model_eval": { "model": "logistic_full", "headline": { … } }
  }
}
```

Notes for the frontend:

- Distance-angle lookups: nearest cell, or bilinear interpolation between cells.
  The pitch grid lets a draggable marker read values directly.
- `n_train_shots` is the training support per distance-angle cell (distance
  rounded to 1 m, angle to 5°). Fade or flag cells with fewer than ~10 shots:
  values there are extrapolated (for example a 1 m shot from 85° reads 0.83).
- The grid ignores defender and keeper positions, so it is a "typical shot from
  here" number. The production model with freeze-frame context is better
  (LL 0.238 vs 0.250) but needs inputs the lab does not collect.

## Limits

- One shot model for all international tournaments: no team, player, or keeper
  quality terms.
- Eval is two men's tournaments (2,033 shots, 160 goals). Differences under
  ~0.005 log loss are noise, as the bootstrap shows.
- Over-confident above 0.5 (see calibration).
- `data-pipeline/scripts/06_backfill_xg.py` still uses `logistic_xg`
  (distance + angle). Rerunning it now uses a baseline trained on 9,868 shots
  instead of 1,624, which changes the match model's xG features slightly.
  That is the match track's decision; nothing here reruns it.
