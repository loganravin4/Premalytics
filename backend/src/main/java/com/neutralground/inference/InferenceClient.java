package com.neutralground.inference;

import java.util.List;

/** The long-lived Python inference service (ml/serve). Production implementation: {@link HttpInferenceClient}. */
public interface InferenceClient {

    MatchInferenceResult predictMatches(List<MatchFixture> fixtures);

    ShotInferenceResult predictShot(ShotFeatures shot);
}
