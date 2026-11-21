package com.neutralground.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

/** Penalty conversion for one bucket of one dimension (e.g. dimension=zone, bucket=top_left). */
@Entity
@Immutable
@Table(name = "penalty_aggregates")
public class PenaltyAggregate {

    @Id
    private Long id;

    private String dataset;

    private String dimension;

    private String bucket;

    private int kicks;

    private int goals;

    private double conversion;

    protected PenaltyAggregate() {
    }

    public String getDataset() {
        return dataset;
    }

    public String getDimension() {
        return dimension;
    }

    public String getBucket() {
        return bucket;
    }

    public int getKicks() {
        return kicks;
    }

    public int getGoals() {
        return goals;
    }

    public double getConversion() {
        return conversion;
    }
}
