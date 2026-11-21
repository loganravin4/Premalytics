package com.neutralground.config;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

import java.net.URI;
import java.time.Duration;
import java.util.List;

/** Typed view of the {@code neutralground.*} settings in application.yml. */
@Validated
@ConfigurationProperties("neutralground")
public record NeutralGroundProperties(
        @Valid @NotNull Cors cors,
        @Valid @NotNull Inference inference,
        @Valid @NotNull RateLimit rateLimit,
        @Valid @NotNull ReadCache readCache) {

    public record Cors(@NotEmpty List<String> allowedOrigins) {
    }

    public record Inference(@NotNull URI baseUrl, @NotNull Duration connectTimeout, @NotNull Duration readTimeout) {
    }

    public record RateLimit(@Min(1) int capacity, @Min(1) int refillPerMinute) {
    }

    public record ReadCache(@NotNull Duration maxAge) {
    }
}
