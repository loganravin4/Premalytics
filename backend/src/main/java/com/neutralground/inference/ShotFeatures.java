package com.neutralground.inference;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;

/** Request body of POST /predict/shot on ml/serve. Optional fields are omitted when null. */
@JsonInclude(JsonInclude.Include.NON_NULL)
public record ShotFeatures(
        @JsonProperty("distance_m") double distanceM,
        @JsonProperty("angle_deg") double angleDeg,
        @JsonProperty("body_part") String bodyPart,
        @JsonProperty("situation") String situation) {
}
