# Neutral Ground API (backend)

Spring Boot 3.5 / Java 21. The public API for Neutral Ground: tournaments, matches, teams, model scorecards,
and ad-hoc predictions. JSON contract: [API.md](API.md). Live OpenAPI: `/api/docs` (Swagger UI at
`/api/docs/ui`).

```
browser ──► api (Spring, :8080) ──► Postgres (schema ng, Flyway)
                     │
                     └──► ml-serve (FastAPI, :8000; models loaded once at startup)

ml/pipeline/publish.py ──► Postgres   (batch: a model run's predictions, results, metrics, Elo)
```

Predictions for known fixtures are computed in batch and published to Postgres; the API only reads them.
Ad-hoc inference (`POST /api/predictions/*`) is forwarded to ml-serve over HTTP with timeouts. Spring never
starts a Python process.

## Run everything with Docker

Needs Docker and trained artifacts in `ml/artifacts/` (gitignored: train them or copy them in).

```powershell
docker compose up --build -d
docker compose --profile tools run --rm publish
```

The first command starts Postgres, ml-serve, and the API (Flyway creates schema `ng` on API startup). The
second loads the WC 2026 run into the database. Then open `http://localhost:8080/api/tournaments/wc2026`.

If port 5432 or 8080 is taken, set `DB_PORT` or change the `api` port mapping. Stop with `docker compose down`
(add `-v` to drop the database volume).

## Run locally without Docker

1. Postgres 17 with an empty database (default `neutral_ground`, user `postgres`, password `postgres`):

   ```powershell
   docker compose up -d postgres
   ```

2. ml-serve, from the repo root, in the project venv (see `docs/VENV.md`):

   ```powershell
   data-pipeline/venv/Scripts/pip install -r ml/serve/requirements.txt
   ```

   ```powershell
   data-pipeline/venv/Scripts/python -m uvicorn ml.serve.app:app --port 8000
   ```

3. The API, from `backend/`:

   ```powershell
   ./mvnw spring-boot:run
   ```

4. Publish a run, from the repo root:

   ```powershell
   data-pipeline/venv/Scripts/python -m ml.pipeline.publish --tournament wc2026
   ```

   `--dry-run` validates every row without touching the database. `--predict` re-scores the fixtures with the
   current model instead of reading `data-pipeline/data/wc2026_predictions.json`. `--xg-grid` and
   `--penalty-aggregates` publish the lab data once XG-04 and PEN-03 produce it. `--help` lists the rest.

## Configuration

Environment variables (a repo-root `.env` is also read):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` | `localhost` `5432` `neutral_ground` `postgres` `postgres` | Database |
| `ML_SERVE_URL` | `http://localhost:8000` | ml-serve base URL |
| `ML_SERVE_CONNECT_TIMEOUT` / `ML_SERVE_READ_TIMEOUT` | `2s` / `5s` | ml-serve timeouts |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated; `*` is ignored |
| `RATE_LIMIT_CAPACITY` / `RATE_LIMIT_REFILL_PER_MINUTE` | `30` / `30` | Per-IP token bucket on POST `/api/**` |
| `READ_CACHE_TTL` | `5m` | In-memory cache for read endpoints |
| `READ_CACHE_MAX_AGE` | `5m` | `Cache-Control: max-age` on reads |
| `PORT` | `8080` | HTTP port |

After publishing a new run, reads can be up to `READ_CACHE_TTL` stale; restart the API to see it at once.
Behind a reverse proxy, set `server.forward-headers-strategy=native` so rate limiting sees client IPs.

ml-serve reads `NG_MATCH_RUN_ID`, `NG_SCORE_RUN_ID`, `NG_SHOT_RUN_ID` (default: the `latest_*.txt` pointers in
`ml/artifacts`) and `NG_SHOT_MODEL_FILE` (default `logistic_xg.joblib`). Restart it to pick up a new run.

## Tests

```powershell
./mvnw test
```

- `web/*Test`: `@WebMvcTest` slices for every endpoint, validation, error bodies, CORS, rate limiting.
- `service/PredictionServiceTest`: inference mapping against a fake `InferenceClient`.
- `inference/HttpInferenceClientTest`: the HTTP contract with ml-serve (`MockRestServiceServer`).
- `ReadApiIntegrationTest`: Testcontainers Postgres; Flyway on a fresh database, Hibernate schema validation,
  every read endpoint over seeded data. **Skipped when Docker is not running.**

Python side: `python -m pytest ml/tests -q` (includes `test_publish.py` and `test_serve.py`).
Latency check for a running ml-serve: `python -m ml.serve.bench --url http://127.0.0.1:8000`.

## Layout

```
src/main/java/com/neutralground/
  config/      properties, CORS + ETag, cache, OpenAPI, rate limit filter, RestClient for ml-serve
  domain/      read-only JPA entities for schema ng
  repository/  Spring Data repositories
  service/     read services (cached) and PredictionService (inference)
  inference/   InferenceClient and its HTTP implementation, ml-serve wire records
  web/         controllers, error handler, Cache-Control advice, DTO records, @KnownTeam validation
src/main/resources/db/migration/   Flyway migrations (schema ng)
```

The old `database/schema/*.sql` (schema `pl_data`) is legacy; see [database/README.md](../database/README.md).
