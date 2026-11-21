"""ml-serve HTTP contract, with a fake predictor so no trained artifacts are needed."""

from typing import Any

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from ml.serve.app import create_app  # noqa: E402
from ml.serve.store import InputError  # noqa: E402


class FakeStore:
    def __init__(self, shot_error: Exception | None = None):
        self.match_calls: list[list[dict[str, Any]]] = []
        self.shot_error = shot_error

    def info(self) -> dict[str, Any]:
        return {"match_model_run_id": "run-1", "score_model_run_id": None, "shot_model_run_id": "shot-1"}

    def predict_matches(self, fixtures):
        self.match_calls.append(fixtures)
        return {"model_run_id": "run-1", "score_model_run_id": None, "predictions": [
            {"home_team": f["home_team"], "away_team": f["away_team"], "p_home_win": 0.5, "p_draw": 0.3,
             "p_away_win": 0.2, "predicted_home_goals": None, "predicted_away_goals": None,
             "home_xg": None, "away_xg": None} for f in fixtures]}

    def predict_shot(self, shot):
        if self.shot_error:
            raise self.shot_error
        return {"p_goal": 0.1, "model": "shot_xg_logistic", "model_run_id": "shot-1", **shot}


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def client(store):
    with TestClient(create_app(store)) as c:
        yield c


def test_health_reports_run_ids(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["match_model_run_id"] == "run-1"


def test_predict_match_passes_fixtures_with_defaults(client, store):
    resp = client.post("/predict/match", json={"fixtures": [
        {"home_team": "BRA", "away_team": "ARG", "match_date": "2026-06-11"}]})
    assert resp.status_code == 200
    assert resp.json()["predictions"][0]["p_home_win"] == 0.5
    sent = store.match_calls[0][0]
    assert sent == {"home_team": "BRA", "away_team": "ARG", "match_date": "2026-06-11",
                    "competition_id": "fifa_world_cup", "competition_stage": "group", "is_neutral_venue": True}


@pytest.mark.parametrize("fixture", [
    {"home_team": "bra", "away_team": "ARG", "match_date": "2026-06-11"},
    {"home_team": "BRA", "away_team": "ARG", "match_date": "11/06/2026"},
    {"home_team": "BRA", "away_team": "ARG", "match_date": "2026-06-11", "competition_stage": "semis"},
    {"home_team": "BRA", "away_team": "ARG", "match_date": "2026-06-11", "unexpected": 1},
])
def test_predict_match_rejects_bad_fixtures(client, fixture):
    assert client.post("/predict/match", json={"fixtures": [fixture]}).status_code == 422


def test_predict_match_rejects_empty_batch(client):
    assert client.post("/predict/match", json={"fixtures": []}).status_code == 422


def test_predict_shot(client):
    resp = client.post("/predict/shot", json={"distance_m": 14.2, "angle_deg": 22.5})
    assert resp.status_code == 200
    assert resp.json()["p_goal"] == 0.1


def test_predict_shot_range_checked(client):
    assert client.post("/predict/shot", json={"distance_m": -1, "angle_deg": 22.5}).status_code == 422
    assert client.post("/predict/shot", json={"distance_m": 10, "angle_deg": 95}).status_code == 422


def test_predict_shot_model_input_errors_are_422():
    with TestClient(create_app(FakeStore(shot_error=InputError("needs body_part")))) as c:
        resp = c.post("/predict/shot", json={"distance_m": 10, "angle_deg": 10})
    assert resp.status_code == 422
    assert "body_part" in resp.json()["detail"]


def test_predict_shot_without_model_is_503():
    with TestClient(create_app(FakeStore(shot_error=RuntimeError("No shot xG model loaded")))) as c:
        assert c.post("/predict/shot", json={"distance_m": 10, "angle_deg": 10}).status_code == 503
