package com.neutralground.inference;

/**
 * The inference service failed. unavailable=true means it could not be reached, timed out, or
 * returned 5xx (HTTP 503 to our caller); false means it rejected the input (HTTP 422).
 */
public class InferenceException extends RuntimeException {

    private final boolean unavailable;

    public InferenceException(String message, boolean unavailable, Throwable cause) {
        super(message, cause);
        this.unavailable = unavailable;
    }

    public boolean isUnavailable() {
        return unavailable;
    }
}
