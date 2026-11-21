package com.neutralground.web;

import com.neutralground.service.TournamentService;
import com.neutralground.web.dto.PageResponse;
import com.neutralground.web.dto.PredictionDtos;
import com.neutralground.web.dto.ReadDtos.MatchSummary;
import com.neutralground.web.dto.ReadDtos.TournamentDetail;
import com.neutralground.web.dto.ReadDtos.TournamentSummary;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/tournaments")
@Tag(name = "Tournaments")
public class TournamentController {

    private final TournamentService tournamentService;

    public TournamentController(TournamentService tournamentService) {
        this.tournamentService = tournamentService;
    }

    @GetMapping
    @Operation(summary = "All tournaments, newest first")
    public List<TournamentSummary> list() {
        return tournamentService.list();
    }

    @GetMapping("/{id}")
    @Operation(summary = "One tournament with per-stage model record")
    public TournamentDetail get(@PathVariable @Pattern(regexp = "^[a-z0-9_]{1,32}$") String id) {
        return tournamentService.get(id);
    }

    @GetMapping("/{id}/matches")
    @Operation(summary = "A tournament's matches in match order, optionally filtered by stage")
    public PageResponse<MatchSummary> matches(
            @PathVariable @Pattern(regexp = "^[a-z0-9_]{1,32}$") String id,
            @RequestParam(required = false) @Pattern(regexp = PredictionDtos.STAGE_PATTERN) String stage,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = ApiPaging.DEFAULT_SIZE) @Min(1) @Max(ApiPaging.MAX_SIZE) int size) {
        return tournamentService.matches(id, stage, page, size);
    }
}
