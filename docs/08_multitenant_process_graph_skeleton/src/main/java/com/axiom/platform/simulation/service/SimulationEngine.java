package com.axiom.platform.simulation.service;

import java.util.UUID;

import com.axiom.platform.twin.api.dto.ScenarioRunResponse;
import reactor.core.publisher.Mono;

public interface SimulationEngine {
    Mono<ScenarioRunResponse> runScenario(UUID scenarioId);
}
