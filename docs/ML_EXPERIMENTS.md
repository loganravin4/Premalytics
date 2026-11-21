# Match model experiments (ML-01 → ML-05)

Last updated: 2026-11-21. Backtest run `ml/artifacts/backtest_20261121_144436/`
(`python -m ml.pipeline.backtest`, 509 s). WC 2026 evaluation
`data-pipeline/data/evaluation/wc2026/20261121_144554/`.

## TL;DR

1. **The shipped WC 2026 retrospective leaked.** `predict.py` built every fixture's
   features from each team's *last* row in `features.joblib`, which ran through
   2026-07-19. Argentina was priced with its pre-final Elo (2101) for every
   match instead of its pre-tournament Elo (2017). The shipped 69.2% / 0.681 was
   not a pre-tournament forecast. Fixed: `predict.py` never reads rows on or
   after a fixture's date, and `--as-of` freezes form at a date. The honest
   number for the shipped model is **67.3% / 0.764 credited, 66.3% / 0.861 raw**.
2. **The 123-feature GBM does not beat a 2-feature Elo logistic.** Over 1,150
   tournament matches the gap is 0.0003 RPS (95% CI −0.0024 to +0.0029). The GBM
   has the better RPS in only 10 of 27 tournaments.
3. **Dixon-Coles beats both.** On its own it improves pooled RPS by 0.0046 and
   log loss by 0.019 over the GBM, and both CIs exclude zero. The best model is a
   walk-forward-fit blend: 0.2 × GBM + 0.8 × Dixon-Coles, then temperature
   T = 0.90. It is the new served model (`ensemble.json` in the run directory).
4. **Draws are still not called.** Draw recall at argmax stays near 0 for every
   calibrated model, because a draw is almost never the single most likely
   outcome. What improved is how *well priced* draws are: on the backtest,
   mean predicted draw probability is 25.0% for the blend vs 24.5% for the GBM,
   against 26.2% actual. The threshold draw rule adds nothing once it is tuned
   walk-forward (−0.0006 log loss).
5. **On WC 2026 the new model gives better probabilities but one fewer correct
   pick.** Raw log loss 0.861 → 0.815 and RPS 0.162 → 0.150. Accuracy 66.3% →
   65.4%. Quote RPS and log loss, not accuracy.

## Method

* **Folds (ML-01).** One fold per tournament edition for WC, Euro, Copa América,
  AFCON, Asian Cup, and Gold Cup. An edition is a run of a competition's matches
  with no gap over 90 days (season ids are unreliable: Euro 2020 spans 2020/2021
  and AFCON 2025 spans 2025/2026). Each fold trains on every match strictly
  before the tournament's first match and scores the whole tournament.
  Twenty-seven tournaments from 2014 to 2026 are reported, 1,150 matches.
  Nine 2010–2013 tournaments are warm-up folds: they are scored only so that
  post-processing has out-of-sample data. In-tournament features use earlier
  rounds of the same tournament (normal pre-match features). The model itself
  stays frozen at the tournament start.
* **Nested post-processing (ML-04/05).** The blend weight, temperature,
  draw bias, and threshold draw rule for a fold are fit only on the
  out-of-sample predictions of folds that **ended before that fold started**.
  The WC 2026 fold's parameters come from 35 earlier tournaments (1,336 matches)
  and never see WC 2026.
* **Metrics (ML-02).** RPS (primary), log loss, multi-class Brier, accuracy,
  draw recall, per-class decile reliability, and ECE. Raw and shootout-credited
  values are always reported together. Raw means a shootout counts as a draw.
  Credited means the draw mass of knockout matches moves to the two teams in
  proportion to their win probabilities, and shootouts are scored for the team
  that advanced. In the backtest a knockout is either an FBref knockout stage
  label or a match in martj42 `shootouts.csv`. martj42 rows label every
  tournament match `group` (stage-inference ticket, not fixed here), so
  credited backtest numbers only adjust shootout matches and FBref knockouts.
* **Dixon-Coles.** Team attack and defense, home advantage (non-neutral only),
  and the low-score ρ term. Fit by weighted maximum likelihood with
  exp(−ξ·days) decay × `TOURNAMENT_WEIGHTS`, an L2 ridge, and a 12-year window.
  ξ = 0.0005/day (≈3.8-year half-life) and ridge 0.1 were picked on the
  2010–2013 warm-up folds only. Fitted ρ ≈ −0.054, so 0-0 and 1-1 are slightly
  more likely than under independence.
