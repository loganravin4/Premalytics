# Penalty Model Limitations (PEN-03)

What the penalties work can and cannot claim. Read before putting any penalty
number on the site. `WC_SPEC.md` rule: no high-confidence penalty "predictions".

## Before and after

**Before PEN-01 → PEN-03:** no penalty dataset, no baseline, no model.

**After:** 520 labeled kicks (356 men's), descriptive aggregates for the
frontend, and a measured answer to "can pre-kick facts predict conversion?"
The answer is **no**.

### Pre-kick predictors, rolling origin

Each tournament scored by models trained only on earlier tournaments (scoring
starts once 120 training kicks exist). 362 kicks scored across AFCON 2023,
Copa América 2024, WC 2022, Euro 2024, Women's Euro 2022, Women's Euro 2025,
and Women's WC 2023. Inputs: phase, taker foot, shootout order, shootout
pressure / game state, gender.

| Predictor | Brier | Log loss | Δ LL vs constant (95% CI) |
|---|---|---|---|
| constant (training conversion rate) | 0.2164 | 0.6246 | — |
| phase_rate (in-game vs shootout, shrunk) | 0.2161 | 0.6239 | −0.0007 (−0.0063, +0.0043) |
| pressure_rate (phase × pressure/game state, shrunk) | 0.2175 | 0.6269 | +0.0024 (−0.0061, +0.0109) |
| logistic_prekick (L2) | 0.2196 | 0.6319 | +0.0073 (−0.0022, +0.0163) |
| gbm_prekick (depth 2) | 0.2196 | 0.6325 | +0.0079 (−0.0052, +0.0203) |

Fixed holdout (train on 384 kicks before 2024-06-01, score 136 kicks from
Euro 2024, Copa América 2024, Women's Euro 2025): constant LL 0.6540,
phase_rate 0.6542, pressure_rate 0.6548, logistic 0.6645, GBM 0.6823.

Nothing beats the constant rate; every interval spans zero, and the flexible
models are worse. **The GBM is not shipped** (`penalty_metrics.json` →
`gbm_decision.ships = false`). The site should present a single base rate
(men's 69.4%, 95% CI 64.4–73.9%) and descriptive slices, never a per-kick
probability.

## What the descriptive numbers say (men's, 356 kicks)

- Placement: 27% of kicks go low left (taker's view), 19% low right; center
  zones hold 12% combined. 92.7% of kicks are on target; keepers save 21.8% of
  those.
- The six side zones convert at 64–81%. The center column swings from 30%
  (high center, 10 kicks, mostly over the bar) to 93% (low center, 15 kicks),
  but those cells have 10–18 kicks each (flagged `low_sample`), and most
  intervals overlap.
- Shootout vs in-game: 68.5% vs 71.3%, intervals overlap.
- Shootout pressure: `must_score` 70.8% (24 kicks), `can_win` 81.8% (22),
  `neutral` 66.7% (195). Intervals overlap; there is no measurable choke or
  clutch effect at this sample size.
- Team kicking first won 12 of 25 men's shootouts (48%, CI 30–67%).

## Limitations

1. **Placement is post-kick.** Conversion by zone describes where kicks that
   scored went. It is not advice on where to shoot and not a prediction for a
   future kick. Takers choose zones knowing their own skill and the keeper,
   so the zone rates are confounded by who shoots where.
2. **Saved kicks' end location is the keeper's touch point**, not the aim
   point. Low saves near the keeper's start position can shift a kick toward
   the center column.
3. **No dive direction.** StatsBomb open events do not record which way the
   keeper went, so "keeper guessed right" analysis is impossible.
4. **Keeper action is tied to the outcome.** No action is recorded on most
   misses, and "standing" mostly appears on center goals. That column is kept
   out of the frontend aggregates and out of every predictor.
5. **Small samples.** 356 men's kicks, 25 men's shootouts. Groups under 20
   kicks are flagged; any difference smaller than about ±10 points is within
   noise.
6. **Kicking foot, not preferred foot.** `natural` vs `across` uses the foot
   that struck the ball. A two-footed taker using a weaker foot is unusual but
   not identified.
7. **Selection.** Only tournaments StatsBomb released: mostly major
   tournaments from 2018 onward. Not qualifiers, not friendlies, and not club
   football.
8. **Women's kicks** (164) are in the `all` scope. Women's shootout conversion
   is lower (61% vs 68%) on 87 kicks; the men's scope is the default.
9. **Shootout format.** Pressure assumes best-of-five then sudden death with
   alternating kicks (true for every shootout in the data).

## Allowed copy on the site

- "Of 356 penalties at recent men's tournaments, 69% were scored."
- "Kicks aimed low to the taker's left were the most common (27%)."
- "Experimental. Descriptive rates from past tournaments, not a prediction."

Not allowed: "X will score", "the keeper should dive left", shootout win
probabilities, or zone rates shown without their sample size.
