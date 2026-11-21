package com.neutralground.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

/** One cell of the precomputed shot xG grid (distance x angle x body part x situation). */
@Entity
@Immutable
@Table(name = "shots_xg_grid")
public class XgGridCell {

    @Id
    private Long id;

    @Column(name = "model_run_id")
    private String modelRunId;

    @Column(name = "distance_m")
    private double distanceM;

    @Column(name = "angle_deg")
    private double angleDeg;

    @Column(name = "body_part")
    private String bodyPart;

    private String situation;

    @Column(name = "p_goal")
    private double pGoal;

    protected XgGridCell() {
    }

    public String getModelRunId() {
        return modelRunId;
    }

    public double getDistanceM() {
        return distanceM;
    }

    public double getAngleDeg() {
        return angleDeg;
    }

    public String getBodyPart() {
        return bodyPart;
    }

    public String getSituation() {
        return situation;
    }

    public double getPGoal() {
        return pGoal;
    }
}
