package com.neutralground.web;

import com.neutralground.service.PredictionService;
import com.neutralground.web.dto.PredictionDtos.MatchPredictionBatch;
import com.neutralground.web.dto.PredictionDtos.MatchPredictionResponse;
import com.neutralground.web.dto.PredictionDtos.ShotPredictionRequest;
import com.neutralground.web.dto.PredictionDtos.ShotPredictionResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/** Ad-hoc inference ("what if A played B", xG sliders). Rate limited per client. */
@RestController
@RequestMapping(value = "/api/predictions", consumes = MediaType.APPLICATION_JSON_VALUE)
@Tag(name = "Predictions")
public class PredictionController {

    private final PredictionService predictionService;

    public PredictionController(PredictionService predictionService) {
        this.predictionService = predictionService;
    }

    @PostMapping("/match")
    @Operation(summary = "Predict win/draw/loss and a scoreline for up to 20 hypothetical fixtures")
    public List<MatchPredictionResponse> predictMatches(@Valid @RequestBody MatchPredictionBatch batch) {
        return predictionService.predictMatches(batch.fixtures());
    }

    @PostMapping("/shot")
    @Operation(summary = "Model xG for one shot (model estimate, not official xG)")
    public ShotPredictionResponse predictShot(@Valid @RequestBody ShotPredictionRequest request) {
        return predictionService.predictShot(request);
    }
}
