package com.neutralground.web;

import com.neutralground.service.TeamService;
import com.neutralground.web.dto.PageResponse;
import com.neutralground.web.dto.ReadDtos.TeamDetail;
import com.neutralground.web.dto.ReadDtos.TeamSummary;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Pattern;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;

@RestController
@RequestMapping("/api/teams")
@Tag(name = "Teams")
public class TeamController {

    private final TeamService teamService;

    public TeamController(TeamService teamService) {
        this.teamService = teamService;
    }

    @GetMapping
    @Operation(summary = "Teams sorted by name, optionally filtered by confederation")
    public PageResponse<TeamSummary> list(
            @RequestParam(required = false) @Pattern(regexp = "^(AFC|CAF|CONCACAF|CONMEBOL|OFC|UEFA)$")
            String confederation,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = ApiPaging.DEFAULT_SIZE) @Min(1) @Max(ApiPaging.MAX_SIZE) int size) {
        return teamService.list(confederation, page, size);
    }

    @GetMapping("/{code}")
    @Operation(summary = "One team: Elo history, results, and the model's predictions for its matches")
    public TeamDetail get(
            @PathVariable @Pattern(regexp = "^[A-Z]{3}$") String code,
            @RequestParam(defaultValue = "2018-01-01") @DateTimeFormat(iso = DateTimeFormat.ISO.DATE)
            LocalDate eloSince) {
        return teamService.get(code, eloSince);
    }
}
