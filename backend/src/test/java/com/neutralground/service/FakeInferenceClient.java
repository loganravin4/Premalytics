package com.neutralground.service;

import com.neutralground.inference.InferenceClient;
import com.neutralground.inference.MatchFixture;
import com.neutralground.inference.MatchInferenceResult;
import com.neutralground.inference.ShotFeatures;
import com.neutralground.inference.ShotInferenceResult;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

/** In-memory InferenceClient: records calls and answers with a configurable function. */
class FakeInferenceClient implements InferenceClient {

    final List<List<MatchFixture>> matchCalls = new ArrayList<>();
    final List<ShotFeatures> shotCalls = new ArrayList<>();
    Function<List<MatchFixture>, MatchInferenceResult> matchAnswer = fixtures -> new MatchInferenceResult(
            "run-1", "score-1",
            fixtures.stream().map(f -> new MatchInferenceResult.Row(f.homeTeam(), f.awayTeam(),
                    0.5, 0.3, 0.2, 2, 1, 1.7, 0.9)).toList());

    @Override
    public MatchInferenceResult predictMatches(List<MatchFixture> fixtures) {
        matchCalls.add(fixtures);
        return matchAnswer.apply(fixtures);
    }

    @Override
    public ShotInferenceResult predictShot(ShotFeatures shot) {
        shotCalls.add(shot);
        return new ShotInferenceResult(0.12, "shot_xg_logistic", "shot-run", shot.distanceM(), shot.angleDeg());
    }
}
