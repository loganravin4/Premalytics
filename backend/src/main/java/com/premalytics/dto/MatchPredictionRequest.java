package com.premalytics.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Inbound match-prediction request. Deserialized from snake_case JSON (mirrors
 * the wc_fixtures.csv columns the Python predict CLI reads); @JsonAlias also
 * accepts the camelCase form of each key.
 */
public class MatchPredictionRequest {

    @JsonProperty("home_team")
    @JsonAlias("homeTeam")
    private String homeTeam;

    @JsonProperty("away_team")
    @JsonAlias("awayTeam")
    private String awayTeam;

    @JsonProperty("match_date")
    @JsonAlias("matchDate")
    private String matchDate;

    @JsonProperty("competition_id")
    @JsonAlias("competitionId")
    private String competitionId;

    @JsonProperty("competition_stage")
    @JsonAlias("competitionStage")
    private String competitionStage;

    @JsonProperty("is_neutral_venue")
    @JsonAlias("isNeutralVenue")
    private boolean isNeutralVenue;

    public MatchPredictionRequest() {
    }

    public String getHomeTeam() {
        return homeTeam;
    }

    public void setHomeTeam(String homeTeam) {
        this.homeTeam = homeTeam;
    }

    public String getAwayTeam() {
        return awayTeam;
    }

    public void setAwayTeam(String awayTeam) {
        this.awayTeam = awayTeam;
    }

    public String getMatchDate() {
        return matchDate;
    }

    public void setMatchDate(String matchDate) {
        this.matchDate = matchDate;
    }

    public String getCompetitionId() {
        return competitionId;
    }

    public void setCompetitionId(String competitionId) {
        this.competitionId = competitionId;
    }

    public String getCompetitionStage() {
        return competitionStage;
    }

    public void setCompetitionStage(String competitionStage) {
        this.competitionStage = competitionStage;
    }

    public boolean isNeutralVenue() {
        return isNeutralVenue;
    }

    public void setNeutralVenue(boolean neutralVenue) {
        this.isNeutralVenue = neutralVenue;
    }
}
