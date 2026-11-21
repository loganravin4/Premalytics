package com.neutralground.inference;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class HttpInferenceClientTest {

    private MockRestServiceServer server;
    private HttpInferenceClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://ml-serve:8000");
        server = MockRestServiceServer.bindTo(builder).build();
        client = new HttpInferenceClient(builder.build());
    }

    @Test
    void postsFixturesAndParsesSnakeCaseResponse() {
        server.expect(requestTo("http://ml-serve:8000/predict/match"))
                .andExpect(method(org.springframework.http.HttpMethod.POST))
                .andExpect(content().json("""
                        {"fixtures":[{"home_team":"BRA","away_team":"ARG","match_date":"2026-06-11",
                          "competition_id":"fifa_world_cup","competition_stage":"group","is_neutral_venue":true}]}
                        """))
                .andRespond(withSuccess("""
                        {"model_run_id":"20260722_002607","score_model_run_id":"score_1",
                         "predictions":[{"home_team":"BRA","away_team":"ARG","p_home_win":0.45,"p_draw":0.28,
                           "p_away_win":0.27,"predicted_home_goals":1,"predicted_away_goals":1,
                           "home_xg":1.4,"away_xg":1.2,"extra":"ignored"}]}
                        """, MediaType.APPLICATION_JSON));

        MatchInferenceResult result = client.predictMatches(List.of(
                new MatchFixture("BRA", "ARG", "2026-06-11", "fifa_world_cup", "group", true)));

        assertThat(result.modelRunId()).isEqualTo("20260722_002607");
        assertThat(result.predictions().get(0).pHomeWin()).isEqualTo(0.45);
        assertThat(result.predictions().get(0).predictedAwayGoals()).isEqualTo(1);
        server.verify();
    }

    @Test
    void serverErrorMeansUnavailable() {
        server.expect(requestTo("http://ml-serve:8000/predict/shot")).andRespond(withStatus(HttpStatus.BAD_GATEWAY));

        assertThatThrownBy(() -> client.predictShot(new ShotFeatures(10, 20, null, null)))
                .isInstanceOfSatisfying(InferenceException.class, e -> assertThat(e.isUnavailable()).isTrue());
    }

    @Test
    void clientErrorMeansRejected() {
        server.expect(requestTo("http://ml-serve:8000/predict/shot"))
                .andRespond(withStatus(HttpStatus.UNPROCESSABLE_ENTITY));

        assertThatThrownBy(() -> client.predictShot(new ShotFeatures(10, 20, null, null)))
                .isInstanceOfSatisfying(InferenceException.class, e -> assertThat(e.isUnavailable()).isFalse());
    }
}
