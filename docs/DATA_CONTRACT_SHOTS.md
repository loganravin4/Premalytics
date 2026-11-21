# Shot-Level Data Contract (Track 2, xG)

Canonical schema for **shot-level** events used to train the shot xG model
(XG-01 → XG-07). This is a **separate table** from the match contract
(`DATA_CONTRACT.md`); one row per non-penalty shot.

Model card, metrics, and the `xg_grid.json` schema: `docs/XG_MODEL.md`.

## File location

```
data-pipeline/data/raw/shots/{slug}_shots_{season_id}.csv
```

`slug` is `wc`, `euro`, `copa`, `afcon`, `wwc` (Women's World Cup) or `weuro`
(Women's Euro), so the WC files keep their old names (`wc_shots_2018.csv`,
`wc_shots_2022.csv`) and `data-pipeline/scripts/06_backfill_xg.py` still finds
them.

Produced by `data-pipeline/scripts/shots/01_export_statsbomb_shots.py` from
StatsBomb open data (https://github.com/statsbomb/open-data). Raw event JSON is
cached as gzip in `data-pipeline/data/raw/statsbomb_cache/` by
`data-pipeline/soccer/statsbomb_open.py`, which the penalty builder shares.

**Grain:** one row per shot attempt. Penalties (in-game and shootout) are not
in this table; they live in the penalty dataset (`docs/PENALTY_LABEL_SPEC.md`).

## Competitions

Every senior international competition in the open data. Youth (FIFA U20 World
Cup 1979) is skipped.

| competition_id | Seasons | StatsBomb ids (competition/season) | Gender |
|---|---|---|---|
| `fifa_world_cup` | 2018, 2022 | 43/3, 43/106 | male |
| `fifa_world_cup` | 1958, 1962, 1970, 1974, 1986, 1990 (1–6 matches each) | 43/269, 270, 272, 51, 54, 55 | male |
| `uefa_euro` | 2020, 2024 | 55/43, 55/282 | male |
| `copa_america` | 2024 | 223/282 | male |
| `afcon` | 2023 | 1267/107 | male |
| `womens_world_cup` | 2019, 2023 | 72/30, 72/107 | female |
| `womens_euro` | 2022, 2025 | 53/106, 53/315 | female |

---

## Schema

| Column | Type | Nullable | Timing | Notes |
|--------|------|----------|--------|-------|
| shot_id | string | No | id | StatsBomb event UUID |
| match_id | string | No | id | `{yyyymmdd}_{home}_{away}` (lowercase FIFA codes) |
| competition_id | string | No | meta | See table above |
| season_id | string | No | meta | Tournament year label, e.g. `2022` (Euro 2020 = `2020`) |
| competition_gender | string | No | feature (as `is_womens`) | `male` / `female` |
| tournament_start_date | date | No | split key | First match date of the tournament. **Splits use this column.** |
| match_date | date | No | meta | `YYYY-MM-DD` |
| team_id | string | No | meta | FIFA 3-letter code of the shooting team |
| player_id | string | No | id | StatsBomb player id |
| player_name | string | No | id | Display name |
| position | string | No | meta | `GK`, `CB`, `LB`, `RB`, `CDM`, `CM`, `CAM`, `LM`, `RM`, `LW`, `RW`, `ST` (etc.) |
| period | int | No | meta | 1–4 (shootouts are excluded) |
| minute | int | No | meta | Match minute |
| shot_x, shot_y | float | No | at release | StatsBomb yards, attacking toward x=120 |
| distance_m | float | No | at release | Distance from goal center, meters |
| angle_deg | float | No | at release | 0 = central, 90 = from the byline |
| body_part | string | No | at release | `right_foot`, `left_foot`, `head`, `other` (`other` dropped at training) |
| technique | string | No | at release | `normal`, `volley`, `half_volley`, `lob`, `backheel`, `diving_header`, `overhead_kick` |
| situation | string | No | at release | `open_play`, `set_piece`, `counter` |
| first_time | bool | No | at release | Struck without a controlling touch |
| under_pressure | bool | No | at release | StatsBomb pressure flag on the shot event |
| assist_type | string | No | at release | `cut_back`, `cross`, `through_ball`, `pass`, `none` (key pass type, checked in that order) |
| ff_available | bool | No | at release | Freeze frame present (100% in the current data) |
| n_def_in_cone | int | Yes | at release | Opponent outfield players inside the triangle shooter → both posts |
| nearest_def_m | float | Yes | at release | Distance from the shooter to the nearest opponent outfield player, meters |
| gk_dist_to_goal_m | float | Yes | at release | Keeper distance from goal center, meters (null if no keeper in frame) |
| gk_dist_to_shooter_m | float | Yes | at release | Keeper distance from the shooter, meters |
| gk_angle_offset_deg | float | Yes | at release | Angle between shooter→goal center and shooter→keeper; 0 = keeper square on the shot line |
| is_goal | bool | No | **label** | Shot outcome is Goal |
| is_penalty | bool | No | filter | Always `False` here (penalties excluded at ingest) |
| sb_xg_benchmark | float | No | **post-model, forbidden** | StatsBomb's own xG. Benchmark only. |

Freeze-frame columns come from the shot's freeze frame: the positions of the
visible players at the moment the ball is struck. That is the release moment,
not later, so they are allowed. When a frame or its keeper is missing the
column is null and the model imputes it (`ff_available` flags the gap).

### Allowed feature columns

Every column marked **at release**, plus `competition_gender` (as the derived
`is_womens`). Derived in `ml/models/shot_xg.py:add_derived_features`:
`log_distance = log(1 + distance_m)`, `is_womens`.

Never features: `shot_id`, `match_id`, `player_id`, `player_name` (ids),
`is_goal` (label), `is_penalty` (filter), `sb_xg_benchmark` (another model's
output), and the split/meta columns.

---

## FORBIDDEN COLUMNS (post-shot leakage — never use as a feature)

Any value only knowable **after the shot resolves** must never be a model
feature. These describe the outcome, not the chance:

- **keeper dive direction** / keeper save technique — only known once the keeper reacts
- **rebound outcome** / follow-up shot result — downstream of this shot
- **post/bar hit indicator** — encodes where the ball ended up
- **VAR outcome** / goal-disallowed flags — adjudicated after the event
- **shot end_location** — post-strike ball placement
- **`statsbomb_xg` / `sb_xg_benchmark`** — the provider's xG is a model output; it
  is stored only to benchmark our model on the same shots
- **shot outcome name** (Goal / Saved / Off T / Post / Blocked) other than
  the binary `is_goal` label

Rule of thumb: if you could only fill the column in *after* watching the
ball leave the foot, it is forbidden as a feature.

`ml/models/shot_xg.py:FORBIDDEN_FEATURES` is the machine-checked list;
`ml/tests/test_shot_xg.py::TestNoForbiddenColumns` fails if any model feature
set contains one of them or a column outside this contract.

---

## Provenance & conversions

- **Pitch:** StatsBomb 120×80 yard pitch; goal center at `[120, 40]`, posts at
  y=36 and y=44. Shots always attack toward x=120.
  - `dx = 120 - x`, `dy = 40 - y` (yards)
  - `distance_m = sqrt(dx² + dy²) × 0.9144`
  - `angle_deg = degrees(atan2(|dy|, dx))` → 0° straight on, 90° from the byline
- **situation** is derived from StatsBomb `shot.type` and `play_pattern`:
  play pattern `From Counter → counter`; a direct `Free Kick`/`Corner` shot type
  or play pattern `From Corner`/`From Free Kick → set_piece`; everything else
  (including `From Throw In`, `From Goal Kick`, `From Keeper`, regular play) →
  `open_play`.
- **assist_type** is resolved from the key-pass event referenced by
  `shot.key_pass_id`: `cut_back` if `pass.cut_back`, else `cross` if
  `pass.cross`, else `through_ball` if the pass technique is Through Ball, else
  `pass`; `none` when there is no key pass.
- **Shooting cone:** the triangle with vertices at the shot location and both
  posts. The keeper is counted separately (keeper columns), never in
  `n_def_in_cone`.
- **Team names:** women's suffixes (`England Women's`, `Wales W`, `WNT Finland`)
  are stripped before mapping to FIFA codes; unmapped historic teams
  (Czechoslovakia, German DR) fall back to a 3-letter slug.
- **Excluded at ingest:** penalties (`shot.type == Penalty`) and every period-5
  (shootout) kick, own goals (not StatsBomb `Shot` events), and any shot missing
  an outcome or location.

## Split

Splits are by **tournament start date** (`ml/config.py` `SHOT_*` keys), so a
tournament is never divided between train and eval:

| Role | Rule | Tournaments |
|---|---|---|
| train | `tournament_start_date < 2024-06-01` | WC 1958–1990 matches, WC 2018, WWC 2019, Euro 2020, WEuro 2022, WC 2022, WWC 2023, AFCON 2023 |
| validation (inside train; model selection only) | `2023-07-01 ≤ start < 2024-06-01` | WWC 2023, AFCON 2023 |
| eval | `tournament_start_date ≥ 2024-06-01` | Euro 2024, Copa América 2024 (headline, men's), WEuro 2025 (reported separately) |
