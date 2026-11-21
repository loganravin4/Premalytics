package com.neutralground.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;

/** RestClient for the ml-serve FastAPI app, with connect and read timeouts from configuration. */
@Configuration
public class InferenceConfig {

    @Bean
    public RestClient inferenceRestClient(RestClient.Builder builder, NeutralGroundProperties properties) {
        return builder
                .baseUrl(properties.inference().baseUrl().toString())
                .requestFactory(requestFactory(properties.inference()))
                .build();
    }

    /**
     * HTTP/1.1 on purpose: the JDK client otherwise attempts an h2c upgrade on plain http, which
     * uvicorn does not support, and the request body is lost (ml-serve answers 422 "body missing").
     */
    static JdkClientHttpRequestFactory requestFactory(NeutralGroundProperties.Inference inference) {
        HttpClient httpClient = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .connectTimeout(inference.connectTimeout())
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(httpClient);
        factory.setReadTimeout(inference.readTimeout());
        return factory;
    }
}
