package com.premalytics.dto;

/**
 * Error payload returned on HTTP 500 when a prediction process fails.
 */
public class ErrorResponse {

    private String message;
    private String detail;

    public ErrorResponse() {
    }

    public ErrorResponse(String message, String detail) {
        this.message = message;
        this.detail = detail;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getDetail() {
        return detail;
    }

    public void setDetail(String detail) {
        this.detail = detail;
    }
}
