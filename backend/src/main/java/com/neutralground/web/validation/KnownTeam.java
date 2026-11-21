package com.neutralground.web.validation;

import jakarta.validation.Constraint;
import jakarta.validation.Payload;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/** A three-letter uppercase team code (^[A-Z]{3}$) that exists in the teams table. Null is valid. */
@Documented
@Constraint(validatedBy = KnownTeamValidator.class)
@Target({ElementType.FIELD, ElementType.PARAMETER, ElementType.RECORD_COMPONENT, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
public @interface KnownTeam {

    String message() default "must be a known three-letter team code, e.g. BRA";

    Class<?>[] groups() default {};

    Class<? extends Payload>[] payload() default {};
}
