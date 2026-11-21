package com.neutralground;

import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.web.servlet.MockMvc;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * Full stack against a real Postgres: Flyway migrations on a fresh database, Hibernate schema
 * validation, and every read endpoint over seeded data. Skipped when Docker is not available.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Testcontainers(disabledWithoutDocker = true)
@Sql(scripts = "/seed/read-api.sql", executionPhase = Sql.ExecutionPhase.BEFORE_TEST_CLASS)
class ReadApiIntegrationTest {

    @Container
    @ServiceConnection
    static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>("postgres:17-alpine");

    @Autowired
    MockMvc mvc;

    @Autowired
    Flyway flyway;

    @Test
    void migrationsApplyOnFreshDatabase() {
        assertThat(flyway.info().applied()).isNotEmpty();
        assertThat(flyway.info().pending()).isEmpty();
        assertThat(flyway.getConfiguration().getDefaultSchema()).isEqualTo("ng");
    }

    @Test
    void listsTournaments() throws Exception {
        mvc.perform(get("/api/tournaments"))
                .andExpect(status().isOk())
                .andExpect(header().string("Cache-Control", "max-age=300, public"))
                .andExpect(jsonPath("$[0].id").value("wc2026"))
                .andExpect(jsonPath("$[0].matchCount").value(4))
                .andExpect(jsonPath("$[0].playedCount").value(3));
    }

    @Test
    void tournamentDetailScoresLatestRunShootoutCredited() throws Exception {
        // BRA-ARG: picked H, won 2-1 (correct). ESP-CPV: picked H, 0-0 (miss).
        // SUI-COL: picked H, 0-0 and SUI won on penalties (credited correct). Final unplayed.
        mvc.perform(get("/api/tournaments/wc2026"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.modelRunId").value("20260722_002607"))
                .andExpect(jsonPath("$.record.scored").value(3))
                .andExpect(jsonPath("$.record.correct").value(2))
                .andExpect(jsonPath("$.stages[0].stage").value("group"))
                .andExpect(jsonPath("$.stages[0].record.correct").value(1))
                .andExpect(jsonPath("$.stages[1].stage").value("round_of_16"))
                .andExpect(jsonPath("$.stages[2].stage").value("final"))
                .andExpect(jsonPath("$.stages[2].played").value(0));
    }

    @Test
    void unknownTournamentIs404() throws Exception {
        mvc.perform(get("/api/tournaments/euro2028"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.message").value("Tournament not found: euro2028"));
        mvc.perform(get("/api/tournaments/euro2028/matches")).andExpect(status().isNotFound());
    }

    @Test
    void pagesTournamentMatchesAndFiltersByStage() throws Exception {
        mvc.perform(get("/api/tournaments/wc2026/matches").param("size", "2").param("page", "1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(2))
                .andExpect(jsonPath("$.items[0].matchNumber").value(3))
                .andExpect(jsonPath("$.totalItems").value(4))
                .andExpect(jsonPath("$.totalPages").value(2));

        mvc.perform(get("/api/tournaments/wc2026/matches").param("stage", "round_of_16"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items.length()").value(1))
                .andExpect(jsonPath("$.items[0].homeTeam.name").value("Switzerland"))
                .andExpect(jsonPath("$.items[0].result.outcome").value("D"))
                .andExpect(jsonPath("$.items[0].result.winner").value("SUI"))
                .andExpect(jsonPath("$.items[0].result.decidedOnPenalties").value(true))
                .andExpect(jsonPath("$.items[0].prediction.pDraw").value(0.0))
                .andExpect(jsonPath("$.items[0].prediction.correct").value(true));
    }

    @Test
    void matchDetailUsesNewestRunAndKeepsHistory() throws Exception {
        mvc.perform(get("/api/matches/1"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.tournamentName").value("FIFA World Cup 2026"))
                .andExpect(jsonPath("$.result.homeGoals").value(2))
                .andExpect(jsonPath("$.prediction.modelRunId").value("20260722_002607"))
                .andExpect(jsonPath("$.prediction.predictedScore.home").value(1))
                .andExpect(jsonPath("$.prediction.homeXg").value(1.31))
                .andExpect(jsonPath("$.predictionHistory.length()").value(2))
                .andExpect(jsonPath("$.predictionHistory[1].modelRunId").value("old_run"))
                .andExpect(jsonPath("$.predictionHistory[1].correct").value(false));

        mvc.perform(get("/api/matches/4"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.result").doesNotExist())
                .andExpect(jsonPath("$.prediction.correct").doesNotExist());

        mvc.perform(get("/api/matches/999")).andExpect(status().isNotFound());
    }

    @Test
    void listsAndFiltersTeams() throws Exception {
        mvc.perform(get("/api/teams").param("size", "2"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].name").value("Argentina"))
                .andExpect(jsonPath("$.totalItems").value(6));

        mvc.perform(get("/api/teams").param("confederation", "UEFA"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalItems").value(2));
    }

    @Test
    void teamDetailHasEloHistoryResultsAndPredictions() throws Exception {
        mvc.perform(get("/api/teams/BRA"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.confederation").value("CONMEBOL"))
                .andExpect(jsonPath("$.currentElo").value(1990.5))
                .andExpect(jsonPath("$.eloHistory.length()").value(2))
                .andExpect(jsonPath("$.matches[0].awayTeam.code").value("ARG"))
                .andExpect(jsonPath("$.record.correct").value(1));

        mvc.perform(get("/api/teams/BRA").param("eloSince", "2000-01-01"))
                .andExpect(jsonPath("$.eloHistory.length()").value(3));

        mvc.perform(get("/api/teams/ZZZ")).andExpect(status().isNotFound());
    }

    @Test
    void latestModelRunScorecard() throws Exception {
        mvc.perform(get("/api/model-runs/latest"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value("20260722_002607"))
                .andExpect(jsonPath("$.metrics.n_features").value(123))
                .andExpect(jsonPath("$.evaluation.overall.correct").value(72));

        mvc.perform(get("/api/model-runs/latest").param("kind", "shot_xg"))
                .andExpect(jsonPath("$.id").value("shot_xg_20260628_010155"));

        mvc.perform(get("/api/model-runs/latest").param("kind", "penalty")).andExpect(status().isNotFound());
        mvc.perform(get("/api/model-runs/old_run")).andExpect(jsonPath("$.metrics.n_train").value(100));
    }

    @Test
    void xgGridAndPenaltyAggregates() throws Exception {
        mvc.perform(get("/api/xg/grid"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.modelRunId").value("shot_xg_20260628_010155"))
                .andExpect(jsonPath("$.cells.length()").value(2))
                .andExpect(jsonPath("$.cells[0].pGoal").value(0.42));

        mvc.perform(get("/api/penalties/aggregates").param("dimension", "zone"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(2))
                .andExpect(jsonPath("$[0].bucket").value("bottom_center"));
    }

    @Test
    void etagSupportsConditionalGet() throws Exception {
        String etag = mvc.perform(get("/api/teams"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getHeader("ETag");
        assertThat(etag).isNotBlank();

        mvc.perform(get("/api/teams").header("If-None-Match", etag))
                .andExpect(status().isNotModified());
    }

    @Test
    void healthAndOpenApi() throws Exception {
        mvc.perform(get("/actuator/health/readiness"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"));
        mvc.perform(get("/actuator/health/liveness")).andExpect(status().isOk());

        mvc.perform(get("/api/docs"))
                .andExpect(status().isOk())
                .andExpect(content().string(containsString("/api/tournaments/{id}/matches")))
                .andExpect(content().string(containsString("Neutral Ground API")));
    }
}
