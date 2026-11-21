package com.neutralground.web.dto;

import com.fasterxml.jackson.annotation.JsonAlias;
import com.neutralground.web.validation.KnownTeam;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;
import java.util.List;

public final class PredictionDtos {

    public static final String STAGE_PATTERN =
            "group|round_of_32|round_of_16|quarter_final|semi_final|third_place|final";

    private PredictionDtos() {
    }

    public record MatchPredictionBatch(
            @NotEmpty @Size(max = 20) List<@NotNull @Valid MatchPredictionRequest> fixtures) {
    }

    /** snake_case keys are accepted as aliases so the Python fixture column names also work. */
    public record MatchPredictionRequest(
            @NotNull @KnownTeam @JsonAlias("home_team") String homeTeam,
            @NotNull @KnownTeam @JsonAlias("away_team") String awayTeam,
            @NotNull @Schema(type = "string", format = "date", example = "2026-06-11")
            @JsonAlias("match_date") LocalDate matchDate,
            @Pattern(regexp = "^[a-z][a-z0-9_]{1,39}$") @JsonAlias("competition_id") String competitionId,
            @Pattern(regexp = STAGE_PATTERN) @JsonAlias("competition_stage") String competitionStage,
            @JsonAlias("is_neutral_venue") Boolean neutralVenue) {

        @AssertTrue(message = "homeTeam and awayTeam must differ")
        @Schema(hidden = true)
        public boolean isDistinctTeams() {
            return homeTeam == null || !homeTeam.equals(awayTeam);
        }

        public String competitionIdOrDefault() {
            return competitionId == null ? "fifa_world_cup" : competitionId;
        }

        public String competitionStageOrDefault() {
            return competitionStage == null ? "group" : competitionStage;
        }

        public boolean neutralVenueOrDefault() {
            return neutralVenue == null || neutralVenue;
        }
    }

    public record MatchPredictionResponse(String homeTeam, String awayTeam, double pHome, double pDraw,
                                          double pAway, String pick, ReadDtos.PredictedScore predictedScore,
                                          Double homeXg, Double awayXg, String modelRunId) {
    }

    public record ShotPredictionRequest(
            @NotNull @DecimalMin("0.0") @DecimalMax("120.0") @JsonAlias("distance_m") Double distanceM,
            @NotNull @DecimalMin("0.0") @DecimalMax("90.0") @JsonAlias("angle_deg") Double angleDeg,
            @Pattern(regexp = "^[a-z_]{1,20}$") @JsonAlias("body_part") String bodyPart,
            @Pattern(regexp = "^[a-z_]{1,20}$") String situation) {
    }

    public record ShotPredictionResponse(double pGoal, String model, String modelRunId, double distanceM,
                                         double angleDeg) {
    }
}
