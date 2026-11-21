package com.neutralground.inference;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

/** Response of POST /predict/match on ml/serve. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record MatchInferenceResult(
        @JsonProperty("model_run_id") String modelRunId,
        @JsonProperty("score_model_run_id") String scoreModelRunId,
        @JsonProperty("predictions") List<Row> predictions) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Row(
            @JsonProperty("home_team") String homeTeam,
            @JsonProperty("away_team") String awayTeam,
            @JsonProperty("p_home_win") double pHomeWin,
            @JsonProperty("p_draw") double pDraw,
            @JsonProperty("p_away_win") double pAwayWin,
            @JsonProperty("predicted_home_goals") Integer predictedHomeGoals,
            @JsonProperty("predicted_away_goals") Integer predictedAwayGoals,
            @JsonProperty("home_xg") Double homeXg,
            @JsonProperty("away_xg") Double awayXg) {
    }
}
