package com.neutralground.service;

import com.neutralground.config.CacheConfig;
import com.neutralground.domain.Team;
import com.neutralground.repository.MatchRepository;
import com.neutralground.repository.TeamEloRepository;
import com.neutralground.repository.TeamRepository;
import com.neutralground.web.dto.PageResponse;
import com.neutralground.web.dto.ReadDtos.EloPoint;
import com.neutralground.web.dto.ReadDtos.MatchSummary;
import com.neutralground.web.dto.ReadDtos.TeamDetail;
import com.neutralground.web.dto.ReadDtos.TeamSummary;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.util.List;

@Service
@Transactional(readOnly = true)
public class TeamService {

    private final TeamRepository teamRepository;
    private final TeamEloRepository teamEloRepository;
    private final MatchRepository matchRepository;
    private final MatchAssembler assembler;

    public TeamService(TeamRepository teamRepository, TeamEloRepository teamEloRepository,
                       MatchRepository matchRepository, MatchAssembler assembler) {
        this.teamRepository = teamRepository;
        this.teamEloRepository = teamEloRepository;
        this.matchRepository = matchRepository;
        this.assembler = assembler;
    }

    @Cacheable(CacheConfig.TEAMS)
    public PageResponse<TeamSummary> list(String confederation, int page, int size) {
        PageRequest pageable = PageRequest.of(page, size, Sort.by("name"));
        return PageResponse.of(confederation == null
                        ? teamRepository.findAll(pageable)
                        : teamRepository.findByConfederation(confederation, pageable),
                TeamService::summary);
    }

    @Cacheable(CacheConfig.TEAM)
    public TeamDetail get(String code, LocalDate eloSince) {
        Team team = teamRepository.findById(code)
                .orElseThrow(() -> new NotFoundException("Team not found: " + code));
        List<EloPoint> elo = teamEloRepository
                .findByTeamCodeAndAsOfDateGreaterThanEqualOrderByAsOfDate(code, eloSince)
                .stream()
                .map(e -> new EloPoint(e.getAsOfDate(), e.getElo()))
                .toList();
        List<MatchSummary> matches = assembler.summaries(matchRepository.findByTeam(code));
        return new TeamDetail(team.getCode(), team.getName(), team.getConfederation(),
                elo.isEmpty() ? null : elo.get(elo.size() - 1).elo(), elo, MatchAssembler.record(matches), matches);
    }

    static TeamSummary summary(Team t) {
        return new TeamSummary(t.getCode(), t.getName(), t.getConfederation());
    }
}
