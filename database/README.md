# database/ (legacy)

Everything in this folder is from the Premier League era of the project and is **not used** by Neutral Ground.

- `schema/*.sql` creates the old `pl_data` schema (clubs, seasons, player and keeper stats).
- `scripts/load_data_to_postgres.py` loads the old EPL CSVs into it.

The current schema lives in Flyway migrations under
[`backend/src/main/resources/db/migration/`](../backend/src/main/resources/db/migration/) (schema `ng`). The API applies
them on startup. Data is loaded by `python -m ml.pipeline.publish` (see [`backend/README.md`](../backend/README.md)).

These files are kept for reference only. Do not add new tables here.
