package com.axiom.platform.twin.service;

import java.util.UUID;

import com.axiom.platform.twin.api.dto.CreateScenarioRequest;
import com.axiom.platform.twin.api.dto.ScenarioRunResponse;
import reactor.core.publisher.Mono;

public interface TwinScenarioService {
    Mono<UUID> createScenario(CreateScenarioRequest request);
    Mono<ScenarioRunResponse> runScenario(UUID scenarioId);
}
