package com.premalytics.dto;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Outbound shot-xG result. Deserialized from the Python predict_shot CLI's
 * stdout JSON and serialized back to the frontend in the same shape.
 *
 * The @JsonProperty annotations on the fields are the single source of the
 * external (snake_case) keys; the getPGoal() getter is @JsonIgnore'd so Jackson
 * does not also emit a getter-derived "pgoal" key.
 */
public class ShotPredictionResponse {

    @JsonProperty("p_goal")
    private double pGoal;

    @JsonProperty("distance_m")
    private double distanceM;

    @JsonProperty("angle_deg")
    private double angleDeg;

    @JsonProperty("model")
    private String model;

    public ShotPredictionResponse() {
    }

    @JsonIgnore
    public double getPGoal() {
        return pGoal;
    }

    public void setPGoal(double pGoal) {
        this.pGoal = pGoal;
    }

    public double getDistanceM() {
        return distanceM;
    }

    public void setDistanceM(double distanceM) {
        this.distanceM = distanceM;
    }

    public double getAngleDeg() {
        return angleDeg;
    }

    public void setAngleDeg(double angleDeg) {
        this.angleDeg = angleDeg;
    }

    public String getModel() {
        return model;
    }

    public void setModel(String model) {
        this.model = model;
    }
}
