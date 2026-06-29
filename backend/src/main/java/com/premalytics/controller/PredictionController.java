package com.premalytics.controller;

import com.premalytics.dto.ErrorResponse;
import com.premalytics.dto.MatchPredictionRequest;
import com.premalytics.dto.MatchPredictionResponse;
import com.premalytics.service.PredictionService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * Match outcome predictions. Delegates to {@link PredictionService}, which shells
 * out to the Python predict CLI.
 */
@RestController
@RequestMapping("/api/predictions")
public class PredictionController {

    private final PredictionService predictionService;

    public PredictionController(PredictionService predictionService) {
        this.predictionService = predictionService;
    }

    @PostMapping("/match")
    public ResponseEntity<?> predictMatch(@RequestBody List<MatchPredictionRequest> requests) {
        try {
            List<MatchPredictionResponse> predictions = predictionService.predict(requests);
            return ResponseEntity.ok(predictions);
        } catch (RuntimeException e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new ErrorResponse("Match prediction failed", e.getMessage()));
        }
    }
}
