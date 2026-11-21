"""
Model loading for ml-serve.
ml/pipeline calls joblib.load on every prediction, so a process-wide memoizing joblib.load lets that code run unchanged while each artifact is read once.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Protocol

import joblib

logger = logging.getLogger("ml.serve")

_original_load = joblib.load
_cache: dict[str, Any] = {}
_cache_lock = threading.Lock()


def _memoized_load(filename, *args, **kwargs):
    if not isinstance(filename, (str, os.PathLike)):
        return _original_load(filename, *args, **kwargs)
    key = str(Path(filename).resolve())
    with _cache_lock:
        if key not in _cache:
            logger.info(f"Loading {key}")
            _cache[key] = _original_load(filename, *args, **kwargs)
        return _cache[key]


def install_memoized_joblib_load() -> None:
    joblib.load = _memoized_load


_reuse = threading.local()
_original_score_fixtures = None


def _reusing_score_fixtures(fixtures, run_id=None):
    current = getattr(_reuse, "current", None)
    if current is not None and current[0] is fixtures and current[1] == run_id:
        return current[2]
    return _original_score_fixtures(fixtures, run_id=run_id)


def install_score_reuse() -> None:
    """Let one request reuse its scoreline predictions (per thread, so concurrent requests stay apart)."""
    global _original_score_fixtures
    import ml.pipeline.predict_scores as predict_scores

    if _original_score_fixtures is None:
        _original_score_fixtures = predict_scores.score_fixtures
        predict_scores.score_fixtures = _reusing_score_fixtures


class Predictor(Protocol):
    """What the HTTP layer needs. ModelStore is the real one; tests pass a fake."""

    def info(self) -> dict[str, Any]: ...

    def predict_matches(self, fixtures: list[dict[str, Any]]) -> dict[str, Any]: ...

    def predict_shot(self, shot: dict[str, Any]) -> dict[str, Any]: ...


class InputError(ValueError):
    """The request cannot be scored by the loaded model (maps to HTTP 422)."""


def _read_pointer(artifacts: Path, name: str) -> str | None:
    path = artifacts / name
    return path.read_text().strip() if path.exists() else None


class ModelStore:
    def __init__(self, match_run_id: str | None = None, score_run_id: str | None = None,
                 shot_run_id: str | None = None, shot_model_file: str = "logistic_xg.joblib"):
        from ml.config import ARTIFACTS_DIR

        install_memoized_joblib_load()
        self.artifacts = ARTIFACTS_DIR
        # Run ids are pinned here; restart the service to pick up a new run.
        self.match_run_id = match_run_id or _read_pointer(ARTIFACTS_DIR, "latest_run.txt")
        if not self.match_run_id:
            raise RuntimeError("No match model run. Train first: python -m ml.pipeline.train")
        self.score_run_id = score_run_id or _read_pointer(ARTIFACTS_DIR, "latest_score_run.txt")
        if self.score_run_id and not (ARTIFACTS_DIR / self.score_run_id).exists():
            logger.warning(f"Score run {self.score_run_id} not found; scorelines disabled")
            self.score_run_id = None
        self.shot_run_id = shot_run_id or _read_pointer(ARTIFACTS_DIR, "latest_shot_run.txt")
        self.shot_model_file = shot_model_file
        self._shot_model = None
        self._shot_features: list[str] = []
        self._warm()

    def _warm(self) -> None:
        features = joblib.load(self.artifacts / self.match_run_id / "features.joblib")
        last = features.iloc[-1]
        warm = [
            {"match_date": str(last["match_date"])[:10], "home_team": last["home_team"],
             "away_team": last["away_team"], "is_neutral_venue": True,
             "competition_id": "fifa_world_cup", "competition_stage": stage}
            for stage in ("group", "final")
        ]
        self.predict_matches(warm)
        if self.shot_run_id and (self.artifacts / self.shot_run_id / self.shot_model_file).exists():
            from ml.models.shot_xg import LOGISTIC_FEATURES

            self._shot_model = joblib.load(self.artifacts / self.shot_run_id / self.shot_model_file)
            names = getattr(self._shot_model, "feature_names_in_", None)
            self._shot_features = list(names) if names is not None else list(LOGISTIC_FEATURES)
        else:
            logger.warning("No shot xG model found; /predict/shot will return 503")
        logger.info(f"Models ready: match={self.match_run_id} score={self.score_run_id} shot={self.shot_run_id}")

    def info(self) -> dict[str, Any]:
        return {
            "match_model_run_id": self.match_run_id,
            "score_model_run_id": self.score_run_id,
            "shot_model_run_id": self.shot_run_id if self._shot_model is not None else None,
            "shot_features": self._shot_features,
        }

    def predict_matches(self, fixtures: list[dict[str, Any]]) -> dict[str, Any]:
        import pandas as pd
        from ml.pipeline.predict import predict_match_outcomes

        frame = pd.DataFrame(fixtures)
        scores: list[dict[str, Any] | None] = [None] * len(fixtures)
        if self.score_run_id:
            install_score_reuse()
            scores = _original_score_fixtures(frame, run_id=self.score_run_id)
            # predict_match_outcomes rescores knockouts for draw redistribution; reuse these instead.
            _reuse.current = (frame, self.score_run_id, scores)
        try:
            outcomes = predict_match_outcomes(frame, run_id=self.match_run_id, score_run_id=self.score_run_id)
        finally:
            _reuse.current = None
        rows = []
        for o, s in zip(outcomes, scores):
            rows.append({
                **o,
                "predicted_home_goals": int(s["predicted_home_goals"]) if s else None,
                "predicted_away_goals": int(s["predicted_away_goals"]) if s else None,
                "home_xg": round(float(s["home_xg"]), 4) if s else None,
                "away_xg": round(float(s["away_xg"]), 4) if s else None,
            })
        return {"model_run_id": self.match_run_id, "score_model_run_id": self.score_run_id, "predictions": rows}

    def predict_shot(self, shot: dict[str, Any]) -> dict[str, Any]:
        import pandas as pd

        if self._shot_model is None:
            raise RuntimeError("No shot xG model loaded")
        missing = [f for f in self._shot_features if shot.get(f) is None]
        if missing:
            raise InputError(f"The loaded shot model needs: {', '.join(missing)}")
        X = pd.DataFrame([{f: shot[f] for f in self._shot_features}], columns=self._shot_features)
        goal_idx = list(self._shot_model.classes_).index(1)
        p_goal = float(self._shot_model.predict_proba(X)[0][goal_idx])
        return {
            "p_goal": round(p_goal, 4),
            "model": f"shot_xg_{Path(self.shot_model_file).stem.removesuffix('_xg')}",
            "model_run_id": self.shot_run_id,
            "distance_m": shot["distance_m"],
            "angle_deg": shot["angle_deg"],
        }
