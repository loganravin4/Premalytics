package com.neutralground.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;

import java.net.http.HttpClient;

@Configuration
public class InferenceConfig {

    @Bean
    public RestClient inferenceRestClient(RestClient.Builder builder, NeutralGroundProperties properties) {
        return builder
                .baseUrl(properties.inference().baseUrl().toString())
                .requestFactory(requestFactory(properties.inference()))
                .build();
    }

    /** HTTP/1.1 because the JDK client's h2c upgrade is unsupported by uvicorn and drops the request body. */
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
