package com.neutralground.service;

import com.neutralground.domain.Match;
import com.neutralground.domain.ModelRun;
import com.neutralground.domain.Prediction;
import com.neutralground.domain.Team;
import com.neutralground.repository.ModelRunRepository;
import com.neutralground.repository.PredictionRepository;
import com.neutralground.web.dto.ReadDtos.MatchPrediction;
import com.neutralground.web.dto.ReadDtos.MatchResult;
import com.neutralground.web.dto.ReadDtos.MatchSummary;
import com.neutralground.web.dto.ReadDtos.ModelRecord;
import com.neutralground.web.dto.ReadDtos.PredictedScore;
import com.neutralground.web.dto.ReadDtos.TeamRef;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.stream.Collectors;

/** Turns matches plus their predictions into API views. Picks the newest published run per match. */
@Component
public class MatchAssembler {

    private final PredictionRepository predictionRepository;
    private final ModelRunRepository modelRunRepository;

    public MatchAssembler(PredictionRepository predictionRepository, ModelRunRepository modelRunRepository) {
        this.predictionRepository = predictionRepository;
        this.modelRunRepository = modelRunRepository;
    }

    /** Every prediction for the given matches, grouped by match id, newest published run first. */
    public Map<Long, List<Prediction>> predictionsByMatch(Collection<Long> matchIds) {
        if (matchIds.isEmpty()) {
            return Map.of();
        }
        List<Prediction> predictions = predictionRepository.findByMatchIdIn(matchIds);
        Map<String, OffsetDateTime> publishedAt = modelRunRepository
                .findAllById(predictions.stream().map(Prediction::getModelRunId).distinct().toList())
                .stream()
                .collect(Collectors.toMap(ModelRun::getId, ModelRun::getPublishedAt));
        Comparator<Prediction> newestFirst = Comparator
                .comparing((Prediction p) -> publishedAt.getOrDefault(p.getModelRunId(), OffsetDateTime.MIN))
                .thenComparing(Prediction::getModelRunId)
                .reversed();
        Map<Long, List<Prediction>> grouped = new HashMap<>();
        for (Prediction p : predictions) {
            grouped.computeIfAbsent(p.getMatchId(), id -> new java.util.ArrayList<>()).add(p);
        }
        grouped.values().forEach(list -> list.sort(newestFirst));
        return grouped;
    }

    public Map<Long, Prediction> latestByMatch(Collection<Long> matchIds) {
        return predictionsByMatch(matchIds).entrySet().stream()
                .collect(Collectors.toMap(Map.Entry::getKey, e -> e.getValue().get(0)));
    }

    public List<MatchSummary> summaries(List<Match> matches) {
        Map<Long, Prediction> latest = latestByMatch(matches.stream().map(Match::getId).toList());
        return matches.stream().map(m -> summary(m, latest.get(m.getId()))).toList();
    }

    public MatchSummary summary(Match m, Prediction p) {
        return new MatchSummary(m.getId(), m.getTournamentId(), m.getMatchNumber(), m.getMatchDate(), m.getStage(),
                ref(m.getHomeTeam()), ref(m.getAwayTeam()), m.isNeutralVenue(), result(m), prediction(m, p));
    }

    public MatchResult result(Match m) {
        if (!m.isPlayed()) {
            return null;
        }
        return new MatchResult(m.getHomeGoals(), m.getAwayGoals(), Outcomes.byGoals(m), m.getWinnerCode(),
                m.isDecidedOnPenalties());
    }

    public MatchPrediction prediction(Match m, Prediction p) {
        if (p == null) {
            return null;
        }
        String pick = Outcomes.pick(p.getPHome(), p.getPDraw(), p.getPAway());
        String actual = Outcomes.credited(m);
        PredictedScore score = p.getPredictedHomeGoals() == null || p.getPredictedAwayGoals() == null
                ? null : new PredictedScore(p.getPredictedHomeGoals(), p.getPredictedAwayGoals());
        return new MatchPrediction(p.getModelRunId(), p.getPHome(), p.getPDraw(), p.getPAway(), pick, score,
                p.getHomeXg(), p.getAwayXg(), actual == null ? null : actual.equals(pick));
    }

    public static ModelRecord record(Collection<MatchSummary> matches) {
        List<Boolean> scored = matches.stream()
                .map(MatchSummary::prediction)
                .filter(Objects::nonNull)
                .map(MatchPrediction::correct)
                .filter(Objects::nonNull)
                .toList();
        return ModelRecord.of(scored.size(), (int) scored.stream().filter(Boolean::booleanValue).count());
    }

    public static TeamRef ref(Team team) {
        return new TeamRef(team.getCode(), team.getName());
    }
}
