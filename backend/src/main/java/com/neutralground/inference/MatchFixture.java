package com.neutralground.inference;

import com.fasterxml.jackson.annotation.JsonProperty;

/** One fixture as ml/serve expects it (the same columns as the predict CLI's fixtures CSV). */
public record MatchFixture(
        @JsonProperty("home_team") String homeTeam,
        @JsonProperty("away_team") String awayTeam,
        @JsonProperty("match_date") String matchDate,
        @JsonProperty("competition_id") String competitionId,
        @JsonProperty("competition_stage") String competitionStage,
        @JsonProperty("is_neutral_venue") boolean neutralVenue) {
}
