package com.premalytics.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.premalytics.dto.ShotPredictionResponse;
import com.premalytics.service.ProcessRunner.ProcessResult;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;

/**
 * Runs the Python shot-xG CLI (ml.pipeline.predict_shot) via ProcessBuilder and
 * parses its stdout JSON into a ShotPredictionResponse. Mirrors the ProcessBuilder
 * pattern in {@link PredictionService}.
 */
@Service
public class XgService {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${ml.python.interpreter}")
    private String pythonInterpreter;

    @Value("${ml.project.root}")
    private String projectRoot;

    public ShotPredictionResponse predict(double distance, double angle) {
        try {
            ProcessBuilder pb = new ProcessBuilder(
                    pythonInterpreter,
                    "-m", "ml.pipeline.predict_shot",
                    "--distance", Double.toString(distance),
                    "--angle", Double.toString(angle)
            );
            pb.directory(new File(projectRoot));

            ProcessResult result = ProcessRunner.run(pb);

            if (result.exitCode != 0 || result.stdout.isBlank()) {
                throw new RuntimeException(
                        "ml.pipeline.predict_shot failed (exit " + result.exitCode + "): " + result.stderr);
            }

            return objectMapper.readValue(result.stdout, ShotPredictionResponse.class);

        } catch (IOException e) {
            throw new RuntimeException("Failed to run shot prediction: " + e.getMessage(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Shot prediction was interrupted", e);
        }
    }
}
