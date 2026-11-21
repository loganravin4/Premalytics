# Neutral Ground

International football analytics. A match-outcome model trained on ~30,000 international matches priced every
World Cup 2026 match before a ball was kicked; the site shows that record match by match, misses included, and
explains how the model works.

> Formerly **Premalytics** (a Premier League project). The EPL baseline is archived at `archive/epl-2025`.
> The repo and folder still carry the old name until they are renamed.

**Outstanding work lives in [`docs/ROADMAP.md`](docs/ROADMAP.md).** Product and design context: [`PRODUCT.md`](PRODUCT.md).

---

## Where it stands

| Area | State |
|------|-------|
| Match model | Gradient-boosted + logistic, 123 features. WC 2026, leak-free (form frozen at 11 June 2026): 70/104 called (67.3%, shootout-credited, log loss 0.764); strict 66.3%, log loss 0.861. An earlier 72/104 figure leaked in-tournament form and is retracted. |
| Shot xG | Logistic + GBM on StatsBomb open data; being expanded (ROADMAP XG-05 → XG-07). |
| Penalties | Not started (ROADMAP PEN-01 → PEN-03). |
| Backend | Spring Boot; being rebuilt (ROADMAP BE-01 → BE-08). |
| Frontend | Rebuilt as Neutral Ground on static JSON generated from pipeline outputs. |

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 19 + TypeScript + Vite + Tailwind v4 |
| Backend | Spring Boot (Java) |
| ML pipeline | Python: scikit-learn, LightGBM/HistGradientBoosting, pandas |
| Data pipeline | Python: martj42 international results, FBref via soccerdata, StatsBomb open data |
| Database | PostgreSQL |

## Quick start

```bash
# ML (from repo root, in the data-pipeline venv; see docs/VENV.md)
python -m pytest ml/tests -q
python -m ml.pipeline.train
python -m ml.pipeline.evaluate
python data-pipeline/scripts/05_evaluate_wc2026.py

# Frontend
cd frontend
npm install
npm run data   # regenerate src/data/generated/ from the latest evaluation run
npm run dev
```

## Repo layout

```
data-pipeline/   ingest, normalization, WC 2026 fixtures/results/evaluation
ml/              features, models, train/evaluate/predict CLIs, tests
backend/         Spring Boot API
frontend/        Neutral Ground web app
database/        legacy SQL schema (pl_data), being replaced by migrations
docs/            ROADMAP.md (outstanding work), WC_SPEC.md + WC_HANDOFF.md (pivot history and rules), data contracts
```
