"""Publish a model run's tournament predictions into the Neutral Ground Postgres schema (ng), idempotently.

Usage: python -m ml.pipeline.publish --tournament wc2026 [--predict] [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data-pipeline" / "data"
ARTIFACTS_DIR = PROJECT_ROOT / "ml" / "artifacts"
TEAM_MAP = DATA_DIR / "static" / "team_map_intl.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ml.pipeline.publish")

STAGES = {"group", "round_of_32", "round_of_16", "quarter_final", "semi_final", "third_place", "final"}

# Add an entry per tournament the models cover.
TOURNAMENTS: dict[str, dict[str, Any]] = {
    "wc2026": {
        "name": "FIFA World Cup 2026",
        "competition_id": "fifa_world_cup",
        "season_year": 2026,
        "hosts": "Canada, Mexico, United States",
        "fixtures": DATA_DIR / "wc2026_full_fixtures.csv",
        "results": DATA_DIR / "wc2026_actual_results.csv",
        "predictions": DATA_DIR / "wc2026_predictions.json",
        "evaluation_dir": DATA_DIR / "evaluation" / "wc2026",
    },
}


class PublishError(RuntimeError):
    """Input data is inconsistent or incomplete; nothing was written."""


@dataclass
class MatchRow:
    match_number: int
    match_date: str
    stage: str
    home_team: str
    away_team: str
    neutral_venue: bool
    home_goals: int | None = None
    away_goals: int | None = None
    winner: str | None = None
    decided_on_penalties: bool = False

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.match_date, self.home_team, self.away_team)


@dataclass
class PredictionRow:
    match_key: tuple[str, str, str]
    p_home: float
    p_draw: float
    p_away: float
    predicted_home_goals: int | None = None
    predicted_away_goals: int | None = None
    home_xg: float | None = None
    away_xg: float | None = None


@dataclass
class Bundle:
    """Everything one publish writes, built and validated before the database is touched."""
    tournament_id: str
    tournament: dict[str, Any]
    teams: list[tuple[str, str, str]]
    matches: list[MatchRow]
    run_id: str
    run_metrics: dict[str, Any]
    run_evaluation: dict[str, Any] | None
    trained_through: str | None
    predictions: list[PredictionRow]
    score_run_id: str | None = None
    elo: list[tuple[str, str, float]] = field(default_factory=list)
    xg_grid: tuple[str, list[dict[str, Any]], dict[str, Any]] | None = None
    penalty: tuple[str, list[dict[str, Any]]] | None = None
    notes: str | None = None


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "t"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(line for line in fh if not line.lstrip().startswith("#")))


def build_teams(team_map_rows: Iterable[dict[str, str]]) -> list[tuple[str, str, str]]:
    """One (code, name, confederation) per team_id; alias rows collapse onto it."""
    teams: dict[str, tuple[str, str, str]] = {}
    for row in team_map_rows:
        code = row["team_id"].strip()
        if code not in teams:
            teams[code] = (code, row["full_name"].strip(), row["confederation"].strip())
    return sorted(teams.values())


def build_matches(fixture_rows: list[dict[str, str]],
                  result_rows: list[dict[str, str]] | None = None) -> list[MatchRow]:
    """Fixtures in file order become match_number 1..n; results join on (date, home, away)."""
    matches: list[MatchRow] = []
    seen: set[tuple[str, str, str]] = set()
    for i, f in enumerate(fixture_rows, start=1):
        stage = (f.get("competition_stage") or "group").strip().lower()
        if stage not in STAGES:
            raise PublishError(f"Fixture {i}: unknown stage {stage!r}")
        row = MatchRow(
            match_number=i,
            match_date=f["match_date"].strip(),
            stage=stage,
            home_team=f["home_team"].strip(),
            away_team=f["away_team"].strip(),
            neutral_venue=_truthy(f.get("is_neutral_venue", "true")),
        )
        if row.key in seen:
            raise PublishError(f"Duplicate fixture {row.key}")
        seen.add(row.key)
        matches.append(row)

    by_key = {m.key: m for m in matches}
    for r in result_rows or []:
        key = (r["match_date"].strip(), r["home_team"].strip(), r["away_team"].strip())
        match = by_key.get(key)
        if match is None:
            raise PublishError(f"Result {key} has no matching fixture")
        if str(r.get("goals_for", "")).strip() == "":
            continue
        match.home_goals = int(float(r["goals_for"]))
        match.away_goals = int(float(r["goals_against"]))
        winner = (r.get("winner") or "").strip() or None
        if match.home_goals > match.away_goals:
            winner = match.home_team
        elif match.away_goals > match.home_goals:
            winner = match.away_team
        if winner is not None and winner not in (match.home_team, match.away_team):
            raise PublishError(f"Result {key}: winner {winner} is not one of the two teams")
        match.winner = winner
        # Goals are after extra time, so a level score with a winner means penalties.
        match.decided_on_penalties = match.home_goals == match.away_goals and winner is not None
        if match.decided_on_penalties and match.stage == "group":
            raise PublishError(f"Result {key}: a group match cannot be decided on penalties")
    return matches


def build_predictions(matches: list[MatchRow], prediction_rows: list[dict[str, Any]],
                      score_rows: list[dict[str, Any]] | None = None) -> list[PredictionRow]:
    if len(prediction_rows) != len(matches):
        raise PublishError(f"{len(prediction_rows)} predictions for {len(matches)} fixtures")
    if score_rows is not None and len(score_rows) != len(matches):
        raise PublishError(f"{len(score_rows)} score predictions for {len(matches)} fixtures")

    out: list[PredictionRow] = []
    # The predict CLI output has no dates, so pair by position and check the teams.
    for i, (m, p) in enumerate(zip(matches, prediction_rows)):
        if (p["home_team"], p["away_team"]) != (m.home_team, m.away_team):
            raise PublishError(f"Prediction {i + 1} is {p['home_team']}-{p['away_team']}, "
                               f"fixture is {m.home_team}-{m.away_team}")
        probs = (float(p["p_home_win"]), float(p["p_draw"]), float(p["p_away_win"]))
        total = sum(probs)
        if any(v < 0 or v > 1 for v in probs) or abs(total - 1) > 0.01:
            raise PublishError(f"Prediction {i + 1} probabilities {probs} do not form a distribution")
        row = PredictionRow(m.key, *probs)
        if score_rows is not None:
            s = score_rows[i]
            if (s["home_team"], s["away_team"]) != (m.home_team, m.away_team):
                raise PublishError(f"Score prediction {i + 1} does not match fixture {m.key}")
            row.predicted_home_goals = int(s["predicted_home_goals"])
            row.predicted_away_goals = int(s["predicted_away_goals"])
            row.home_xg = round(float(s["home_xg"]), 4) if s.get("home_xg") is not None else None
            row.away_xg = round(float(s["away_xg"]), 4) if s.get("away_xg") is not None else None
        out.append(row)
    return out


def build_elo(features: Any, since: str, team_codes: set[str]) -> list[tuple[str, str, float]]:
    """Pre-match (team, date, elo) points; a team that played twice on one date keeps the later row."""
    required = {"match_date", "home_team", "away_team", "home_elo", "away_elo"}
    missing = required - set(features.columns)
    if missing:
        raise PublishError(f"Feature matrix lacks Elo columns: {sorted(missing)}")
    points: dict[tuple[str, str], float] = {}
    for row in features[sorted(required)].itertuples(index=False):
        day = str(row.match_date)[:10]
        if day < since:
            continue
        for team, elo in ((row.home_team, row.home_elo), (row.away_team, row.away_elo)):
            # elo == elo drops NaN.
            if team in team_codes and elo == elo:
                points[(team, day)] = round(float(elo), 2)
    return [(team, day, elo) for (team, day), elo in sorted(points.items())]


def build_xg_grid(payload: Any) -> tuple[str | None, list[dict[str, Any]]]:
    cells = payload.get("cells", []) if isinstance(payload, dict) else payload
    run_id = payload.get("model_run_id") if isinstance(payload, dict) else None
    out = []
    for c in cells:
        out.append({
            "distance_m": float(c["distance_m"]),
            "angle_deg": float(c["angle_deg"]),
            "body_part": str(c.get("body_part") or "any"),
            "situation": str(c.get("situation") or "any"),
            "p_goal": float(c["p_goal"]),
        })
    return run_id, out


def build_penalty_aggregates(payload: Any, dataset: str | None = None) -> tuple[str, list[dict[str, Any]]]:
    rows = payload.get("aggregates", []) if isinstance(payload, dict) else payload
    name = dataset or (payload.get("dataset") if isinstance(payload, dict) else None) or "penalty_kicks_v0"
    out = []
    for r in rows:
        kicks, goals = int(r["kicks"]), int(r["goals"])
        conversion = r.get("conversion")
        out.append({
            "dimension": str(r["dimension"]),
            "bucket": str(r["bucket"]),
            "kicks": kicks,
            "goals": goals,
            "conversion": float(conversion) if conversion is not None else (goals / kicks if kicks else 0.0),
        })
    return name, out


def _latest(pointer: str) -> str | None:
    path = ARTIFACTS_DIR / pointer
    return path.read_text().strip() if path.exists() else None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_evaluation(eval_root: Path, run_id: str) -> dict[str, Any] | None:
    """Newest evaluation metrics.json under eval_root whose model_run_id is run_id."""
    if not eval_root.exists():
        return None
    for run_dir in sorted((d for d in eval_root.iterdir() if d.is_dir()), reverse=True):
        metrics = run_dir / "metrics.json"
        if metrics.exists():
            data = _read_json(metrics)
            if data.get("model_run_id") == run_id:
                logger.info(f"Evaluation metrics: {metrics.relative_to(PROJECT_ROOT)}")
                return data
    return None


def _fixtures_frame(matches: list[MatchRow], competition_id: str):
    import pandas as pd
    return pd.DataFrame([{
        "match_date": m.match_date,
        "home_team": m.home_team,
        "away_team": m.away_team,
        "is_neutral_venue": m.neutral_venue,
        "competition_id": competition_id,
        "competition_stage": m.stage,
    } for m in matches])


def build_bundle(args: argparse.Namespace) -> Bundle:
    meta = TOURNAMENTS.get(args.tournament)
    if meta is None:
        raise PublishError(f"Unknown tournament {args.tournament!r}. Known: {sorted(TOURNAMENTS)}")

    teams = build_teams(read_csv(Path(args.team_map)))
    team_codes = {t[0] for t in teams}

    fixtures_path = Path(args.fixtures or meta["fixtures"])
    results_path = Path(args.results or meta["results"])
    results = read_csv(results_path) if results_path.exists() else None
    if results is None:
        logger.warning(f"No results file at {results_path}; publishing fixtures without results")
    matches = build_matches(read_csv(fixtures_path), results)
    unknown = sorted({t for m in matches for t in (m.home_team, m.away_team)} - team_codes)
    if unknown:
        raise PublishError(f"Teams missing from {args.team_map}: {unknown}")

    run_id = args.run_id or _latest("latest_run.txt")
    if not run_id:
        raise PublishError("No --run-id given and ml/artifacts/latest_run.txt does not exist")
    run_dir = ARTIFACTS_DIR / run_id

    if args.predict:
        from ml.pipeline.predict import predict_match_outcomes
        prediction_rows = predict_match_outcomes(_fixtures_frame(matches, meta["competition_id"]), run_id=run_id)
        notes = "predictions computed at publish time"
    else:
        predictions_path = Path(args.predictions or meta["predictions"])
        prediction_rows = _read_json(predictions_path)
        notes = f"predictions from {predictions_path.relative_to(PROJECT_ROOT).as_posix()}" \
            if predictions_path.is_relative_to(PROJECT_ROOT) else f"predictions from {predictions_path.name}"

    score_rows, score_run_id = None, None
    if args.scores == "auto":
        score_run_id = args.score_run_id or _latest("latest_score_run.txt")
        if score_run_id and (ARTIFACTS_DIR / score_run_id).exists():
            from ml.pipeline.predict_scores import score_fixtures
            score_rows = score_fixtures(_fixtures_frame(matches, meta["competition_id"]), run_id=score_run_id)
        else:
            logger.warning("No score model artifacts found; publishing without predicted scorelines")
            score_run_id = None
    elif args.scores != "none":
        score_rows = _read_json(Path(args.scores))
        score_run_id = args.score_run_id

    predictions = build_predictions(matches, prediction_rows, score_rows)

    metrics_path = run_dir / "metrics.json"
    run_metrics = _read_json(metrics_path) if metrics_path.exists() else {}
    if not run_metrics:
        logger.warning(f"No training metrics at {metrics_path}; model_runs.metrics will be empty")
    evaluation = (_read_json(Path(args.evaluation)) if args.evaluation
                  else find_evaluation(Path(meta["evaluation_dir"]), run_id))
    trained_through = run_metrics.get("trained_through") or _train_cutoff()

    elo: list[tuple[str, str, float]] = []
    if not args.no_elo:
        features_path = run_dir / "features.joblib"
        if features_path.exists():
            import joblib
            elo = build_elo(joblib.load(features_path), args.elo_since, team_codes)
        else:
            logger.warning(f"No {features_path}; skipping Elo history")

    xg_grid = None
    if args.xg_grid:
        grid_run_id, cells = build_xg_grid(_read_json(Path(args.xg_grid)))
        grid_run_id = args.shot_run_id or grid_run_id or _latest("latest_shot_run.txt")
        if not grid_run_id:
            raise PublishError("xG grid has no model_run_id; pass --shot-run-id")
        shot_metrics_path = ARTIFACTS_DIR / grid_run_id / "shot_metrics.json"
        shot_metrics = _read_json(shot_metrics_path) if shot_metrics_path.exists() else {}
        xg_grid = (grid_run_id, cells, shot_metrics)

    penalty = None
    if args.penalty_aggregates:
        penalty = build_penalty_aggregates(_read_json(Path(args.penalty_aggregates)), args.penalty_dataset)

    return Bundle(
        tournament_id=args.tournament,
        tournament={**meta, "start_date": min(m.match_date for m in matches),
                    "end_date": max(m.match_date for m in matches)},
        teams=teams, matches=matches, run_id=run_id, run_metrics=run_metrics, run_evaluation=evaluation,
        trained_through=trained_through, predictions=predictions, score_run_id=score_run_id, elo=elo,
        xg_grid=xg_grid, penalty=penalty, notes=notes,
    )


def _train_cutoff() -> str | None:
    try:
        from ml.config import TRAIN_CUTOFF_DATE
        return TRAIN_CUTOFF_DATE
    except ImportError:
        return None


def database_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    if os.environ.get("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    return "host={h} port={p} dbname={d} user={u} password={pw}".format(
        h=os.environ.get("DB_HOST", "localhost"), p=os.environ.get("DB_PORT", "5432"),
        d=os.environ.get("DB_NAME", "neutral_ground"), u=os.environ.get("DB_USER", "postgres"),
        pw=os.environ.get("DB_PASSWORD", "postgres"))


def write_bundle(conn, b: Bundle) -> dict[str, int]:
    from psycopg2.extras import Json, execute_values

    counts: dict[str, int] = {}
    with conn.cursor() as cur:
        # The API owns the schema through Flyway; this script only writes rows, never DDL.
        cur.execute("SELECT to_regclass('ng.predictions')")
        if cur.fetchone()[0] is None:
            raise PublishError("Schema ng is missing. Start the API once so Flyway applies the migrations.")

        execute_values(cur, """
            INSERT INTO ng.teams (code, name, confederation) VALUES %s
            ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, confederation = EXCLUDED.confederation
        """, b.teams)
        counts["teams"] = len(b.teams)

        t = b.tournament
        cur.execute("""
            INSERT INTO ng.tournaments (id, name, competition_id, season_year, hosts, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, competition_id = EXCLUDED.competition_id,
                season_year = EXCLUDED.season_year, hosts = EXCLUDED.hosts,
                start_date = EXCLUDED.start_date, end_date = EXCLUDED.end_date
        """, (b.tournament_id, t["name"], t["competition_id"], t["season_year"], t["hosts"],
              t["start_date"], t["end_date"]))

        # Park existing match numbers out of the way so a reordered fixture file cannot collide.
        cur.execute("UPDATE ng.matches SET match_number = -match_number WHERE tournament_id = %s",
                    (b.tournament_id,))
        match_ids = execute_values(cur, """
            INSERT INTO ng.matches (tournament_id, match_number, match_date, stage, home_team, away_team,
                                    neutral_venue, home_goals, away_goals, winner, decided_on_penalties)
            VALUES %s
            ON CONFLICT (tournament_id, match_date, home_team, away_team) DO UPDATE SET
                match_number = EXCLUDED.match_number, stage = EXCLUDED.stage,
                neutral_venue = EXCLUDED.neutral_venue, home_goals = EXCLUDED.home_goals,
                away_goals = EXCLUDED.away_goals, winner = EXCLUDED.winner,
                decided_on_penalties = EXCLUDED.decided_on_penalties
            RETURNING id, match_date::text, home_team, away_team
        """, [(b.tournament_id, m.match_number, m.match_date, m.stage, m.home_team, m.away_team,
               m.neutral_venue, m.home_goals, m.away_goals, m.winner, m.decided_on_penalties)
              for m in b.matches], fetch=True)
        id_by_key = {(d, h, a): i for i, d, h, a in match_ids}
        cur.execute("DELETE FROM ng.matches WHERE tournament_id = %s AND match_number < 0", (b.tournament_id,))
        counts["matches"] = len(id_by_key)
        counts["stale_matches_removed"] = cur.rowcount

        cur.execute("""
            INSERT INTO ng.model_runs (id, kind, trained_through, metrics, evaluation, notes, published_at)
            VALUES (%s, 'match', %s, %s, %s, %s, now())
            ON CONFLICT (id) DO UPDATE SET trained_through = EXCLUDED.trained_through,
                metrics = EXCLUDED.metrics, evaluation = COALESCE(EXCLUDED.evaluation, ng.model_runs.evaluation),
                notes = EXCLUDED.notes, published_at = now()
        """, (b.run_id, b.trained_through, Json(b.run_metrics),
              Json(b.run_evaluation) if b.run_evaluation is not None else None, b.notes))
        if b.score_run_id:
            cur.execute("""
                INSERT INTO ng.model_runs (id, kind, notes) VALUES (%s, 'score', 'scorelines for match predictions')
                ON CONFLICT (id) DO NOTHING
            """, (b.score_run_id,))

        execute_values(cur, """
            INSERT INTO ng.predictions (model_run_id, match_id, p_home, p_draw, p_away, predicted_home_goals,
                                        predicted_away_goals, home_xg, away_xg, score_model_run_id)
            VALUES %s
            ON CONFLICT (model_run_id, match_id) DO UPDATE SET p_home = EXCLUDED.p_home,
                p_draw = EXCLUDED.p_draw, p_away = EXCLUDED.p_away,
                predicted_home_goals = EXCLUDED.predicted_home_goals,
                predicted_away_goals = EXCLUDED.predicted_away_goals, home_xg = EXCLUDED.home_xg,
                away_xg = EXCLUDED.away_xg, score_model_run_id = EXCLUDED.score_model_run_id, created_at = now()
        """, [(b.run_id, id_by_key[p.match_key], p.p_home, p.p_draw, p.p_away, p.predicted_home_goals,
               p.predicted_away_goals, p.home_xg, p.away_xg, b.score_run_id if p.predicted_home_goals is not None
               else None) for p in b.predictions])
        counts["predictions"] = len(b.predictions)

        if b.elo:
            execute_values(cur, """
                INSERT INTO ng.team_elo (team_code, as_of_date, elo, model_run_id) VALUES %s
                ON CONFLICT (team_code, as_of_date) DO UPDATE SET elo = EXCLUDED.elo,
                    model_run_id = EXCLUDED.model_run_id
            """, [(team, day, elo, b.run_id) for team, day, elo in b.elo], page_size=5000)
        counts["elo_points"] = len(b.elo)

        if b.xg_grid:
            grid_run_id, cells, shot_metrics = b.xg_grid
            cur.execute("""
                INSERT INTO ng.model_runs (id, kind, metrics, published_at) VALUES (%s, 'shot_xg', %s, now())
                ON CONFLICT (id) DO UPDATE SET metrics = EXCLUDED.metrics, published_at = now()
            """, (grid_run_id, Json(shot_metrics)))
            cur.execute("DELETE FROM ng.shots_xg_grid WHERE model_run_id = %s", (grid_run_id,))
            execute_values(cur, """
                INSERT INTO ng.shots_xg_grid (model_run_id, distance_m, angle_deg, body_part, situation, p_goal)
                VALUES %s
            """, [(grid_run_id, c["distance_m"], c["angle_deg"], c["body_part"], c["situation"], c["p_goal"])
                  for c in cells], page_size=5000)
            counts["xg_grid_cells"] = len(cells)

        if b.penalty:
            dataset, rows = b.penalty
            cur.execute("DELETE FROM ng.penalty_aggregates WHERE dataset = %s", (dataset,))
            execute_values(cur, """
                INSERT INTO ng.penalty_aggregates (dataset, dimension, bucket, kicks, goals, conversion) VALUES %s
            """, [(dataset, r["dimension"], r["bucket"], r["kicks"], r["goals"], r["conversion"]) for r in rows])
            counts["penalty_aggregates"] = len(rows)
    return counts


def summarize(b: Bundle) -> dict[str, Any]:
    played = [m for m in b.matches if m.home_goals is not None]
    return {
        "tournament": b.tournament_id,
        "model_run_id": b.run_id,
        "score_model_run_id": b.score_run_id,
        "teams": len(b.teams),
        "matches": len(b.matches),
        "played": len(played),
        "decided_on_penalties": sum(m.decided_on_penalties for m in played),
        "predictions": len(b.predictions),
        "with_scoreline": sum(p.predicted_home_goals is not None for p in b.predictions),
        "elo_points": len(b.elo),
        "has_evaluation": b.run_evaluation is not None,
        "xg_grid_cells": len(b.xg_grid[1]) if b.xg_grid else 0,
        "penalty_aggregates": len(b.penalty[1]) if b.penalty else 0,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publish a model run's tournament predictions to Postgres")
    p.add_argument("--tournament", default="wc2026", help="Tournament id (default: wc2026)")
    p.add_argument("--run-id", help="Match model run id (default: ml/artifacts/latest_run.txt)")
    p.add_argument("--fixtures", help="Fixtures CSV (default: per tournament)")
    p.add_argument("--results", help="Results CSV (default: per tournament; skipped if missing)")
    p.add_argument("--predictions", help="Predictions JSON from ml.pipeline.predict (default: per tournament)")
    p.add_argument("--predict", action="store_true", help="Compute predictions now instead of reading JSON")
    p.add_argument("--scores", default="auto",
                   help="'auto' (score model if its artifacts exist), 'none', or a predict_scores JSON path")
    p.add_argument("--score-run-id", help="Score model run id (default: ml/artifacts/latest_score_run.txt)")
    p.add_argument("--evaluation", help="Evaluation metrics.json (default: newest one for this run)")
    p.add_argument("--team-map", default=str(TEAM_MAP), help="Team map CSV")
    p.add_argument("--elo-since", default="2010-01-01", help="Earliest Elo date to publish (YYYY-MM-DD)")
    p.add_argument("--no-elo", action="store_true", help="Skip Elo history")
    p.add_argument("--xg-grid", help="XG-04 xg_grid.json to publish")
    p.add_argument("--shot-run-id", help="Shot model run id for the xG grid")
    p.add_argument("--penalty-aggregates", help="PEN-03 penalty_aggregates.json to publish")
    p.add_argument("--penalty-dataset", help="Dataset name for the penalty aggregates")
    p.add_argument("--database-url", help="libpq URL or DSN (default: DATABASE_URL or DB_* env vars)")
    p.add_argument("--dry-run", action="store_true", help="Build and validate rows; write nothing")
    args = p.parse_args(argv)
    date.fromisoformat(args.elo_since)
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        bundle = build_bundle(args)
    except (PublishError, FileNotFoundError) as e:
        logger.error(str(e))
        return 1
    summary = summarize(bundle)
    if args.dry_run:
        print(json.dumps({"dry_run": True, **summary}, indent=2))
        return 0

    import psycopg2
    conn = psycopg2.connect(database_url(args.database_url))
    try:
        with conn:
            counts = write_bundle(conn, bundle)
    except PublishError as e:
        logger.error(str(e))
        return 1
    finally:
        conn.close()
    print(json.dumps({**summary, "written": counts}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
