package com.neutralground.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.Map;

/** One published model run. metrics and evaluation hold the pipeline's JSON files verbatim. */
@Entity
@Immutable
@Table(name = "model_runs")
public class ModelRun {

    @Id
    private String id;

    private String kind;

    @Column(name = "trained_through")
    private LocalDate trainedThrough;

    @JdbcTypeCode(SqlTypes.JSON)
    private Map<String, Object> metrics;

    @JdbcTypeCode(SqlTypes.JSON)
    private Map<String, Object> evaluation;

    private String notes;

    @Column(name = "published_at")
    private OffsetDateTime publishedAt;

    protected ModelRun() {
    }

    public String getId() {
        return id;
    }

    public String getKind() {
        return kind;
    }

    public LocalDate getTrainedThrough() {
        return trainedThrough;
    }

    public Map<String, Object> getMetrics() {
        return metrics;
    }

    public Map<String, Object> getEvaluation() {
        return evaluation;
    }

    public String getNotes() {
        return notes;
    }

    public OffsetDateTime getPublishedAt() {
        return publishedAt;
    }
}
