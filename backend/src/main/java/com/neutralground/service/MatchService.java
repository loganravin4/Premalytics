package com.neutralground.service;

import com.neutralground.config.CacheConfig;
import com.neutralground.domain.Match;
import com.neutralground.domain.Prediction;
import com.neutralground.repository.MatchRepository;
import com.neutralground.repository.TournamentRepository;
import com.neutralground.web.dto.ReadDtos.MatchDetail;
import com.neutralground.web.dto.ReadDtos.MatchPrediction;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
@Transactional(readOnly = true)
public class MatchService {

    private final MatchRepository matchRepository;
    private final TournamentRepository tournamentRepository;
    private final MatchAssembler assembler;

    public MatchService(MatchRepository matchRepository, TournamentRepository tournamentRepository,
                        MatchAssembler assembler) {
        this.matchRepository = matchRepository;
        this.tournamentRepository = tournamentRepository;
        this.assembler = assembler;
    }

    @Cacheable(CacheConfig.MATCH)
    public MatchDetail get(long id) {
        Match m = matchRepository.findWithTeamsById(id)
                .orElseThrow(() -> new NotFoundException("Match not found: " + id));
        List<Prediction> predictions = assembler.predictionsByMatch(List.of(id)).getOrDefault(id, List.of());
        List<MatchPrediction> history = predictions.stream().map(p -> assembler.prediction(m, p)).toList();
        String tournamentName = tournamentRepository.findById(m.getTournamentId())
                .map(t -> t.getName()).orElse(null);
        return new MatchDetail(m.getId(), m.getTournamentId(), tournamentName, m.getMatchNumber(), m.getMatchDate(),
                m.getStage(), MatchAssembler.ref(m.getHomeTeam()), MatchAssembler.ref(m.getAwayTeam()),
                m.isNeutralVenue(), assembler.result(m), history.isEmpty() ? null : history.get(0), history);
    }
}
