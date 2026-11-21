package com.neutralground.service;

import com.neutralground.config.CacheConfig;
import com.neutralground.domain.Match;
import com.neutralground.domain.Tournament;
import com.neutralground.repository.MatchRepository;
import com.neutralground.repository.TournamentRepository;
import com.neutralground.web.dto.PageResponse;
import com.neutralground.web.dto.ReadDtos.MatchSummary;
import com.neutralground.web.dto.ReadDtos.StageSummary;
import com.neutralground.web.dto.ReadDtos.TournamentDetail;
import com.neutralground.web.dto.ReadDtos.TournamentSummary;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

@Service
@Transactional(readOnly = true)
public class TournamentService {

    /** Display order of stages; unknown stages sort last. */
    public static final List<String> STAGE_ORDER = List.of(
            "group", "round_of_32", "round_of_16", "quarter_final", "semi_final", "third_place", "final");

    private final TournamentRepository tournamentRepository;
    private final MatchRepository matchRepository;
    private final MatchAssembler assembler;

    public TournamentService(TournamentRepository tournamentRepository, MatchRepository matchRepository,
                             MatchAssembler assembler) {
        this.tournamentRepository = tournamentRepository;
        this.matchRepository = matchRepository;
        this.assembler = assembler;
    }

    @Cacheable(CacheConfig.TOURNAMENTS)
    public List<TournamentSummary> list() {
        return tournamentRepository.findAll().stream()
                .sorted(Comparator.comparing(Tournament::getStartDate,
                        Comparator.nullsLast(Comparator.<java.time.LocalDate>naturalOrder())).reversed())
                .map(t -> {
                    List<Match> matches = matchRepository.findByTournamentIdOrderByMatchNumber(t.getId());
                    return new TournamentSummary(t.getId(), t.getName(), t.getCompetitionId(), t.getSeasonYear(),
                            t.getHosts(), t.getStartDate(), t.getEndDate(), matches.size(),
                            (int) matches.stream().filter(Match::isPlayed).count());
                })
                .toList();
    }

    @Cacheable(CacheConfig.TOURNAMENT)
    public TournamentDetail get(String id) {
        Tournament t = find(id);
        List<Match> matches = matchRepository.findByTournamentIdOrderByMatchNumber(id);
        List<MatchSummary> summaries = assembler.summaries(matches);

        Map<String, List<MatchSummary>> byStage = new LinkedHashMap<>();
        summaries.stream()
                .sorted(Comparator.comparingInt(s -> stageRank(s.stage())))
                .forEach(s -> byStage.computeIfAbsent(s.stage(), k -> new java.util.ArrayList<>()).add(s));
        List<StageSummary> stages = byStage.entrySet().stream()
                .map(e -> new StageSummary(e.getKey(), e.getValue().size(),
                        (int) e.getValue().stream().filter(s -> s.result() != null).count(),
                        MatchAssembler.record(e.getValue())))
                .toList();
        String modelRunId = summaries.stream()
                .map(MatchSummary::prediction)
                .filter(Objects::nonNull)
                .map(p -> p.modelRunId())
                .findFirst()
                .orElse(null);

        return new TournamentDetail(t.getId(), t.getName(), t.getCompetitionId(), t.getSeasonYear(), t.getHosts(),
                t.getStartDate(), t.getEndDate(), matches.size(),
                (int) matches.stream().filter(Match::isPlayed).count(), modelRunId,
                MatchAssembler.record(summaries), stages);
    }

    @Cacheable(CacheConfig.TOURNAMENT_MATCHES)
    public PageResponse<MatchSummary> matches(String id, String stage, int page, int size) {
        find(id);
        PageRequest pageable = PageRequest.of(page, size, Sort.by("matchNumber"));
        Page<Match> result = stage == null
                ? matchRepository.findByTournamentId(id, pageable)
                : matchRepository.findByTournamentIdAndStage(id, stage, pageable);
        return PageResponse.of(result, assembler.summaries(result.getContent()));
    }

    private Tournament find(String id) {
        return tournamentRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Tournament not found: " + id));
    }

    static int stageRank(String stage) {
        int i = STAGE_ORDER.indexOf(stage);
        return i < 0 ? STAGE_ORDER.size() : i;
    }
}
