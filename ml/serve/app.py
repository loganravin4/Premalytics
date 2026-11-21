"""
ml-serve: FastAPI inference service called by the Spring API (never by browsers directly).

    uvicorn ml.serve.app:app --host 0.0.0.0 --port 8000      # from the repo root

Endpoints:
    GET  /health          model run ids; 200 once models are loaded
    POST /predict/match   {"fixtures": [{home_team, away_team, match_date, competition_id,
                           competition_stage, is_neutral_venue}]}
                          -> {"model_run_id", "score_model_run_id", "predictions": [{home_team, away_team,
                              p_home_win, p_draw, p_away_win, predicted_home_goals, predicted_away_goals,
                              home_xg, away_xg}]}
    POST /predict/shot    {"distance_m", "angle_deg", "body_part"?, "situation"?}
                          -> {"p_goal", "model", "model_run_id", "distance_m", "angle_deg"}

Environment: NG_MATCH_RUN_ID, NG_SCORE_RUN_ID, NG_SHOT_RUN_ID pin runs (default: the latest_*.txt
pointers in ml/artifacts); NG_SHOT_MODEL_FILE picks the shot model file (default logistic_xg.joblib).
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from ml.serve.store import InputError, Predictor

logger = logging.getLogger("ml.serve")

Stage = Literal["group", "round_of_32", "round_of_16", "quarter_final", "semi_final", "third_place", "final"]


class Fixture(BaseModel):
    model_config = ConfigDict(extra="forbid")

    home_team: str = Field(pattern=r"^[A-Z]{3}$")
    away_team: str = Field(pattern=r"^[A-Z]{3}$")
    match_date: date
    competition_id: str = Field(default="fifa_world_cup", pattern=r"^[a-z][a-z0-9_]{1,39}$")
    competition_stage: Stage = "group"
    is_neutral_venue: bool = True


class MatchRequest(BaseModel):
    fixtures: list[Fixture] = Field(min_length=1, max_length=50)


class MatchPrediction(BaseModel):
    home_team: str
    away_team: str
    p_home_win: float
    p_draw: float
    p_away_win: float
    predicted_home_goals: int | None = None
    predicted_away_goals: int | None = None
    home_xg: float | None = None
    away_xg: float | None = None


class MatchResponse(BaseModel):
    model_run_id: str
    score_model_run_id: str | None = None
    predictions: list[MatchPrediction]


class ShotRequest(BaseModel):
    distance_m: float = Field(ge=0, le=120)
    angle_deg: float = Field(ge=0, le=90)
    body_part: str | None = Field(default=None, pattern=r"^[a-z_]{1,20}$")
    situation: str | None = Field(default=None, pattern=r"^[a-z_]{1,20}$")


class ShotResponse(BaseModel):
    p_goal: float
    model: str
    model_run_id: str | None
    distance_m: float
    angle_deg: float


def _default_store() -> Predictor:
    from ml.serve.store import ModelStore

    return ModelStore(
        match_run_id=os.environ.get("NG_MATCH_RUN_ID") or None,
        score_run_id=os.environ.get("NG_SCORE_RUN_ID") or None,
        shot_run_id=os.environ.get("NG_SHOT_RUN_ID") or None,
        shot_model_file=os.environ.get("NG_SHOT_MODEL_FILE", "logistic_xg.joblib"),
    )


def create_app(store: Predictor | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        started = time.perf_counter()
        app.state.store = store if store is not None else _default_store()
        logger.info(f"ml-serve ready in {time.perf_counter() - started:.1f}s")
        yield

    app = FastAPI(title="Neutral Ground ml-serve", version="1", lifespan=lifespan)

    @app.get("/health")
    def health(request: Request) -> dict[str, Any]:
        return {"status": "ok", **request.app.state.store.info()}

    @app.post("/predict/match", response_model=MatchResponse)
    def predict_match(body: MatchRequest, request: Request) -> dict[str, Any]:
        fixtures = [{**f.model_dump(), "match_date": f.match_date.isoformat()} for f in body.fixtures]
        return request.app.state.store.predict_matches(fixtures)

    @app.post("/predict/shot", response_model=ShotResponse)
    def predict_shot(body: ShotRequest, request: Request) -> dict[str, Any]:
        try:
            return request.app.state.store.predict_shot(body.model_dump())
        except InputError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

    return app


app = create_app()
