package com.neutralground.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

@Entity
@Immutable
@Table(name = "predictions")
public class Prediction {

    @Id
    private Long id;

    @Column(name = "model_run_id")
    private String modelRunId;

    @Column(name = "match_id")
    private Long matchId;

    @Column(name = "p_home")
    private double pHome;

    @Column(name = "p_draw")
    private double pDraw;

    @Column(name = "p_away")
    private double pAway;

    @Column(name = "predicted_home_goals")
    private Integer predictedHomeGoals;

    @Column(name = "predicted_away_goals")
    private Integer predictedAwayGoals;

    @Column(name = "home_xg")
    private Double homeXg;

    @Column(name = "away_xg")
    private Double awayXg;

    @Column(name = "score_model_run_id")
    private String scoreModelRunId;

    protected Prediction() {
    }

    public Long getId() {
        return id;
    }

    public String getModelRunId() {
        return modelRunId;
    }

    public Long getMatchId() {
        return matchId;
    }

    public double getPHome() {
        return pHome;
    }

    public double getPDraw() {
        return pDraw;
    }

    public double getPAway() {
        return pAway;
    }

    public Integer getPredictedHomeGoals() {
        return predictedHomeGoals;
    }

    public Integer getPredictedAwayGoals() {
        return predictedAwayGoals;
    }

    public Double getHomeXg() {
        return homeXg;
    }

    public Double getAwayXg() {
        return awayXg;
    }

    public String getScoreModelRunId() {
        return scoreModelRunId;
    }
}
