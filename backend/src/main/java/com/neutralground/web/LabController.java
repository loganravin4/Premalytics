package com.neutralground.web;

import com.neutralground.service.LabService;
import com.neutralground.web.dto.ReadDtos.PenaltyAggregateView;
import com.neutralground.web.dto.ReadDtos.XgGrid;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Pattern;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api")
@Tag(name = "Labs")
public class LabController {

    private final LabService labService;

    public LabController(LabService labService) {
        this.labService = labService;
    }

    @GetMapping("/xg/grid")
    @Operation(summary = "Precomputed shot xG grid from the newest shot model run that has one")
    public XgGrid xgGrid() {
        return labService.xgGrid();
    }

    @GetMapping("/penalties/aggregates")
    @Operation(summary = "Penalty conversion aggregates (experimental)")
    public List<PenaltyAggregateView> penaltyAggregates(
            @RequestParam(required = false) @Pattern(regexp = "^[a-z0-9_]{1,64}$") String dataset,
            @RequestParam(required = false) @Pattern(regexp = "^[a-z0-9_]{1,32}$") String dimension) {
        return labService.penaltyAggregates(dataset, dimension);
    }
}
