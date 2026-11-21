package com.neutralground.config;

import org.springframework.cache.annotation.EnableCaching;
import org.springframework.context.annotation.Configuration;

/**
 * Turns on the Caffeine cache behind the read services (spec in spring.cache.caffeine.spec).
 * Kept out of the application class so MVC slice tests do not need a CacheManager.
 */
@Configuration
@EnableCaching
public class CacheConfig {

    public static final String TOURNAMENTS = "tournaments";
    public static final String TOURNAMENT = "tournament";
    public static final String TOURNAMENT_MATCHES = "tournamentMatches";
    public static final String MATCH = "match";
    public static final String TEAMS = "teams";
    public static final String TEAM = "team";
    public static final String TEAM_EXISTS = "teamExists";
    public static final String MODEL_RUNS = "modelRuns";
    public static final String XG_GRID = "xgGrid";
    public static final String PENALTIES = "penalties";
}
