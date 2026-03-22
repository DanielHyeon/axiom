package com.axiom.platform.graph.service;

import java.util.UUID;

import com.axiom.platform.process.api.dto.ImpactAnalysisResponse;
import com.axiom.platform.process.domain.ProcessDefinitionEntity;
import reactor.core.publisher.Mono;

public interface ProcessGraphProjectionService {
    Mono<ProcessDefinitionEntity> upsertProcessNode(ProcessDefinitionEntity entity);
    Mono<Void> upsertDependency(UUID sourceProcessId, UUID targetProcessId, String relationType, double weight, String interfaceCode);
    Mono<ImpactAnalysisResponse> analyzeImpact(UUID processDefinitionId, int depth);
}
