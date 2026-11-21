# Penalty Label Spec (PEN-02)

Dataset: `data-pipeline/data/static/penalties/penalty_kicks_v0.csv` (tracked,
~520 rows). Builder: `data-pipeline/scripts/penalties/01_build_penalty_csv.py`.
Audit: `docs/PENALTY_DATA_AUDIT.md`.

**Grain:** one row per penalty kick, in-game or shootout. A retaken kick
appears once per recorded attempt.

## Timing classes

Every column is exactly one of:

- **id / meta** — identifies the kick; never a feature.
- **pre-kick** — known before the taker starts the run-up. The only columns a
  predictor may use.
- **post-kick** — known only once the ball is struck or the kick resolves:
  placement, outcome, keeper action. Labels and descriptive slices only.
  `ml/models/penalty_baselines.py:POSTKICK_COLUMNS` is the machine-checked list.

## Columns

| Column | Type | Timing | Notes |
|---|---|---|---|
| kick_id | string | id | StatsBomb shot event UUID |
| source | string | meta | `statsbomb_open` for every v0 row. Future sources get their own value. |
| competition_id, season_id | string | meta | As in the shot contract |
| competition_gender | string | pre-kick | `male` / `female` (feature as `is_womens`) |
| tournament_start_date | date | split key | Splits use this column |
| match_id, match_date | string, date | meta | `match_id` = `{yyyymmdd}_{home}_{away}` |
| team_id, opponent_id | string | meta | FIFA codes of the kicking and defending teams |
| taker_id, taker_name | string | id | |
| keeper_id, keeper_name | string | id | Defending keeper |
| phase | string | pre-kick | `in_game` / `shootout` |
| period, minute | int | pre-kick | Shootout kicks have `period = 5` |
| taker_foot | string | pre-kick | `right` / `left` (kicking foot) |
| team_score_before, opp_score_before | int | pre-kick | Match score before the kick (in-game) or shootout score before the kick (shootout) |
| game_state | string | pre-kick | `leading` / `level` / `trailing` from the two score columns |
| shootout_kick_number | int | pre-kick | 1-based order across both teams; null in-game |
| shootout_round, team_kick_number | int | pre-kick | The kicking team's 1-based kick number; null in-game |
| team_kicked_first | bool | pre-kick | Kicking team took the shootout's first kick |
| shootout_pressure | string | pre-kick | See below; null in-game |
| outcome | string | post-kick | `goal`, `saved`, `post`, `off_target` |
| is_goal | bool | **label** | |
| end_y, end_z | float | post-kick | Ball end location (yards). For saves, where the keeper stopped it |
| on_target | bool | post-kick | Inside the posts and under the bar |
| placement_col, placement_row, placement_zone | string | post-kick | 3×3 grid, below |
| foot_side | string | post-kick | `natural` / `across` / `center`, below |
| keeper_technique | string | post-kick | `diving` / `standing` / `none_recorded` |
| keeper_set | string | post-kick | `set` / `moving` as recorded at the kick |

## Placement zones (3×3)

From the **taker's view**, facing the goal (StatsBomb `y` grows to the taker's
right, so smaller `y` is the taker's left).

- Columns split the 8-yard goal into thirds: `left` y < 38.67, `center`
  38.67–41.33, `right` y > 41.33.
- Rows split the 2.67-yard height into thirds: `low` z < 0.89, `mid`
  0.89–1.78, `high` z ≥ 1.78.
- `placement_zone = {row}_{col}`, e.g. `low_left`.
- Misses map to the nearest edge zone: wide of the left post → `*_left`, over
  the bar → `high_*`. `on_target` separates them, so "kicks aimed low left"
  includes the ones that went wide low left.

## Foot × side

- `natural`: right-footer to the left third, left-footer to the right third
  (the open-body placement).
- `across`: the opposite third.
- `center`: middle third.

## Shootout pressure

Computed from the shootout state before the kick (best of five, then sudden
death):

- `must_score`: a miss ends the shootout as a loss.
- `can_win`: a goal ends the shootout as a win.
- `neutral`: neither. Includes the first kicker of a sudden-death round.

## Splits

Chronological by `tournament_start_date`. Rolling origin: each tournament is
scored by models trained only on tournaments that started before it. Fixed
holdout: tournaments starting on/after `PENALTY_EVAL_START_DATE` (2024-06-01:
Euro 2024, Copa América 2024, Women's Euro 2025).

---

## `penalty_aggregates.json` schema

Path: `ml/exports/penalty_aggregates.json` (tracked) and
`ml/artifacts/penalties_{ts}/penalty_aggregates.json`. Written by
`python -m ml.pipeline.evaluate_penalties`. All rates are goals / kicks with
Wilson 95% intervals.

```jsonc
{
  "schema_version": 1,
  "generated": "2026-11-21",
  "run_id": "penalties_…",
  "label": "Experimental. Descriptive conversion rates from past tournament kicks, not a prediction.",
  "source": "StatsBomb open data (international tournaments)",
  "perspective": "Zones are from the taker's view: 'left' is the taker's left.",
  "min_display_n": 20,                       // groups below this have low_sample: true
  "default_scope": "mens",
  "scopes": {
    "mens": <Scope>,                         // 356 kicks
    "all":  <Scope>                          // 520 kicks, men's + women's
  },
  "model_check": {
    "question": "…",
    "constant_log_loss": 0.62458,
    "best_other": ["phase_rate", 0.62387],
    "any_beats_constant": false,             // pre-kick facts do not predict conversion
    "n_scored_kicks": 362
  }
}
```

`<Scope>`:

```jsonc
{
  "n_kicks": 356,
  "overall": { "n": 356, "goals": 247, "conversion": 0.6938, "ci95": [0.6441, 0.7394] },
  "by_phase": [<Group>],                     // phase
  "zones": {
    "rows": ["high", "mid", "low"],          // top to bottom
    "cols": ["left", "center", "right"],     // taker's view
    "perspective": "taker",
    "cells": [[<Cell>, <Cell>, <Cell>], …]   // cells[row_index][col_index]
  },
  "on_target_rate": 0.927,
  "save_rate_on_target": 0.2182,
  "by_foot": [<Group>],                      // taker_foot
  "foot_x_side": [<Group>],                  // taker_foot, foot_side
  "foot_x_col": [<Group>],                   // taker_foot, placement_col
  "shootout_order": [<Group>],               // order_bucket: "1".."5", "6+"
  "shootout_pressure": [<Group>],            // shootout_pressure
  "in_game_state": [<Group>],                // game_state
  "shootouts": { "n_shootouts": 25, "first_kicker_won": 12, "first_kicker_win_rate": 0.48, "ci95": [0.30, 0.67] }
}
```

`<Group>`: the grouping columns as keys (e.g. `"taker_foot": "right"`), plus
`n`, `goals`, `conversion`, `ci95`, `share` (fraction of kicks in the scope),
`low_sample`.

`<Cell>`: `zone`, `row`, `col`, `n`, `share`, `goals`, `saved`, `missed`
(post + off target), `conversion` (null when `n = 0`), `ci95`, `low_sample`.

Keeper action is deliberately absent; see `PENALTY_DATA_AUDIT.md`.
