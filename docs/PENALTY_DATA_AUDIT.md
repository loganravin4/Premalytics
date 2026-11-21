# Penalty Data Audit (PEN-01)

Source: StatsBomb open data, every senior international tournament in the
registry (`data-pipeline/soccer/statsbomb_open.py`). Built by
`data-pipeline/scripts/penalties/01_build_penalty_csv.py`; the numbers below are
from `python -m ml.pipeline.evaluate_penalties` (`penalty_metrics.json` →
`audit`).

## What a penalty looks like in the events

- Every kick, in-game or shootout, is a `Shot` event with `shot.type == Penalty`.
  Shootout kicks are in `period == 5`.
- `shot.end_location` is `[x, y, z]` in yards: `y` across the goal mouth
  (posts at 36 and 44), `z` height (crossbar at 2.67). For saved kicks it is
  where the keeper stopped the ball, close to but not exactly the aimed spot.
- `shot.body_part` gives the kicking foot. Preferred foot is not in the data.
- The opposing keeper's `Goal Keeper` event (linked via `related_events`) has
  `type` (Penalty Saved / Penalty Conceded / Shot Faced), `technique`
  (Diving / Standing), `position` (Set / Moving), and the body part used on a
  save. **There is no dive-direction field.**
- Score state before each kick is rebuilt from earlier events (goals and
  `Own Goal For`), and shootout state from earlier period-5 kicks.

## Kick counts

| Tournament | Start | Gender | In-game | Shootout | Total |
|---|---|---|---|---|---|
| WC 1974 | 1974-06-19 | men | 2 | 0 | 2 |
| WC 2018 | 2018-06-14 | men | 29 | 39 | 68 |
| Women's WC 2019 | 2019-06-07 | women | 26 | 7 | 33 |
| Euro 2020 | 2021-06-11 | men | 17 | 38 | 55 |
| Women's Euro 2022 | 2022-07-06 | women | 10 | 0 | 10 |
| WC 2022 | 2022-11-20 | men | 23 | 41 | 64 |
| Women's WC 2023 | 2023-07-20 | women | 27 | 43 | 70 |
| AFCON 2023 | 2024-01-13 | men | 22 | 60 | 82 |
| Euro 2024 | 2024-06-14 | men | 12 | 24 | 36 |
| Copa América 2024 | 2024-06-21 | men | 10 | 39 | 49 |
| Women's Euro 2025 | 2025-07-02 | women | 14 | 37 | 51 |
| **Total** | | | **192** | **328** | **520** |

Men's: 356 kicks (115 in-game, 241 shootout). Women's: 164 (77 in-game, 87
shootout). 32 shootouts (25 men's, 7 women's). The other historic WC matches
(1958, 1962, 1970, 1986, 1990) contain no penalties.

Outcomes: 354 goals (68.1%), 107 saved (including 3 saved onto the post),
30 hit the woodwork, 29 off target.

## Field coverage

| Field | Coverage | Notes |
|---|---|---|
| End location y (horizontal placement) | 100% | |
| End location z (height) | 100% | |
| 3×3 placement zone | 100% | Misses map to the nearest edge zone; `on_target` flags them |
| Taker foot (left/right) | 100% | Kicking foot, not preferred foot |
| Keeper identity | 100% | From the keeper event or the freeze frame |
| Keeper action (diving/standing) | 81.5% | diving 381, standing 43, none recorded 96. Missing mostly on misses (`Shot Faced`), so it is tied to the outcome |
| Keeper dive direction | 0% | Not in the data |
| Taker penalty history | — | Only these tournaments; too sparse per player |

## Go / no-go

| Use | Verdict | Why |
|---|---|---|
| Conversion by 3×3 zone (descriptive) | **Go** | 100% placement coverage; zones with < 20 kicks are flagged `low_sample` (the three center zones for men's) |
| Foot × side, shootout order, pressure, game state (descriptive) | **Go** | Full coverage; groups have 14–272 kicks, all with Wilson intervals |
| In-game vs shootout comparison | **Go** | 192 vs 328 kicks |
| Keeper dive direction or "which way to dive" | **No-go** | No dive-direction field; keeper action is recorded mostly when the keeper touches the ball |
| Keeper-action conversion on the site | **No-go** | `none_recorded` is mostly misses and `standing` mostly center goals, so the rate restates the outcome |
| Taker or keeper skill ratings | **No-go** | 1–6 kicks per player |
| Pre-kick GBM | **Try, ship only if it beats the baseline** | 520 labeled kicks clears the ~200 bar in the roadmap. PEN-03 ran it: it did **not** beat the constant rate (`PENALTY_LIMITATIONS.md`), so it is not shipped |

Bottom line: the data supports an honest descriptive penalties page (where
kicks go and how often each zone scores). It does not support predicting
individual kicks, keepers' dives, or shootout winners.
