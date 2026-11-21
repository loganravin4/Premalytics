package com.neutralground.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.neutralground.web.ApiError;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.time.Clock;
import java.time.Duration;

/**
 * Per-client token bucket on POST /api/**. Reads are cached and stay unlimited; POSTs reach the
 * inference service, so they are the expensive path. Keyed on the remote address: behind a proxy,
 * set server.forward-headers-strategy so that address is the real client.
 */
@Component
public class RateLimitFilter extends OncePerRequestFilter {

    private final int capacity;
    private final double tokensPerNano;
    private final Clock clock;
    private final ObjectMapper objectMapper;
    private final Cache<String, Bucket> buckets = Caffeine.newBuilder()
            .maximumSize(100_000)
            .expireAfterAccess(Duration.ofMinutes(10))
            .build();

    @Autowired
    public RateLimitFilter(NeutralGroundProperties properties, ObjectMapper objectMapper) {
        this(properties.rateLimit(), objectMapper, Clock.systemUTC());
    }

    RateLimitFilter(NeutralGroundProperties.RateLimit limit, ObjectMapper objectMapper, Clock clock) {
        this.capacity = limit.capacity();
        this.tokensPerNano = limit.refillPerMinute() / (double) Duration.ofMinutes(1).toNanos();
        this.objectMapper = objectMapper;
        this.clock = clock;
    }

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        return !"POST".equals(request.getMethod()) || !request.getRequestURI().startsWith("/api/");
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        Bucket bucket = buckets.get(request.getRemoteAddr(), key -> new Bucket(capacity, nanos()));
        long waitSeconds = bucket.tryConsume(nanos());
        if (waitSeconds == 0) {
            chain.doFilter(request, response);
            return;
        }
        response.setStatus(HttpStatus.TOO_MANY_REQUESTS.value());
        response.setHeader("Retry-After", Long.toString(waitSeconds));
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        objectMapper.writeValue(response.getOutputStream(), ApiError.of(HttpStatus.TOO_MANY_REQUESTS,
                "Too many prediction requests. Try again in " + waitSeconds + "s.", request.getRequestURI()));
    }

    private long nanos() {
        java.time.Instant now = clock.instant();
        return now.getEpochSecond() * 1_000_000_000L + now.getNano();
    }

    private final class Bucket {
        private double tokens;
        private long updatedAt;

        Bucket(double tokens, long now) {
            this.tokens = tokens;
            this.updatedAt = now;
        }

        /** Returns 0 when a token was taken, else the seconds until one is available. */
        synchronized long tryConsume(long now) {
            tokens = Math.min(capacity, tokens + (now - updatedAt) * tokensPerNano);
            updatedAt = now;
            if (tokens >= 1) {
                tokens -= 1;
                return 0;
            }
            return Math.max(1, (long) Math.ceil((1 - tokens) / tokensPerNano / 1_000_000_000L));
        }
    }
}
