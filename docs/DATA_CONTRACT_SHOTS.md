# Premalytics Shot-Level Data Contract (Track 2 — xG)

Canonical schema for **shot-level** events used to train the shot xG model
(XG-01 → XG-04). This is a **separate table** from the match contract
(`DATA_CONTRACT.md`); one row per shot.

## File location

```
data-pipeline/data/raw/shots/wc_shots_{season_id}.csv
```

Produced by `data-pipeline/scripts/shots/01_export_statsbomb_shots.py` from
StatsBomb open data (https://github.com/statsbomb/open-data).

**Grain:** one row per shot attempt.

---

## Schema

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| shot_id | string | No | Unique per shot (StatsBomb event UUID) |
| match_id | string | No | Joins to match contract: `{yyyymmdd}_{home}_{away}` (lowercase FIFA codes) |
| competition_id | string | No | e.g. `fifa_world_cup` |
| season_id | string | No | Tournament year, e.g. `2022` |
| match_date | date | No | `YYYY-MM-DD` |
| team_id | string | No | FIFA 3-letter code of the shooting team |
| player_id | string | No | Provider (StatsBomb) player id |
| player_name | string | No | Display name |
| position | string | No | `GK`, `CB`, `LB`, `RB`, `CDM`, `CM`, `CAM`, `LM`, `RM`, `LW`, `RW`, `ST` (etc.) |
| minute | int | No | Match minute |
| distance_m | float | No | Distance from goal centre in metres |
| angle_deg | float | No | Angle to goal in degrees (0 = central, 90 = wide) |
| body_part | string | No | `right_foot`, `left_foot`, `head` |
| situation | string | No | `open_play`, `set_piece`, `counter`, `penalty` |
| is_goal | bool | No | **Label** |
| is_penalty | bool | No | Exclude from xG model training (kept for provenance) |
| under_pressure | bool | Yes | Defender within ~1 m at time of shot |
| assist_type | string | Yes | `pass`, `cross`, `through_ball`, `none` |

### Allowed feature columns

Everything except `shot_id`, `match_id`, `player_id`, `player_name`,
`is_goal` (the label), and `is_penalty` (a filter flag) may be used as a
model input — subject to the leakage rule below. All inputs are known **at
the moment the shot is taken**.

---

## FORBIDDEN COLUMNS (post-shot leakage — never use as a feature)

Any value only knowable **after the shot resolves** must never be a model
feature. These describe the outcome, not the chance:

- **keeper dive direction** — only known once the keeper reacts to the shot
- **rebound outcome** / follow-up shot result — downstream of this shot
- **post/bar hit indicator** — *as a feature*. It may exist as metadata for
  analysis, but it encodes where the ball ended up, so it leaks the outcome
- **VAR outcome** / goal-disallowed flags — adjudicated after the event
- **shot end_location / `statsbomb_xg`** — end_location is post-strike ball
  placement; the provider's own xG is a model output, not an input
- **shot outcome name** (Goal / Saved / Off T / Post / Blocked) other than
  the binary `is_goal` label

Rule of thumb: if you could only fill the column in *after* watching the
ball leave the foot, it is forbidden as a feature.

---

## Provenance & conversions

- **Source:** StatsBomb open data, competition 43 (FIFA World Cup),
  seasons 3 (WC 2018) and 106 (WC 2022).
- **Pitch:** StatsBomb uses a 120×80 yard pitch; goal centre at `[120, 40]`.
  - `dx = 120 - x`, `dy = 40 - y` (yards)
  - `distance_m = sqrt(dx² + dy²) × 0.9144`
  - `angle_deg = degrees(atan2(|dy|, dx))` → 0° straight on, 90° from the byline
- **situation** is derived from StatsBomb `shot.type` and `play_pattern`:
  `Penalty → penalty`; play pattern `From Counter → counter`; a direct
  `Free Kick`/`Corner` shot type or play pattern `From Corner`/`From Free
  Kick → set_piece`; everything else (including `From Throw In`,
  `From Goal Kick`, `From Keeper`, regular play) → `open_play`.
- **assist_type** is resolved from the key-pass event referenced by
  `shot.key_pass_id`: `cross` if `pass.cross`, `through_ball` if the pass
  technique is Through Ball, else `pass`; `none` when there is no key pass.
- **Excluded at ingest:** penalties (`shot.type == Penalty`), own goals
  (not StatsBomb `Shot` events), and any shot missing an outcome.
