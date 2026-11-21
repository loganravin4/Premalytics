package com.neutralground.web;

import com.neutralground.inference.InferenceException;
import com.neutralground.service.PredictionService;
import com.neutralground.service.TeamCatalog;
import com.neutralground.web.dto.PredictionDtos.MatchPredictionResponse;
import com.neutralground.web.dto.PredictionDtos.ShotPredictionResponse;
import com.neutralground.web.dto.ReadDtos.PredictedScore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasItem;
import static org.hamcrest.Matchers.not;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(PredictionController.class)
class PredictionControllerTest {

    @Autowired
    MockMvc mvc;

    @MockitoBean
    PredictionService predictionService;

    @MockitoBean
    TeamCatalog teamCatalog;

    @BeforeEach
    void knownTeams() {
        when(teamCatalog.exists(anyString())).thenAnswer(inv -> List.of("BRA", "ARG", "ESP").contains(inv.getArgument(0)));
    }

    @Test
    void predictsMatches() throws Exception {
        when(predictionService.predictMatches(anyList())).thenReturn(List.of(new MatchPredictionResponse(
                "BRA", "ARG", 0.45, 0.28, 0.27, "H", new PredictedScore(1, 0), 1.4, 0.9, "20260722_002607")));

        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("""
                        {"fixtures":[{"homeTeam":"BRA","awayTeam":"ARG","matchDate":"2026-06-11"}]}
                        """))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(jsonPath("$[0].pHome").value(0.45))
                .andExpect(jsonPath("$[0].pick").value("H"))
                .andExpect(jsonPath("$[0].predictedScore.home").value(1))
                .andExpect(jsonPath("$[0].modelRunId").value("20260722_002607"));
    }

    @Test
    void acceptsSnakeCaseAliases() throws Exception {
        when(predictionService.predictMatches(anyList())).thenReturn(List.of());

        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("""
                        {"fixtures":[{"home_team":"BRA","away_team":"ARG","match_date":"2026-06-11",
                          "competition_stage":"final","is_neutral_venue":true}]}
                        """))
                .andExpect(status().isOk());
    }

    @Test
    void rejectsUnknownAndMalformedTeamCodes() throws Exception {
        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("""
                        {"fixtures":[{"homeTeam":"bra","awayTeam":"XYZ","matchDate":"2026-06-11","competitionStage":"semis"}]}
                        """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value(400))
                .andExpect(jsonPath("$.fieldErrors[*].field", hasItem("fixtures[0].homeTeam")))
                .andExpect(jsonPath("$.fieldErrors[*].field", hasItem("fixtures[0].awayTeam")))
                .andExpect(jsonPath("$.fieldErrors[*].field", hasItem("fixtures[0].competitionStage")));
        verifyNoInteractions(predictionService);
    }

    @Test
    void rejectsSameTeamTwice() throws Exception {
        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("""
                        {"fixtures":[{"homeTeam":"BRA","awayTeam":"BRA","matchDate":"2026-06-11"}]}
                        """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors[0].field").value("fixtures[0].distinctTeams"));
    }

    @Test
    void rejectsBadDateWithFieldError() throws Exception {
        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("""
                        {"fixtures":[{"homeTeam":"BRA","awayTeam":"ARG","matchDate":"11/06/2026"}]}
                        """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors[0].field").value("fixtures[0].matchDate"))
                .andExpect(jsonPath("$.fieldErrors[0].message").value("must be a date in yyyy-MM-dd format"));
    }

    @Test
    void rejectsEmptyAndOversizedBatches() throws Exception {
        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("{\"fixtures\":[]}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors[0].field").value("fixtures"));

        String fixture = "{\"homeTeam\":\"BRA\",\"awayTeam\":\"ARG\",\"matchDate\":\"2026-06-11\"}";
        String many = String.join(",", java.util.Collections.nCopies(21, fixture));
        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON)
                        .content("{\"fixtures\":[" + many + "]}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void malformedJsonIsBadRequestWithoutInternals() throws Exception {
        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("{not json"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value("Malformed JSON request body"))
                .andExpect(content().string(not(containsString("Exception"))));
    }

    @Test
    void wrongContentTypeIs415() throws Exception {
        mvc.perform(post("/api/predictions/match").contentType(MediaType.TEXT_PLAIN).content("x"))
                .andExpect(status().isUnsupportedMediaType());
    }

    @Test
    void inferenceOutageIs503() throws Exception {
        when(predictionService.predictMatches(anyList()))
                .thenThrow(new InferenceException("Inference service unavailable", true, null));

        mvc.perform(post("/api/predictions/match").contentType(MediaType.APPLICATION_JSON).content("""
                        {"fixtures":[{"homeTeam":"BRA","awayTeam":"ARG","matchDate":"2026-06-11"}]}
                        """))
                .andExpect(status().isServiceUnavailable())
                .andExpect(jsonPath("$.message").value("Inference service unavailable"));
    }

    @Test
    void unexpectedErrorsDoNotLeakDetails() throws Exception {
        when(predictionService.predictShot(any())).thenThrow(new IllegalStateException("secret db password"));

        mvc.perform(post("/api/predictions/shot").contentType(MediaType.APPLICATION_JSON).content("""
                        {"distanceM":14.2,"angleDeg":22.5}
                        """))
                .andExpect(status().isInternalServerError())
                .andExpect(jsonPath("$.message").value("Internal server error"))
                .andExpect(content().string(not(containsString("secret"))));
    }

    @Test
    void predictsShot() throws Exception {
        when(predictionService.predictShot(any()))
                .thenReturn(new ShotPredictionResponse(0.1, "shot_xg_logistic", "shot_run", 14.2, 22.5));

        mvc.perform(post("/api/predictions/shot").contentType(MediaType.APPLICATION_JSON).content("""
                        {"distance_m":14.2,"angle_deg":22.5}
                        """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.pGoal").value(0.1))
                .andExpect(jsonPath("$.model").value("shot_xg_logistic"));
    }

    @Test
    void rejectsOutOfRangeShot() throws Exception {
        mvc.perform(post("/api/predictions/shot").contentType(MediaType.APPLICATION_JSON).content("""
                        {"distanceM":-1,"angleDeg":120}
                        """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors[*].field", hasItem("distanceM")))
                .andExpect(jsonPath("$.fieldErrors[*].field", hasItem("angleDeg")));
    }

    @Test
    void getOnPostEndpointIs405() throws Exception {
        mvc.perform(get("/api/predictions/match"))
                .andExpect(status().isMethodNotAllowed());
    }

    @Test
    void corsAllowsConfiguredOriginOnly() throws Exception {
        mvc.perform(options("/api/predictions/match")
                        .header("Origin", "http://localhost:5173")
                        .header("Access-Control-Request-Method", "POST"))
                .andExpect(status().isOk())
                .andExpect(header().string("Access-Control-Allow-Origin", "http://localhost:5173"));

        mvc.perform(options("/api/predictions/match")
                        .header("Origin", "https://evil.example")
                        .header("Access-Control-Request-Method", "POST"))
                .andExpect(status().isForbidden());
    }
}
