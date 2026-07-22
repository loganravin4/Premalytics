package com.premalytics.dto;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Outbound match-prediction result. Deserialized from the Python predict CLI's
 * stdout JSON (snake_case) and serialized back to the frontend in the same shape.
 *
 * The p* getters (getPHomeWin/getPDraw/getPAwayWin) are @JsonIgnore'd so Jackson
 * emits only the snake_case field keys, not getter-derived "phomeWin" duplicates.
 * The string getters (getHomeTeam/getAwayTeam) link cleanly to their fields and
 * need no annotation.
 */
public class MatchPredictionResponse {

    @JsonProperty("home_team")
    private String homeTeam;

    @JsonProperty("away_team")
    private String awayTeam;

    @JsonProperty("p_home_win")
    private double pHomeWin;

    @JsonProperty("p_draw")
    private double pDraw;

    @JsonProperty("p_away_win")
    private double pAwayWin;

    public MatchPredictionResponse() {
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

    @JsonIgnore
    public double getPHomeWin() {
        return pHomeWin;
    }

    public void setPHomeWin(double pHomeWin) {
        this.pHomeWin = pHomeWin;
    }

    @JsonIgnore
    public double getPDraw() {
        return pDraw;
    }

    public void setPDraw(double pDraw) {
        this.pDraw = pDraw;
    }

    @JsonIgnore
    public double getPAwayWin() {
        return pAwayWin;
    }

    public void setPAwayWin(double pAwayWin) {
        this.pAwayWin = pAwayWin;
    }
}
