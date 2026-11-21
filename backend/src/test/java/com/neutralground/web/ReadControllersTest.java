package com.neutralground.web;

import com.neutralground.service.LabService;
import com.neutralground.service.MatchService;
import com.neutralground.service.ModelRunService;
import com.neutralground.service.NotFoundException;
import com.neutralground.service.TeamService;
import com.neutralground.service.TournamentService;
import com.neutralground.web.dto.PageResponse;
import com.neutralground.web.dto.ReadDtos.EloPoint;
import com.neutralground.web.dto.ReadDtos.MatchDetail;
import com.neutralground.web.dto.ReadDtos.MatchPrediction;
import com.neutralground.web.dto.ReadDtos.MatchResult;
import com.neutralground.web.dto.ReadDtos.MatchSummary;
import com.neutralground.web.dto.ReadDtos.ModelRecord;
import com.neutralground.web.dto.ReadDtos.ModelRunView;
import com.neutralground.web.dto.ReadDtos.PenaltyAggregateView;
import com.neutralground.web.dto.ReadDtos.StageSummary;
import com.neutralground.web.dto.ReadDtos.TeamDetail;
import com.neutralground.web.dto.ReadDtos.TeamRef;
import com.neutralground.web.dto.ReadDtos.TeamSummary;
import com.neutralground.web.dto.ReadDtos.TournamentDetail;
import com.neutralground.web.dto.ReadDtos.TournamentSummary;
import com.neutralground.web.dto.ReadDtos.XgCell;
import com.neutralground.web.dto.ReadDtos.XgGrid;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest({TournamentController.class, MatchController.class, TeamController.class, ModelRunController.class,
        LabController.class})
class ReadControllersTest {

    private static final TeamRef BRA = new TeamRef("BRA", "Brazil");
    private static final TeamRef ARG = new TeamRef("ARG", "Argentina");
    private static final MatchPrediction PREDICTION =
            new MatchPrediction("run-1", 0.5, 0.3, 0.2, "H", null, null, null, true);
    private static final MatchSummary SUMMARY = new MatchSummary(7, "wc2026", 1, LocalDate.of(2026, 6, 11), "group",
            BRA, ARG, true, new MatchResult(2, 1, "H", "BRA", false), PREDICTION);

    @Autowired
    MockMvc mvc;

    @MockitoBean
    TournamentService tournamentService;
    @MockitoBean
    MatchService matchService;
    @MockitoBean
    TeamService teamService;
    @MockitoBean
    ModelRunService modelRunService;
    @MockitoBean
    LabService labService;

