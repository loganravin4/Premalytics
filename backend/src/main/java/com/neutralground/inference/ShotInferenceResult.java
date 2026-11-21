package com.neutralground.inference;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Response of POST /predict/shot on ml/serve. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record ShotInferenceResult(
        @JsonProperty("p_goal") double pGoal,
        @JsonProperty("model") String model,
        @JsonProperty("model_run_id") String modelRunId,
        @JsonProperty("distance_m") double distanceM,
        @JsonProperty("angle_deg") double angleDeg) {
}
