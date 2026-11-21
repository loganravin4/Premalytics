package com.neutralground.service;

import com.neutralground.inference.InferenceException;
import com.neutralground.inference.MatchFixture;
import com.neutralground.inference.MatchInferenceResult;
import com.neutralground.web.dto.PredictionDtos.MatchPredictionRequest;
import com.neutralground.web.dto.PredictionDtos.MatchPredictionResponse;
import com.neutralground.web.dto.PredictionDtos.ShotPredictionRequest;
import com.neutralground.web.dto.PredictionDtos.ShotPredictionResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.LocalDate;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PredictionServiceTest {

    private FakeInferenceClient client;
    private PredictionService service;

    @BeforeEach
    void setUp() {
        client = new FakeInferenceClient();
        service = new PredictionService(client);
    }

    @Test
    void mapsRequestsToFixturesWithDefaults() {
        service.predictMatches(List.of(
                new MatchPredictionRequest("BRA", "ARG", LocalDate.of(2026, 6, 11), null, null, null),
                new MatchPredictionRequest("ESP", "FRA", LocalDate.of(2026, 7, 14), "uefa_euro", "semi_final",
                        false)));

        List<MatchFixture> sent = client.matchCalls.get(0);
        assertThat(sent).containsExactly(
                new MatchFixture("BRA", "ARG", "2026-06-11", "fifa_world_cup", "group", true),
                new MatchFixture("ESP", "FRA", "2026-07-14", "uefa_euro", "semi_final", false));
    }

    @Test
    void mapsInferenceRowsToResponses() {
        List<MatchPredictionResponse> responses = service.predictMatches(List.of(
                new MatchPredictionRequest("BRA", "ARG", LocalDate.of(2026, 6, 11), null, null, null)));

        MatchPredictionResponse r = responses.get(0);
        assertThat(r.homeTeam()).isEqualTo("BRA");
        assertThat(r.pHome()).isEqualTo(0.5);
        assertThat(r.pick()).isEqualTo("H");
        assertThat(r.predictedScore().home()).isEqualTo(2);
        assertThat(r.predictedScore().away()).isEqualTo(1);
        assertThat(r.modelRunId()).isEqualTo("run-1");
    }

    @Test
    void omitsScoreWhenInferenceHasNone() {
        client.matchAnswer = fixtures -> new MatchInferenceResult("run-1", null, List.of(
                new MatchInferenceResult.Row("BRA", "ARG", 0.2, 0.3, 0.5, null, null, null, null)));

        MatchPredictionResponse r = service.predictMatches(List.of(
                new MatchPredictionRequest("BRA", "ARG", LocalDate.of(2026, 6, 11), null, null, null))).get(0);

        assertThat(r.predictedScore()).isNull();
        assertThat(r.pick()).isEqualTo("A");
    }

    @Test
    void rejectsMismatchedRowCount() {
        client.matchAnswer = fixtures -> new MatchInferenceResult("run-1", null, List.of());

        assertThatThrownBy(() -> service.predictMatches(List.of(
                new MatchPredictionRequest("BRA", "ARG", LocalDate.of(2026, 6, 11), null, null, null))))
                .isInstanceOf(InferenceException.class)
                .hasMessageContaining("0 predictions for 1 fixtures");
    }

    @Test
    void rejectsRowsOutOfOrder() {
        client.matchAnswer = fixtures -> new MatchInferenceResult("run-1", null, List.of(
                new MatchInferenceResult.Row("ARG", "BRA", 0.2, 0.3, 0.5, null, null, null, null)));

        assertThatThrownBy(() -> service.predictMatches(List.of(
                new MatchPredictionRequest("BRA", "ARG", LocalDate.of(2026, 6, 11), null, null, null))))
                .isInstanceOf(InferenceException.class);
    }

    @Test
    void predictsShot() {
        ShotPredictionResponse r = service.predictShot(new ShotPredictionRequest(14.2, 22.5, "foot", null));

        assertThat(r.pGoal()).isEqualTo(0.12);
        assertThat(r.modelRunId()).isEqualTo("shot-run");
        assertThat(client.shotCalls.get(0).bodyPart()).isEqualTo("foot");
        assertThat(client.shotCalls.get(0).situation()).isNull();
    }
}
