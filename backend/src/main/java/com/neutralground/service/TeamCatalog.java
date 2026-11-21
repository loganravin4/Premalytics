package com.neutralground.service;

import com.neutralground.config.CacheConfig;
import com.neutralground.repository.TeamRepository;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

/** Team code lookups used by request validation. */
@Service
public class TeamCatalog {

    private final TeamRepository teamRepository;

    public TeamCatalog(TeamRepository teamRepository) {
        this.teamRepository = teamRepository;
    }

    @Cacheable(CacheConfig.TEAM_EXISTS)
    public boolean exists(String code) {
        return teamRepository.existsById(code);
    }
}
