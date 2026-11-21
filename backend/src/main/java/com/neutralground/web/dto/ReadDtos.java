package com.neutralground.web.dto;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;

/** backend/API.md documents each of these shapes, so keep the two in sync. */
public final class ReadDtos {

    private ReadDtos() {
    }

    public record TeamRef(String code, String name) {
    }

    public record TeamSummary(String code, String name, String confederation) {
    }

    /** outcome is by goals after extra time, so a shootout is "D" with winner set. */
    public record MatchResult(int homeGoals, int awayGoals, String outcome, String winner,
                              boolean decidedOnPenalties) {
    }

    public record PredictedScore(int home, int away) {
    }

    /** correct is null when unplayed; a knockout decided on penalties is scored for the team that advanced. */
    public record MatchPrediction(String modelRunId, double pHome, double pDraw, double pAway, String pick,
                                  PredictedScore predictedScore, Double homeXg, Double awayXg, Boolean correct) {
    }

    public record MatchSummary(long id, String tournamentId, int matchNumber, LocalDate date, String stage,
                               TeamRef homeTeam, TeamRef awayTeam, boolean neutralVenue,
                               MatchResult result, MatchPrediction prediction) {
    }

    /** prediction is from the newest published run; predictionHistory has every run, newest first. */
    public record MatchDetail(long id, String tournamentId, String tournamentName, int matchNumber, LocalDate date,
                              String stage, TeamRef homeTeam, TeamRef awayTeam, boolean neutralVenue,
                              MatchResult result, MatchPrediction prediction,
                              List<MatchPrediction> predictionHistory) {
    }

    public record ModelRecord(int scored, int correct, Double accuracy) {

        public static ModelRecord of(int scored, int correct) {
            return new ModelRecord(scored, correct,
                    scored == 0 ? null : Math.round(correct * 10_000.0 / scored) / 10_000.0);
        }
    }

    public record StageSummary(String stage, int matches, int played, ModelRecord record) {
    }

    public record TournamentSummary(String id, String name, String competitionId, int year, String hosts,
                                    LocalDate startDate, LocalDate endDate, int matchCount, int playedCount) {
    }

    public record TournamentDetail(String id, String name, String competitionId, int year, String hosts,
                                   LocalDate startDate, LocalDate endDate, int matchCount, int playedCount,
                                   String modelRunId, ModelRecord record, List<StageSummary> stages) {
    }

    public record EloPoint(LocalDate date, double elo) {
    }

    public record TeamDetail(String code, String name, String confederation, Double currentElo,
                             List<EloPoint> eloHistory, ModelRecord record, List<MatchSummary> matches) {
    }

    public record ModelRunView(String id, String kind, LocalDate trainedThrough, OffsetDateTime publishedAt,
                               Map<String, Object> metrics, Map<String, Object> evaluation, String notes) {
    }

    public record XgCell(double distanceM, double angleDeg, String bodyPart, String situation, double pGoal) {
    }

    public record XgGrid(String modelRunId, List<XgCell> cells) {
    }

    public record PenaltyAggregateView(String dataset, String dimension, String bucket, int kicks, int goals,
                                       double conversion) {
    }
}
