package com.neutralground.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.hibernate.annotations.Immutable;

/** A national team, keyed by its three-letter code (e.g. BRA). */
@Entity
@Immutable
@Table(name = "teams")
public class Team {

    @Id
    private String code;

    private String name;

    private String confederation;

    protected Team() {
    }

    public String getCode() {
        return code;
    }

    public String getName() {
        return name;
    }

    public String getConfederation() {
        return confederation;
    }
}