* **Baselines (ML-03).** Elo logistic (`diff_elo` plus a neutral-venue flag),
  "favorite always" (higher Elo; probabilities are the training-set
  favorite/draw/underdog rates), class priors, and the shipped 123-feature
  balanced logistic.
  * **FIFA-rank baseline: skipped.** The repo has no FIFA ranking data.
  * **Market baseline: skipped.** No free closing-odds source covers
    international matches. Football-Data.co.uk is club leagues only. The
    BeatTheBookie dump ends in 2015 and is club-focused. Everything else is a
    paid scraper or would mean scraping OddsPortal against its terms.

## Results: pooled backtest (27 tournaments, 2014–2026)

Sorted by RPS. Lower is better except accuracy and draw recall. ECE is the mean
per-class expected calibration error over 10 bins.

| model | n | RPS | LL raw | LL credited | Brier | acc | draw recall | ECE |
|---|---|---|---|---|---|---|---|---|
| **blend_temp (served)** | 1150 | **0.1802** | 0.9283 | 0.8754 | 0.5512 | 0.572 | 0.007 | 0.0308 |
| blend_drawbias | 1150 | 0.1802 | 0.9285 | 0.8753 | 0.5514 | 0.573 | 0.010 | 0.0299 |
| elo_dc_blend | 1150 | 0.1802 | 0.9278 | 0.8739 | 0.5508 | 0.567 | 0.003 | 0.0288 |
| dixon_coles | 1150 | 0.1804 | 0.9281 | 0.8759 | 0.5510 | 0.570 | 0.043 | 0.0357 |
| blend (no temperature) | 1150 | 0.1805 | 0.9292 | 0.8763 | 0.5516 | 0.572 | 0.007 | 0.0323 |
| gbm_raw (no isotonic) | 1150 | 0.1849 | 0.9460 | 0.8903 | 0.5628 | 0.567 | 0.007 | 0.0296 |
| gbm_drawcal_wf | 1150 | 0.1850 | 0.9459 | 0.8929 | 0.5629 | 0.572 | 0.003 | 0.0225 |
| **gbm (shipped model)** | 1150 | 0.1850 | 0.9466 | 0.8920 | 0.5633 | 0.572 | 0.003 | 0.0304 |
| gbm_drawcal_shipped | 1150 | 0.1852 | 0.9473 | 0.8932 | 0.5637 | 0.572 | 0.003 | 0.0275 |
| gbm_raw_temp | 1150 | 0.1852 | 0.9474 | 0.8918 | 0.5635 | 0.567 | 0.007 | 0.0298 |
| elo_logistic | 1150 | 0.1854 | 0.9470 | 0.8882 | 0.5637 | 0.567 | 0.000 | 0.0348 |
| gbm_temp | 1150 | 0.1854 | 0.9477 | 0.8934 | 0.5638 | 0.572 | 0.003 | 0.0282 |
| gbm_drawbias | 1150 | 0.1854 | 0.9477 | 0.8938 | 0.5640 | 0.572 | 0.003 | 0.0280 |
| logistic_123 | 1150 | 0.1901 | 0.9848 | 0.9434 | 0.5838 | 0.511 | 0.299 | 0.0709 |
| favorite | 1150 | 0.1954 | 0.9821 | 0.9185 | 0.5846 | 0.564 | 0.000 | 0.0310 |
| priors | 1150 | 0.2287 | 1.0759 | 1.0139 | 0.6512 | 0.443 | 0.000 | 0.0289 |

Excluding WC 2026 (1,046 matches) gives the same ranking. The DC-based models
tie at RPS 0.1830–0.1833, the GBM is at 0.1875, and Elo logistic is at 0.1877.
The full table is in `summary.md`.

Paired bootstrap of the per-match difference (4,000 resamples, all 1,150 matches):

| comparison | ΔRPS (95% CI) | Δlog loss (95% CI) |
|---|---|---|
| Elo logistic − GBM | +0.0003 (−0.0024, +0.0029) | +0.0004 (−0.0097, +0.0104) |
| Dixon-Coles − GBM | −0.0046 (−0.0081, −0.0011) | −0.0185 (−0.0309, −0.0062) |
| blend_temp − GBM | −0.0049 (−0.0072, −0.0025) | −0.0183 (−0.0269, −0.0098) |
| blend_temp − Elo logistic | −0.0052 (−0.0082, −0.0022) | −0.0187 (−0.0296, −0.0079) |
| elo_dc_blend − GBM | −0.0048 (−0.0076, −0.0021) | −0.0187 (−0.0288, −0.0085) |

