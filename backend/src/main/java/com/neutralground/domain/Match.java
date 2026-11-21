package com.neutralground.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

import java.time.LocalDate;

/** A tournament fixture. Result columns are null until the match is played; goals include extra time. */
@Entity
@Immutable
@Table(name = "matches")
public class Match {

    @Id
    private Long id;

    @Column(name = "tournament_id")
    private String tournamentId;

    @Column(name = "match_number")
    private int matchNumber;

    @Column(name = "match_date")
    private LocalDate matchDate;

    private String stage;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "home_team")
    private Team homeTeam;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "away_team")
    private Team awayTeam;

    @Column(name = "neutral_venue")
    private boolean neutralVenue;

    @Column(name = "home_goals")
    private Integer homeGoals;

    @Column(name = "away_goals")
    private Integer awayGoals;

    @Column(name = "winner")
    private String winnerCode;

    @Column(name = "decided_on_penalties")
    private boolean decidedOnPenalties;

    protected Match() {
    }

    public Long getId() {
        return id;
    }

    public String getTournamentId() {
        return tournamentId;
    }

    public int getMatchNumber() {
        return matchNumber;
    }

    public LocalDate getMatchDate() {
        return matchDate;
    }

    public String getStage() {
        return stage;
    }

    public Team getHomeTeam() {
        return homeTeam;
    }

    public Team getAwayTeam() {
        return awayTeam;
    }

    public boolean isNeutralVenue() {
        return neutralVenue;
    }

    public Integer getHomeGoals() {
        return homeGoals;
    }

    public Integer getAwayGoals() {
        return awayGoals;
    }

    public String getWinnerCode() {
        return winnerCode;
    }

    public boolean isDecidedOnPenalties() {
        return decidedOnPenalties;
    }

    public boolean isPlayed() {
        return homeGoals != null && awayGoals != null;
    }
}
