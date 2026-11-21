package com.neutralground.inference;

/** unavailable=true means unreachable, timed out, or 5xx (we answer 503); false means it rejected the input (422). */
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
