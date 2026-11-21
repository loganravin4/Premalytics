# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, confirmed by the owner (2026-11-21):

- **Football fans** who followed World Cup 2026 and want to see how a model read each match: who it backed, where it was right, where it was badly wrong.
- **Technical reviewers** (recruiters, engineers, data scientists) evaluating the project as a portfolio piece. They look for honest metrics, a clear method, and evidence that the numbers were produced without leakage.

## Product Purpose

Neutral Ground is an international football analytics site. Its core is a match-outcome model trained on ~30,000 international matches that priced every World Cup 2026 match before a ball was kicked. The site shows that record match by match and explains how the model works and where it fails. Later surfaces add a shot xG lab, a penalties lab, and tournament simulations for upcoming international tournaments (Euro 2028, AFCON 2027, WC 2030 qualifying).

Success: a fan can find any WC 2026 match and see the model's call against the result in seconds; a reviewer leaves trusting the numbers because the site shows its misses as plainly as its hits.

## Positioning

Pre-tournament probabilities for all 104 WC 2026 matches, scored against what happened, with the misses shown as prominently as the hits. Not a tipster, not betting advice, not a live scores site.

## Operating Context

- Static-first: the frontend reads JSON generated from repo outputs (`data-pipeline/data/evaluation/wc2026/<run>/predictions_scored.csv`, `wc2026_full_fixtures.csv`, `data-pipeline/data/static/team_map_intl.csv`, `ml/artifacts/<run>/metrics.json`). A Spring Boot API (`docs/ROADMAP.md` BE-04) replaces this later behind `VITE_API_URL`.
- Read on phones during and after matches; read on laptops by reviewers.

## Capabilities and Constraints

- Stack: React 19 + TypeScript + Vite 7 + Tailwind v4, React Router 7, Framer Motion, Recharts (existing).
- Teams are identified by three-letter FIFA-style codes (`team_map_intl.csv`). No official crests or FIFA marks may be used.
- No player-level data exists for international matches; no player pages.
- Two scoring modes exist for knockouts: raw (draw is a valid outcome) and shootout-credited. Every headline number states which.
- Open: xG lab (FE-02), penalties lab (FE-03), simulator (FE-17) wait on ML tracks.

## Brand Commitments

- Name: **Neutral Ground** (formerly Premalytics; renamed 2026-11-21 when the project left the Premier League). The name nods to neutral-venue tournament football, which is also a model feature.
- Voice: plain, specific, a little dry. States numbers with their caveats. Never hype, never betting language ("lock", "banker", "value").
- No FIFA, World Cup, or federation logos, trophy imagery, or official tournament branding. "World Cup 2026" is used as a plain descriptive name.

## Evidence on Hand

- WC 2026 scored predictions, served blend model (leak-free run `20261121_144554`, form frozen at 11 June 2026): 104 matches, 68 correct (65.4%) shootout-credited, log loss 0.732; strict 65.4%, log loss 0.815. The previous GBM model's leak-free record was 70/104, log loss 0.764 / 0.861 strict.
- Walk-forward backtest, 27 tournaments 2014–2026 (1,150 matches): blend RPS 0.1802, previous GBM 0.1850, Elo logistic 0.1854 (`docs/ML_EXPERIMENTS.md`).
- The earlier 72/104 (69%, log loss 0.681) figure leaked in-tournament form and must not be quoted.
- Training: 30,417 matches, 123 features.
- Shot xG: Brier 0.087 on 1,417 WC 2022 shots.
- No testimonials, users, press, or partner logos exist. None may be invented.

## Product Principles

1. Misses are content. Every place that shows a hit can show a miss.
2. Every number carries its denominator and its mode.
3. Probabilities, not picks. Show the three-way split, not just the winner.
4. The match is the unit. Everything links back to individual matches.

## Accessibility & Inclusion

WCAG 2.2 AA. Probability encodings must not rely on color alone (labels and positions carry the meaning). Respect reduced motion.