blend_temp has a lower RPS than the GBM in 20 of 27 tournaments.

Per tournament (RPS, best in bold):

| tournament | n | GBM | Elo logistic | Dixon-Coles | blend_temp |
|---|---|---|---|---|---|
| fifa_world_cup_2014 | 64 | **0.1948** | 0.2017 | 0.2082 | 0.2000 |
| afc_asian_cup_2015 | 32 | 0.1841 | 0.1775 | 0.1743 | **0.1699** |
| afcon_2015 | 32 | 0.2183 | 0.2177 | **0.2016** | 0.2104 |
| copa_america_2015 | 26 | 0.1967 | 0.2140 | **0.1845** | 0.1915 |
| concacaf_gold_cup_2015 | 26 | 0.2123 | 0.2120 | **0.1993** | 0.2099 |
| copa_america_2016 | 32 | 0.1783 | 0.1807 | 0.1731 | **0.1714** |
| uefa_euro_2016 | 51 | **0.2269** | 0.2379 | 0.2277 | 0.2293 |
| afcon_2017 | 32 | **0.1973** | 0.1986 | 0.2038 | 0.2010 |
| concacaf_gold_cup_2017 | 19 | 0.1552 | 0.1550 | **0.1401** | 0.1437 |
| fifa_world_cup_2018 | 64 | 0.2181 | 0.2162 | **0.2057** | 0.2083 |
| afc_asian_cup_2019 | 51 | 0.1691 | **0.1684** | 0.1747 | 0.1709 |
| copa_america_2019 | 26 | 0.1691 | 0.1646 | **0.1552** | 0.1562 |
| concacaf_gold_cup_2019 | 28 | 0.1508 | **0.1493** | 0.1653 | 0.1568 |
| afcon_2019 | 52 | 0.1819 | 0.1752 | 0.1762 | **0.1746** |
| uefa_euro_2020 | 51 | 0.1834 | 0.1908 | 0.1860 | **0.1814** |
| copa_america_2021 | 28 | 0.1649 | 0.1592 | **0.1527** | 0.1546 |
| concacaf_gold_cup_2021 | 25 | 0.1253 | 0.1224 | 0.1278 | **0.1195** |
| afcon_2022 | 52 | 0.2091 | 0.2113 | **0.1933** | 0.2010 |
| fifa_world_cup_2022 | 64 | 0.2257 | 0.2180 | **0.2141** | 0.2179 |
| concacaf_gold_cup_2023 | 25 | 0.1827 | 0.1895 | **0.1710** | 0.1733 |
| afc_asian_cup_2024 | 51 | 0.1674 | 0.1646 | **0.1557** | 0.1573 |
| afcon_2024 | 52 | 0.2138 | 0.2199 | **0.2028** | 0.2064 |
| uefa_euro_2024 | 51 | 0.1981 | 0.1971 | **0.1885** | 0.1901 |
| copa_america_2024 | 32 | 0.1600 | **0.1578** | 0.1711 | 0.1674 |
| concacaf_gold_cup_2025 | 28 | 0.1382 | **0.1303** | 0.1324 | 0.1315 |
| afcon_2025 | 52 | 0.1386 | **0.1341** | 0.1498 | 0.1444 |
| fifa_world_cup_2026 | 104 | 0.1603 | 0.1621 | 0.1525 | **0.1498** |

## Before / after

"Pooled" means the 27-tournament backtest. WC 2026 is the production
retrospective (`predict.py --as-of 2026-06-11`, so all 104 fixtures are priced
from pre-tournament form, then scored by `05_evaluate_wc2026.py`). Raw means
model probabilities scored goals-based. Credited means knockout draw mass is
redistributed by score-model xG and shootouts are scored for the team that
advanced.