    @Test
    void listsTournamentsWithCacheHeaders() throws Exception {
        when(tournamentService.list()).thenReturn(List.of(new TournamentSummary("wc2026", "FIFA World Cup 2026",
                "fifa_world_cup", 2026, "Canada, Mexico, United States", LocalDate.of(2026, 6, 11),
                LocalDate.of(2026, 7, 19), 104, 104)));

        mvc.perform(get("/api/tournaments"))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "max-age=300, public"))
                .andExpect(header().exists("ETag"))
                .andExpect(jsonPath("$[0].id").value("wc2026"))
                .andExpect(jsonPath("$[0].startDate").value("2026-06-11"))
                .andExpect(jsonPath("$[0].matchCount").value(104));
    }

    @Test
    void getsTournament() throws Exception {
        when(tournamentService.get("wc2026")).thenReturn(new TournamentDetail("wc2026", "FIFA World Cup 2026",
                "fifa_world_cup", 2026, null, null, null, 104, 104, "run-1", ModelRecord.of(104, 72),
                List.of(new StageSummary("group", 72, 72, ModelRecord.of(72, 47)))));

        mvc.perform(get("/api/tournaments/wc2026"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.record.accuracy").value(0.6923))
                .andExpect(jsonPath("$.stages[0].record.correct").value(47));
    }

    @Test
    void missingTournamentIs404() throws Exception {
        when(tournamentService.get("nope")).thenThrow(new NotFoundException("Tournament not found: nope"));

        mvc.perform(get("/api/tournaments/nope"))
                .andExpect(status().isNotFound())
                .andExpect(header().string("Cache-Control", "no-store"))
                .andExpect(jsonPath("$.status").value(404))
                .andExpect(jsonPath("$.message").value("Tournament not found: nope"));
    }

    @Test
    void listsTournamentMatchesByStage() throws Exception {
        when(tournamentService.matches("wc2026", "group", 0, 50))
                .thenReturn(new PageResponse<>(List.of(SUMMARY), 0, 50, 1, 1));

        mvc.perform(get("/api/tournaments/wc2026/matches").param("stage", "group"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].homeTeam.code").value("BRA"))
                .andExpect(jsonPath("$.items[0].result.outcome").value("H"))
                .andExpect(jsonPath("$.items[0].prediction.pHome").value(0.5))
                .andExpect(jsonPath("$.items[0].prediction.correct").value(true))
                .andExpect(jsonPath("$.totalItems").value(1));
    }

    @Test
    void rejectsBadStageAndPaging() throws Exception {
        mvc.perform(get("/api/tournaments/wc2026/matches").param("stage", "semis").param("size", "500"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.length()").value(2));
        mvc.perform(get("/api/tournaments/wc2026/matches").param("page", "abc"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors[0].field").value("page"));
        verifyNoInteractions(tournamentService);
    }

    @Test
    void getsMatch() throws Exception {
        when(matchService.get(7)).thenReturn(new MatchDetail(7, "wc2026", "FIFA World Cup 2026", 1,
                LocalDate.of(2026, 6, 11), "group", BRA, ARG, true, null, PREDICTION, List.of(PREDICTION)));

        mvc.perform(get("/api/matches/7"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tournamentName").value("FIFA World Cup 2026"))
                .andExpect(jsonPath("$.result").doesNotExist())
                .andExpect(jsonPath("$.predictionHistory[0].modelRunId").value("run-1"));
    }

    @Test
    void nonNumericMatchIdIs400() throws Exception {
        mvc.perform(get("/api/matches/abc")).andExpect(status().isBadRequest());
    }

    @Test
    void listsTeams() throws Exception {
        when(teamService.list(isNull(), eq(0), eq(50)))
                .thenReturn(new PageResponse<>(List.of(new TeamSummary("BRA", "Brazil", "CONMEBOL")), 0, 50, 1, 1));

        mvc.perform(get("/api/teams"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].confederation").value("CONMEBOL"));
    }

    @Test
    void rejectsUnknownConfederation() throws Exception {
        mvc.perform(get("/api/teams").param("confederation", "MARS"))
                .andExpect(status().isBadRequest());
    }

    @Test
    void getsTeam() throws Exception {
        when(teamService.get("BRA", LocalDate.of(2018, 1, 1))).thenReturn(new TeamDetail("BRA", "Brazil",
                "CONMEBOL", 1990.5, List.of(new EloPoint(LocalDate.of(2026, 6, 13), 1990.5)),
                ModelRecord.of(1, 1), List.of(SUMMARY)));

        mvc.perform(get("/api/teams/BRA"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.currentElo").value(1990.5))
                .andExpect(jsonPath("$.eloHistory[0].date").value("2026-06-13"))
                .andExpect(jsonPath("$.matches[0].id").value(7));
    }

    @Test
    void rejectsLowercaseTeamCode() throws Exception {
        mvc.perform(get("/api/teams/bra"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors[0].field").value("code"));
    }

    @Test
    void getsLatestModelRun() throws Exception {
        when(modelRunService.latest("match")).thenReturn(new ModelRunView("run-1", "match",
                LocalDate.of(2026, 6, 11), OffsetDateTime.of(2026, 7, 23, 0, 0, 0, 0, ZoneOffset.UTC),
                Map.of("n_train", 30417), Map.of("overall", Map.of("accuracy", 0.6923)), null));

        mvc.perform(get("/api/model-runs/latest"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.metrics.n_train").value(30417))
                .andExpect(jsonPath("$.evaluation.overall.accuracy").value(0.6923));
        verify(modelRunService).latest("match");
    }

    @Test
    void getsModelRunById() throws Exception {
        when(modelRunService.get("run-1")).thenReturn(new ModelRunView("run-1", "match", null, null, Map.of(),
                null, null));

        mvc.perform(get("/api/model-runs/run-1")).andExpect(status().isOk()).andExpect(jsonPath("$.id").value("run-1"));
    }

    @Test
    void getsXgGrid() throws Exception {
        when(labService.xgGrid()).thenReturn(new XgGrid("shot-run", List.of(new XgCell(10, 0, "foot", "open_play",
                0.21))));

        mvc.perform(get("/api/xg/grid"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.cells[0].pGoal").value(0.21));
    }

    @Test
    void getsPenaltyAggregates() throws Exception {
        when(labService.penaltyAggregates(isNull(), eq("zone"))).thenReturn(List.of(
                new PenaltyAggregateView("penalty_kicks_v0", "zone", "top_left", 40, 34, 0.85)));

        mvc.perform(get("/api/penalties/aggregates").param("dimension", "zone"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].conversion").value(0.85));
    }

    @Test
    void unknownRouteIs404Json() throws Exception {
        mvc.perform(get("/api/nope"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("No such endpoint"));
    }
}
