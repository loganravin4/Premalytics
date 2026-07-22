package com.premalytics.controller;

import com.premalytics.dto.ErrorResponse;
import com.premalytics.dto.ShotPredictionResponse;
import com.premalytics.service.XgService;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Shot-level xG prediction. Delegates to {@link XgService}, which shells out to
 * the Python predict_shot CLI.
 */
@RestController
@RequestMapping("/api/xg")
public class XgController {

    private final XgService xgService;

    public XgController(XgService xgService) {
        this.xgService = xgService;
    }

    @GetMapping("/predict")
    public ResponseEntity<?> predictShot(@RequestParam double distance, @RequestParam double angle) {
        try {
            ShotPredictionResponse prediction = xgService.predict(distance, angle);
            return ResponseEntity.ok(prediction);
        } catch (RuntimeException e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new ErrorResponse("Shot prediction failed", e.getMessage()));
        }
    }
}