| model | pooled RPS | pooled LL (raw / credited) | pooled acc | pooled draw recall | WC 2026 acc (raw / credited) | WC 2026 LL (raw / credited) | WC 2026 RPS (raw) | WC 2026 group stage |
|---|---|---|---|---|---|---|---|---|
| Shipped GBM, **as reported** (leaky) | — | — | — | — | 66.3% / 69.2% | 0.853 / 0.681 | — | 65.3% |
| Shipped GBM, honest (`--as-of`) | 0.1850 | 0.9466 / 0.8920 | 57.2% | 0.3% | 66.3% / 67.3% | 0.861 / 0.764 | 0.1616 | 61.1% |
| Elo logistic baseline | 0.1854 | 0.9470 / 0.8882 | 56.7% | 0.0% | — | — | — | — |
| Dixon-Coles alone | 0.1804 | 0.9281 / 0.8759 | 57.0% | 4.3% | — | — | — | — |
| **GBM + DC blend, T = 0.90 (served)** | **0.1802** | **0.9283 / 0.8754** | 57.2% | 0.7% | 65.4% / 65.4% | **0.815 / 0.732** | **0.1500** | 59.7% |

The WC 2026 backtest fold (in-tournament features, so not the same setup as
the retrospective) tells the same story. GBM: RPS 0.1603, LL 0.853. Blend:
RPS 0.1498, LL 0.813.

The leaky row's "raw" numbers come from the July 22 evaluation of the raw GBM
(`20260722_004013`). The leaky predictions JSON had no raw columns.

## What did not work

* **Temperature / isotonic on the GBM (ML-05).** The GBM's in-training isotonic
  wrapper already gives pooled ECE ≈ 0.03. Walk-forward temperature (T ≈ 1.08)
  and draw-bias scaling slightly *hurt* RPS (0.1850 → 0.1854). Dropping isotonic
  for temperature (`gbm_raw_temp`) is no better. Temperature only helps after
  blending, where it sharpens the mostly-Dixon-Coles mix (T = 0.90).
* **Threshold draw rule.** Re-tuned walk-forward
  (`python -m ml.pipeline.tune_draw_calibration`), the pooled optimum is
  threshold 0.50 / α 0.10, nowhere near the shipped 0.75 / 0.60. Nested
  walk-forward it improves log loss by 0.0006. The shipped constants were tuned
  on WC 2026 itself. They stay in `config.py` for the plain-GBM path only. The
  served ensemble does not apply them.
* **Draw recall.** Calibrated models almost never call a draw at argmax: with
  draws at about 26%, a draw is rarely the single most likely outcome. The balanced 123-feature logistic reaches 30% draw recall by
  over-predicting draws and pays for it (RPS 0.1901). Draw recall at argmax is
  the wrong target. Draw *calibration* is fine: the blend's draw-class bins
  read 0.16 → 0.17, 0.26 → 0.28, and 0.32 → 0.30 (predicted → observed).
* **Roadmap done-criterion for ML-04.** RPS and log loss improve without
  worsening log loss. Draw recall does not meaningfully improve (0.3% → 0.7%).

## Decisions to review

* **Served model: blend_temp rather than elo_dc_blend.** Both tie on the
  backtest (RPS 0.1802 vs 0.1802; excluding WC 2026, 0.1832 vs 0.1830).
  blend_temp keeps the GBM in the stack, as ML-04 asks. The GBM's weight is only
  0.2, so the served model is mostly Dixon-Coles.
* **WC 2026 accuracy drops by one match** (69 → 68 correct raw) while every
  probabilistic metric improves.
* **Frontend copy should stop quoting "69%".** The honest pre-tournament figure
  for the shipped model was 67% credited. The new model is 65% credited, with
  log loss 0.732.
* **Duplicate matches in the corpus (pre-existing).** The loader keeps both the
  FBref and martj42 rows for 18 tournament matches when they disagree on
  home/away (for example 9 Euro 2020 pairs). The backtest scores each match once
  (FBref row preferred). Training and Elo still count those matches twice.
  Follow-up: dedupe on (date, unordered team pair) in `ml/features/loader.py`.

## Reproduce

```
python -m ml.pipeline.backtest                      # ~9 min; features cached in ml/artifacts/feature_cache/
python -m ml.pipeline.tune_draw_calibration         # walk-forward draw rule grid
python -m ml.pipeline.train_ensemble --run-id <run> --variant blend_temp
python -m ml.pipeline.predict --fixtures data-pipeline/data/wc2026_full_fixtures.csv \
    --as-of 2026-06-11 --include-raw > data-pipeline/data/wc2026_predictions.json
python data-pipeline/scripts/05_evaluate_wc2026.py
```

Artifacts: `metrics.json` (per-tournament and pooled, raw and credited),
`predictions.csv` (every match × model), `reliability.json` (pooled per-class
decile bins for every model plus per-fold ECE, for the frontend), and
`summary.md`.
