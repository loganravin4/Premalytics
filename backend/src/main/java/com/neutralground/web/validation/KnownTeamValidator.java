package com.neutralground.web.validation;

import com.neutralground.service.TeamCatalog;
import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;

import java.util.regex.Pattern;

public class KnownTeamValidator implements ConstraintValidator<KnownTeam, String> {

    private static final Pattern CODE = Pattern.compile("^[A-Z]{3}$");

    private final TeamCatalog teamCatalog;

    public KnownTeamValidator(TeamCatalog teamCatalog) {
        this.teamCatalog = teamCatalog;
    }

    @Override
    public boolean isValid(String value, ConstraintValidatorContext context) {
        return value == null || (CODE.matcher(value).matches() && teamCatalog.exists(value));
    }
}
