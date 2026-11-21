package com.neutralground.web;

import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.exc.InvalidFormatException;
import com.neutralground.inference.InferenceException;
import com.neutralground.service.NotFoundException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.List;
import java.util.stream.Collectors;

/** Maps every failure to {@link ApiError}. Messages are written for API clients; no stack traces leak. */
@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(MethodArgumentNotValidException.class)
    ResponseEntity<ApiError> invalidBody(MethodArgumentNotValidException e, HttpServletRequest request) {
        List<ApiError.FieldError> fields = e.getBindingResult().getFieldErrors().stream()
                .map(f -> new ApiError.FieldError(f.getField(), f.getDefaultMessage()))
                .toList();
        List<ApiError.FieldError> global = e.getBindingResult().getGlobalErrors().stream()
                .map(g -> new ApiError.FieldError(g.getObjectName(), g.getDefaultMessage()))
                .toList();
        return respond(ApiError.validation(request.getRequestURI(),
                java.util.stream.Stream.concat(fields.stream(), global.stream()).toList()));
    }

    @ExceptionHandler(HandlerMethodValidationException.class)
    ResponseEntity<ApiError> invalidParameters(HandlerMethodValidationException e, HttpServletRequest request) {
        List<ApiError.FieldError> fields = e.getParameterValidationResults().stream()
                .flatMap(result -> result.getResolvableErrors().stream()
                        .map(err -> new ApiError.FieldError(result.getMethodParameter().getParameterName(),
                                err.getDefaultMessage())))
                .toList();
        return respond(ApiError.validation(request.getRequestURI(), fields));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    ResponseEntity<ApiError> constraintViolation(ConstraintViolationException e, HttpServletRequest request) {
        List<ApiError.FieldError> fields = e.getConstraintViolations().stream()
                .map(v -> new ApiError.FieldError(lastNode(v.getPropertyPath().toString()), v.getMessage()))
                .toList();
        return respond(ApiError.validation(request.getRequestURI(), fields));
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    ResponseEntity<ApiError> unreadable(HttpMessageNotReadableException e, HttpServletRequest request) {
        if (e.getCause() instanceof InvalidFormatException ife) {
            String message = ife.getTargetType() == java.time.LocalDate.class
                    ? "must be a date in yyyy-MM-dd format"
                    : "has an invalid value";
            return respond(ApiError.validation(request.getRequestURI(),
                    List.of(new ApiError.FieldError(path(ife), message))));
        }
        if (e.getCause() instanceof JsonMappingException jme && !jme.getPath().isEmpty()) {
            return respond(ApiError.validation(request.getRequestURI(),
                    List.of(new ApiError.FieldError(path(jme), "has an invalid value"))));
        }
        return respond(ApiError.of(HttpStatus.BAD_REQUEST, "Malformed JSON request body", request.getRequestURI()));
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    ResponseEntity<ApiError> typeMismatch(MethodArgumentTypeMismatchException e, HttpServletRequest request) {
        return respond(ApiError.validation(request.getRequestURI(),
                List.of(new ApiError.FieldError(e.getName(), "has an invalid value"))));
    }

    @ExceptionHandler(MissingServletRequestParameterException.class)
    ResponseEntity<ApiError> missingParameter(MissingServletRequestParameterException e,
                                              HttpServletRequest request) {
        return respond(ApiError.validation(request.getRequestURI(),
                List.of(new ApiError.FieldError(e.getParameterName(), "is required"))));
    }

    @ExceptionHandler(NotFoundException.class)
    ResponseEntity<ApiError> notFound(NotFoundException e, HttpServletRequest request) {
        return respond(ApiError.of(HttpStatus.NOT_FOUND, e.getMessage(), request.getRequestURI()));
    }

    @ExceptionHandler(NoResourceFoundException.class)
    ResponseEntity<ApiError> noRoute(NoResourceFoundException e, HttpServletRequest request) {
        return respond(ApiError.of(HttpStatus.NOT_FOUND, "No such endpoint", request.getRequestURI()));
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    ResponseEntity<ApiError> methodNotAllowed(HttpRequestMethodNotSupportedException e,
                                              HttpServletRequest request) {
        return respond(ApiError.of(HttpStatus.METHOD_NOT_ALLOWED, "Method " + e.getMethod() + " is not allowed",
                request.getRequestURI()));
    }

    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    ResponseEntity<ApiError> unsupportedMediaType(HttpMediaTypeNotSupportedException e,
                                                  HttpServletRequest request) {
        return respond(ApiError.of(HttpStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json",
                request.getRequestURI()));
    }

    @ExceptionHandler(InferenceException.class)
    ResponseEntity<ApiError> inference(InferenceException e, HttpServletRequest request) {
        HttpStatus status = e.isUnavailable() ? HttpStatus.SERVICE_UNAVAILABLE : HttpStatus.UNPROCESSABLE_ENTITY;
        return respond(ApiError.of(status, e.getMessage(), request.getRequestURI()));
    }

    @ExceptionHandler(Exception.class)
    ResponseEntity<ApiError> unexpected(Exception e, HttpServletRequest request) {
        log.error("Unhandled error on {} {}", request.getMethod(), request.getRequestURI(), e);
        return respond(ApiError.of(HttpStatus.INTERNAL_SERVER_ERROR, "Internal server error",
                request.getRequestURI()));
    }

    private static ResponseEntity<ApiError> respond(ApiError error) {
        return ResponseEntity.status(error.status()).body(error);
    }

    private static String path(JsonMappingException e) {
        return e.getPath().stream()
                .map(ref -> ref.getFieldName() != null ? ref.getFieldName() : "[" + ref.getIndex() + "]")
                .collect(Collectors.joining("."))
                .replace(".[", "[");
    }

    private static String lastNode(String propertyPath) {
        int dot = propertyPath.lastIndexOf('.');
        return dot < 0 ? propertyPath : propertyPath.substring(dot + 1);
    }
}
