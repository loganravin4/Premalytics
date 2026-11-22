# Neutral Ground: frontend

React 19 + TypeScript + Vite + Tailwind v4.

```bash
npm install
npm run data    # rebuild src/data/generated/wc2026.json from the pipeline's latest evaluation run
npm run dev
npm run build
npm run lint
```

## Data

The site reads `src/data/generated/wc2026.json`, written by `scripts/build-data.mjs` from:

- `data-pipeline/data/evaluation/wc2026/<latest run>/predictions_scored.csv` and `metrics.json`
- `data-pipeline/data/wc2026_full_fixtures.csv`, `wc2026_actual_results.csv`
- `data-pipeline/data/static/team_map_intl.csv`
- `ml/artifacts/<model run>/metrics.json` for the training-set size and feature count, when present
- `ml/exports/xg_grid.json` and `ml/exports/penalty_aggregates.json` for the xG lab and penalties pages, which load lazily

The generated file is committed so the site builds without the pipeline. When the Spring API (ROADMAP BE-04) lands,
the data module switches to it behind `VITE_API_URL`.

Groups are derived from the group-stage schedule and labeled by their teams; official group letters are not in the data.

## Design

Direction and product context: `../PRODUCT.md`. Tokens live in `src/index.css` (`:root` and the dark variants).
