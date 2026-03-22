package com.axiom.platform.twin.api;

import java.util.UUID;

import com.axiom.platform.twin.api.dto.CreateScenarioRequest;
import com.axiom.platform.twin.api.dto.ScenarioRunResponse;
import com.axiom.platform.twin.service.TwinScenarioService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/twin/scenarios")
public class TwinScenarioController {

    private final TwinScenarioService twinScenarioService;

    public TwinScenarioController(TwinScenarioService twinScenarioService) {
        this.twinScenarioService = twinScenarioService;
    }

    @PostMapping
    public Mono<UUID> create(@Valid @RequestBody CreateScenarioRequest request) {
        return twinScenarioService.createScenario(request);
    }

    @PostMapping("/{scenarioId}/runs")
    public Mono<ScenarioRunResponse> run(@PathVariable UUID scenarioId) {
        return twinScenarioService.runScenario(scenarioId);
    }
}
