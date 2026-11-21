package com.neutralground.web;

import org.springframework.http.HttpStatus;

import java.time.Instant;
import java.util.List;

/** The one error body every endpoint returns. fieldErrors is empty unless validation failed. */
public record ApiError(int status, String error, String message, String path, Instant timestamp,
                       List<FieldError> fieldErrors) {

    public record FieldError(String field, String message) {
    }

    public static ApiError of(HttpStatus status, String message, String path) {
        return new ApiError(status.value(), status.getReasonPhrase(), message, path, Instant.now(), List.of());
    }

    public static ApiError validation(String path, List<FieldError> fieldErrors) {
        HttpStatus status = HttpStatus.BAD_REQUEST;
        return new ApiError(status.value(), status.getReasonPhrase(), "Request validation failed", path,
                Instant.now(), fieldErrors);
    }
}
