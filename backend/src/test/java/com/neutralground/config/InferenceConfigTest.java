package com.neutralground.config;

import com.neutralground.inference.HttpInferenceClient;
import com.neutralground.inference.InferenceException;
import com.neutralground.inference.ShotFeatures;
import com.neutralground.inference.ShotInferenceResult;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.RestClient;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** The real RestClient wiring against a real socket: protocol version, body delivery, read timeout. */
class InferenceConfigTest {

    private HttpServer server;
    private final AtomicReference<String> received = new AtomicReference<>();
    private final AtomicReference<String> protocol = new AtomicReference<>();
    private final AtomicReference<String> upgrade = new AtomicReference<>();

    @BeforeEach
    void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/predict/shot", exchange -> {
            protocol.set(exchange.getProtocol());
            upgrade.set(exchange.getRequestHeaders().getFirst("Upgrade"));
            received.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            byte[] body = """
                    {"p_goal":0.2,"model":"shot_xg_logistic","model_run_id":"r","distance_m":11.0,"angle_deg":0.0}
                    """.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.createContext("/slow", exchange -> {
            try {
                Thread.sleep(2_000);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            exchange.sendResponseHeaders(200, -1);
            exchange.close();
        });
        server.start();
    }

    @AfterEach
    void stop() {
        server.stop(0);
    }

    private RestClient client(Duration readTimeout) {
        NeutralGroundProperties.Inference inference = new NeutralGroundProperties.Inference(
                URI.create("http://127.0.0.1:" + server.getAddress().getPort()), Duration.ofSeconds(1), readTimeout);
        return new InferenceConfig().inferenceRestClient(RestClient.builder(),
                new NeutralGroundProperties(null, inference, null, null));
    }

    @Test
    void sendsJsonBodyOverHttp11() {
        ShotInferenceResult result = new HttpInferenceClient(client(Duration.ofSeconds(2)))
                .predictShot(new ShotFeatures(11, 0, null, null));

        assertThat(protocol.get()).isEqualTo("HTTP/1.1");
        assertThat(upgrade.get()).as("no h2c upgrade, which uvicorn drops the body on").isNull();
        assertThat(received.get()).isEqualTo("{\"distance_m\":11.0,\"angle_deg\":0.0}");
        assertThat(result.pGoal()).isEqualTo(0.2);
    }

    @Test
    void readTimeoutSurfacesAsUnavailable() {
        RestClient slow = client(Duration.ofMillis(200));
        assertThatThrownBy(() -> slow.get().uri("/slow").retrieve().toBodilessEntity())
                .isInstanceOf(org.springframework.web.client.ResourceAccessException.class);

        HttpInferenceClient inference = new HttpInferenceClient(slow.mutate().baseUrl(
                "http://127.0.0.1:" + server.getAddress().getPort() + "/slow").build());
        assertThatThrownBy(() -> inference.predictShot(new ShotFeatures(1, 1, null, null)))
                .isInstanceOfSatisfying(InferenceException.class, e -> assertThat(e.isUnavailable()).isTrue());
    }
}
