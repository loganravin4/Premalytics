package com.neutralground.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

import java.time.LocalDate;

@Entity
@Immutable
@Table(name = "tournaments")
public class Tournament {

    @Id
    private String id;

    private String name;

    @Column(name = "competition_id")
    private String competitionId;

    @Column(name = "season_year")
    private int seasonYear;

    private String hosts;

    @Column(name = "start_date")
    private LocalDate startDate;

    @Column(name = "end_date")
    private LocalDate endDate;

    protected Tournament() {
    }

    public String getId() {
        return id;
    }

    public String getName() {
        return name;
    }

    public String getCompetitionId() {
        return competitionId;
    }

    public int getSeasonYear() {
        return seasonYear;
    }

    public String getHosts() {
        return hosts;
    }

    public LocalDate getStartDate() {
        return startDate;
    }

    public LocalDate getEndDate() {
        return endDate;
    }
}
