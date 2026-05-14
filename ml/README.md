# Premalytics ML Pipeline

End-to-end EPL match outcome prediction with honest, leakage-free evaluation.

## Quick Start

```bash
# From the repo root — all commands run in the data-pipeline venv
cd premalytics

# 1. Download and normalize match data (if not already done)
python data-pipeline/scripts/01_download_match_data.py
python data-pipeline/scripts/02_normalize_and_export.py

# 2. Run tests
python -m pytest ml/tests/ -v

# 3. Train models
python -m ml.pipeline.train

# 4. Evaluate on holdout (2024-2025 season)
python -m ml.pipeline.evaluate

# 5. Predict upcoming fixtures
python -m ml.pipeline.predict --fixtures fixtures.csv
```

## Prerequisites

The ML pipeline reads directly from normalized CSVs — **no PostgreSQL required**.

```bash
# Activate the existing venv (or create one)
source data-pipeline/venv/Scripts/activate   # Windows: .\data-pipeline\venv\Scripts\activate

# Install ML dependencies
pip install -r ml/requirements.txt

# Optional: faster gradient boosting
pip install lightgbm
```

## Data Splits (Chronological)

| Split | Seasons | Rows (~) | Purpose |
|-------|---------|----------|---------|
| Train | 2021-22, 2022-23 | 1,520 | Model fitting |
| Validation | 2023-24 | 760 | Hyperparameter tuning |
| **Holdout** | **2024-25** | **760** | **Final honest evaluation** |

The holdout set is never touched during training decisions.

## Feature Engineering

All features are computed strictly from matches BEFORE the target match date.
Rolling windows: last 3, 5, and 10 matches per team.

**Per-team rolling features (home and away perspective):**
- `form_pts_{N}` — points per game (W=3, D=1, L=0) in last N matches
- `form_win_{N}` — win rate in last N matches
- `gf_avg_{N}` — goals for average
- `ga_avg_{N}` — goals against average
- `xgf_avg_{N}` — expected goals for average
- `xga_avg_{N}` — expected goals against average
- `shots_avg_{N}` — shots taken average
- `shots_ag_avg_{N}` — shots conceded average
- `sot_avg_{N}` — shots on target average
- `corners_avg_{N}` — corners average
- `at_home_win_rate_5` — win rate in last 5 home-venue matches
- `at_away_win_rate_5` — win rate in last 5 away-venue matches
- `rest_days` — days since last match
- `season_pts_rate` — cumulative points / games played this season

**Head-to-head (last 3 and 5 meetings):**
- `h2h_win_{3,5}` — win rate in recent head-to-head meetings

**ELO ratings (pre-match, carries across seasons):**
- `elo` — team ELO before this match (starts at 1500, K=20)
  - Formula: `E = 1/(1+10^((opp_elo − team_elo)/400))`, `new_elo = elo + K*(actual − E)`, actual: W=1, D=0.5, L=0
  - Same-day matches use start-of-day ELOs — no intra-day ordering dependency

**Opponent-relative differentials (home − away, post-pivot):**
- `diff_elo` — ELO delta (primary strength signal)
- `diff_form_pts_{3,5,10}` — points-per-game form differential
- `diff_form_win_5` — win-rate differential
- `diff_gf_avg_5`, `diff_ga_avg_5` — goal-scoring/conceding differential
- `diff_xgf_avg_5`, `diff_xga_avg_5` — xG differential (when available)
- `diff_season_pts_rate` — season points-rate differential

**Total features:** 90 (home_ + away_ rolling/ELO + diff_ differentials)

## Models

| Model | Notes |
|-------|-------|
| `naive_baseline` | Always predicts training-set class priors. Floor to beat. |
| `logistic_baseline` | Multinomial logistic regression with median imputation + scaling. |
| `gradient_boost` | `HistGradientBoostingClassifier` (or LightGBM if installed). Native NaN handling. |

## Artifacts

Artifacts are saved under `ml/artifacts/{run_id}/`:

```
ml/artifacts/
└── 20240501_143022/          ← run_id (timestamp)
    ├── naive_baseline.pkl
    ├── logistic_baseline.pkl
    ├── gradient_boost.pkl
    ├── feature_cols.json      ← ordered feature list
    ├── feature_importance.csv ← for gradient_boost
    ├── cv_results.json        ← walk-forward CV metrics
    ├── validation_metrics.json
    ├── holdout_metrics.json   ← written by evaluate.py
    └── run_meta.json
```

## Predict Upcoming Fixtures

Create a CSV with upcoming matches:

```csv
match_date,home_team,away_team
2025-05-10,Arsenal,Chelsea
2025-05-10,Liverpool,Manchester City
```

Team names must match the canonical names in `DATA_CONTRACT.md`
(e.g., `Manchester City`, `Nott'ham Forest`, `Newcastle Utd`).

```bash
python -m ml.pipeline.predict --fixtures upcoming.csv --output predictions.csv
```

Output:
```
match_date   home_team         away_team           prob_H  prob_D  prob_A  predicted
2025-05-10   Arsenal           Chelsea             0.4521  0.2610  0.2869  H
2025-05-10   Liverpool         Manchester City     0.3890  0.2714  0.3396  H
```

## Evaluation Metrics

- **Accuracy** — fraction of correct outcome predictions
- **Log loss** — proper scoring rule; penalizes overconfident wrong predictions
- **Brier score** — quadratic scoring rule per class (H/D/A)
- **Calibration MAE** — how closely predicted probabilities match empirical frequencies

Typical baselines for EPL:
| Model | Accuracy | Log Loss |
|-------|----------|----------|
| Naive (home-win always) | ~0.46 | ~1.0 |
| Logistic regression | ~0.53 | ~0.95 |
| Gradient boosting | ~0.55 | ~0.91 |
| Betting market implied | ~0.58 | ~0.86 |

## Running Tests

```bash
# All tests
python -m pytest ml/tests/ -v

# Only leakage tests
python -m pytest ml/tests/test_features.py::TestNoLeakage -v

# Only data contract tests
python -m pytest ml/tests/test_validation.py -v
```

## Next Improvements

Prioritized by expected lift:

1. **Hyperparameter tuning** — Optuna on walk-forward CV; ~+1% accuracy
2. **xG coverage** — FBRef xG is available for all seasons in raw/; enrich 2023-24+
3. **Draw specialization** — draws are the hardest class (recall=0); dedicated binary classifier
4. **Player availability** — key players injured/suspended; requires manual data
5. **Ensemble** — blend logistic + boosting probabilities; ~+0.5% accuracy
6. **Betting market features** — closing odds are strong priors (if available)
