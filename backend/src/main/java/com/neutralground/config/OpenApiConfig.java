package com.neutralground.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI neutralGroundOpenApi() {
        return new OpenAPI().info(new Info()
                .title("Neutral Ground API")
                .version("v1")
                .description("International football predictions, results, and model scorecards. "
                        + "Probabilities are model estimates, not betting advice."));
    }
}
