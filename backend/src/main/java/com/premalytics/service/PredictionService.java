package com.premalytics.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.premalytics.dto.MatchPredictionRequest;
import com.premalytics.dto.MatchPredictionResponse;
import com.premalytics.service.ProcessRunner.ProcessResult;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * Runs the Python match-prediction CLI (ml.pipeline.predict) via ProcessBuilder.
 *
 * Requests are written to a temp fixtures CSV (wc_fixtures.csv format), the CLI
 * is invoked with the project root as working directory, and its stdout JSON is
 * parsed into MatchPredictionResponse objects.
 */
@Service
public class PredictionService {

    private static final String FIXTURE_HEADER =
            "match_date,home_team,away_team,is_neutral_venue,competition_id,competition_stage";

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${ml.python.interpreter}")
    private String pythonInterpreter;

    @Value("${ml.project.root}")
    private String projectRoot;

    public List<MatchPredictionResponse> predict(List<MatchPredictionRequest> requests) {
        Path tempCsv = null;
        try {
            tempCsv = writeFixturesCsv(requests);

            ProcessBuilder pb = new ProcessBuilder(
                    pythonInterpreter,
                    "-m", "ml.pipeline.predict",
                    "--fixtures", tempCsv.toAbsolutePath().toString()
            );
            pb.directory(new File(projectRoot));

            ProcessResult result = ProcessRunner.run(pb);

            if (result.exitCode != 0 || result.stdout.isBlank()) {
                throw new RuntimeException(
                        "ml.pipeline.predict failed (exit " + result.exitCode + "): " + result.stderr);
            }

            return objectMapper.readValue(
                    result.stdout, new TypeReference<List<MatchPredictionResponse>>() {});

        } catch (IOException e) {
            throw new RuntimeException("Failed to run match prediction: " + e.getMessage(), e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Match prediction was interrupted", e);
        } finally {
            deleteQuietly(tempCsv);
        }
    }

    /** Write the requests to a temp CSV matching wc_fixtures.csv exactly. */
    private Path writeFixturesCsv(List<MatchPredictionRequest> requests) throws IOException {
        Path tempCsv = Files.createTempFile("wc_fixtures_", ".csv");
        List<String> lines = new ArrayList<>();
        lines.add(FIXTURE_HEADER);
        for (MatchPredictionRequest r : requests) {
            lines.add(String.join(",",
                    nullToEmpty(r.getMatchDate()),
                    nullToEmpty(r.getHomeTeam()),
                    nullToEmpty(r.getAwayTeam()),
                    Boolean.toString(r.isNeutralVenue()),
                    nullToEmpty(r.getCompetitionId()),
                    nullToEmpty(r.getCompetitionStage())
            ));
        }
        Files.write(tempCsv, lines, StandardCharsets.UTF_8);
        return tempCsv;
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    private static void deleteQuietly(Path path) {
        if (path == null) {
            return;
        }
        try {
            Files.deleteIfExists(path);
        } catch (IOException ignored) {
            // best-effort cleanup
        }
    }
}
