package com.neutralground.inference;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.HttpServerErrorException;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

@Component
public class HttpInferenceClient implements InferenceClient {

    private static final Logger log = LoggerFactory.getLogger(HttpInferenceClient.class);

    private final RestClient restClient;

    public HttpInferenceClient(RestClient inferenceRestClient) {
        this.restClient = inferenceRestClient;
    }

    @Override
    public MatchInferenceResult predictMatches(List<MatchFixture> fixtures) {
        return call("/predict/match", () -> restClient.post()
                .uri("/predict/match")
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("fixtures", fixtures))
                .retrieve()
                .body(MatchInferenceResult.class));
    }

    @Override
    public ShotInferenceResult predictShot(ShotFeatures shot) {
        return call("/predict/shot", () -> restClient.post()
                .uri("/predict/shot")
                .contentType(MediaType.APPLICATION_JSON)
                .body(shot)
                .retrieve()
                .body(ShotInferenceResult.class));
    }

    private <T> T call(String path, Supplier<T> request) {
        try {
            T body = request.get();
            if (body == null) {
                throw new InferenceException("Empty response from inference service " + path, true, null);
            }
            return body;
        } catch (HttpClientErrorException e) {
            log.warn("Inference service rejected {}: {} {}", path, e.getStatusCode(), e.getResponseBodyAsString());
            throw new InferenceException("The model could not score this input", false, e);
        } catch (HttpServerErrorException | ResourceAccessException e) {
            log.error("Inference service unavailable on {}: {}", path, e.getMessage());
            throw new InferenceException("Inference service unavailable", true, e);
        } catch (RestClientException e) {
            log.error("Inference call {} failed: {}", path, e.getMessage());
            throw new InferenceException("Inference service returned an unreadable response", true, e);
        }
    }
}
