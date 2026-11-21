package com.neutralground.web;

import com.neutralground.service.ModelRunService;
import com.neutralground.web.dto.ReadDtos.ModelRunView;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Pattern;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/model-runs")
@Tag(name = "Model runs")
public class ModelRunController {

    private final ModelRunService modelRunService;

    public ModelRunController(ModelRunService modelRunService) {
        this.modelRunService = modelRunService;
    }

    @GetMapping("/latest")
    @Operation(summary = "Scorecard of the newest published run of a kind (default: the match model)")
    public ModelRunView latest(
            @RequestParam(defaultValue = "match") @Pattern(regexp = "^(match|score|shot_xg|penalty)$") String kind) {
        return modelRunService.latest(kind);
    }

    @GetMapping("/{id}")
    @Operation(summary = "Scorecard of one run")
    public ModelRunView get(@PathVariable @Pattern(regexp = "^[A-Za-z0-9_.-]{1,64}$") String id) {
        return modelRunService.get(id);
    }
}
