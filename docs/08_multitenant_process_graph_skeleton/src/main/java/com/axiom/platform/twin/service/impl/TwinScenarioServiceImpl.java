package com.axiom.platform.twin.service.impl;

import java.time.LocalDateTime;
import java.util.UUID;

import com.axiom.platform.common.context.TenantContextHolder;
import com.axiom.platform.simulation.service.SimulationEngine;
import com.axiom.platform.twin.api.dto.CreateScenarioRequest;
import com.axiom.platform.twin.api.dto.ScenarioRunResponse;
import com.axiom.platform.twin.domain.TwinScenarioEntity;
import com.axiom.platform.twin.service.TwinScenarioService;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public class TwinScenarioServiceImpl implements TwinScenarioService {

    private final SimulationEngine simulationEngine;

    public TwinScenarioServiceImpl(SimulationEngine simulationEngine) {
        this.simulationEngine = simulationEngine;
    }

    @Override
    public Mono<UUID> createScenario(CreateScenarioRequest request) {
        return TenantContextHolder.getCurrent()
                .map(context -> {
                    // TODO: repository.save(entity) 로 대체
                    TwinScenarioEntity entity = new TwinScenarioEntity();
                    entity.setId(UUID.randomUUID());
                    entity.setTenantId(context.tenantId());
                    entity.setScenarioKey(request.scenarioKey());
                    entity.setName(request.name());
                    entity.setBaseSnapshotId(request.baseSnapshotId());
                    entity.setAssumptionJson(request.assumptionJson());
                    entity.setStatus("DRAFT");
                    entity.setCreatedBy(context.userId());
                    entity.setCreatedAt(LocalDateTime.now());
                    entity.setUpdatedAt(LocalDateTime.now());
                    return entity.getId();
                });
    }

    @Override
    public Mono<ScenarioRunResponse> runScenario(UUID scenarioId) {
        return simulationEngine.runScenario(scenarioId);
    }
}
