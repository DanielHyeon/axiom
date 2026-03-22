package com.axiom.platform.simulation.service.impl;

import java.time.LocalDateTime;
import java.util.UUID;

import com.axiom.platform.simulation.service.SimulationEngine;
import com.axiom.platform.twin.api.dto.ScenarioRunResponse;
import org.springframework.stereotype.Component;
import reactor.core.publisher.Mono;

@Component
public class RuleBasedSimulationEngine implements SimulationEngine {

    @Override
    public Mono<ScenarioRunResponse> runScenario(UUID scenarioId) {
        // TODO:
        // 1) base snapshot 조회
        // 2) assumption_json 파싱
        // 3) queue/service-time/SLA/automation-rate 가정 반영
        // 4) 결과 JSON 생성 및 scenario_runs 저장
        return Mono.just(new ScenarioRunResponse(
                UUID.randomUUID(),
                scenarioId,
                "COMPLETED",
                LocalDateTime.now(),
                LocalDateTime.now(),
                "{\"summary\":\"simulation placeholder\"}"
        ));
    }
}
