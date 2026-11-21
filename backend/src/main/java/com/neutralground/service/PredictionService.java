package com.neutralground.service;

import com.neutralground.inference.InferenceClient;
import com.neutralground.inference.InferenceException;
import com.neutralground.inference.MatchFixture;
import com.neutralground.inference.MatchInferenceResult;
import com.neutralground.inference.ShotFeatures;
import com.neutralground.inference.ShotInferenceResult;
import com.neutralground.web.dto.PredictionDtos.MatchPredictionRequest;
import com.neutralground.web.dto.PredictionDtos.MatchPredictionResponse;
import com.neutralground.web.dto.PredictionDtos.ShotPredictionRequest;
import com.neutralground.web.dto.PredictionDtos.ShotPredictionResponse;
import com.neutralground.web.dto.ReadDtos.PredictedScore;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

/** Ad-hoc "what if" predictions, delegated to the inference service. */
@Service
public class PredictionService {

    private final InferenceClient inferenceClient;

    public PredictionService(InferenceClient inferenceClient) {
        this.inferenceClient = inferenceClient;
    }

    public List<MatchPredictionResponse> predictMatches(List<MatchPredictionRequest> requests) {
        List<MatchFixture> fixtures = requests.stream()
                .map(r -> new MatchFixture(r.homeTeam(), r.awayTeam(), r.matchDate().toString(),
                        r.competitionIdOrDefault(), r.competitionStageOrDefault(), r.neutralVenueOrDefault()))
                .toList();
        MatchInferenceResult result = inferenceClient.predictMatches(fixtures);
        List<MatchInferenceResult.Row> rows = result.predictions() == null ? List.of() : result.predictions();
        if (rows.size() != fixtures.size()) {
            throw new InferenceException("Inference service returned " + rows.size() + " predictions for "
                    + fixtures.size() + " fixtures", true, null);
        }
        List<MatchPredictionResponse> responses = new ArrayList<>(rows.size());
        for (int i = 0; i < rows.size(); i++) {
            MatchInferenceResult.Row row = rows.get(i);
            MatchFixture fixture = fixtures.get(i);
            if (!fixture.homeTeam().equals(row.homeTeam()) || !fixture.awayTeam().equals(row.awayTeam())) {
                throw new InferenceException("Inference service returned predictions out of order", true, null);
            }
            PredictedScore score = row.predictedHomeGoals() == null || row.predictedAwayGoals() == null
                    ? null : new PredictedScore(row.predictedHomeGoals(), row.predictedAwayGoals());
            responses.add(new MatchPredictionResponse(row.homeTeam(), row.awayTeam(), row.pHomeWin(), row.pDraw(),
                    row.pAwayWin(), Outcomes.pick(row.pHomeWin(), row.pDraw(), row.pAwayWin()), score,
                    row.homeXg(), row.awayXg(), result.modelRunId()));
        }
        return responses;
    }

    public ShotPredictionResponse predictShot(ShotPredictionRequest request) {
        ShotInferenceResult result = inferenceClient.predictShot(
                new ShotFeatures(request.distanceM(), request.angleDeg(), request.bodyPart(), request.situation()));
        return new ShotPredictionResponse(result.pGoal(), result.model(), result.modelRunId(), result.distanceM(),
                result.angleDeg());
    }
}
