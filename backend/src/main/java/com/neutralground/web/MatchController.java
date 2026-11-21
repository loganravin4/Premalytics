package com.neutralground.web;

import com.neutralground.service.MatchService;
import com.neutralground.web.dto.ReadDtos.MatchDetail;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Min;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/matches")
@Tag(name = "Matches")
public class MatchController {

    private final MatchService matchService;

    public MatchController(MatchService matchService) {
        this.matchService = matchService;
    }

    @GetMapping("/{id}")
    @Operation(summary = "One match with its result and every published prediction")
    public MatchDetail get(@PathVariable @Min(1) long id) {
        return matchService.get(id);
    }
}
