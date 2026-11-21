package com.neutralground.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.IdClass;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

import java.io.Serializable;
import java.time.LocalDate;
import java.util.Objects;

/** A team's pre-match Elo rating on a date, taken from the match model's feature matrix. */
@Entity
@Immutable
@Table(name = "team_elo")
@IdClass(TeamElo.Key.class)
public class TeamElo {

    @Id
    @Column(name = "team_code")
    private String teamCode;

    @Id
    @Column(name = "as_of_date")
    private LocalDate asOfDate;

    private double elo;

    @Column(name = "model_run_id")
    private String modelRunId;

    protected TeamElo() {
    }

    public String getTeamCode() {
        return teamCode;
    }

    public LocalDate getAsOfDate() {
        return asOfDate;
    }

    public double getElo() {
        return elo;
    }

    public String getModelRunId() {
        return modelRunId;
    }

    public static class Key implements Serializable {
        private String teamCode;
        private LocalDate asOfDate;

        public Key() {
        }

        @Override
        public boolean equals(Object o) {
            return o instanceof Key k && Objects.equals(teamCode, k.teamCode) && Objects.equals(asOfDate, k.asOfDate);
        }

        @Override
        public int hashCode() {
            return Objects.hash(teamCode, asOfDate);
        }
    }
}
