package com.axiom.platform.process.service;

import java.util.UUID;

import com.axiom.platform.process.api.dto.CreateProcessDefinitionRequest;
import com.axiom.platform.process.api.dto.CreateProcessVersionRequest;
import com.axiom.platform.process.api.dto.ImpactAnalysisResponse;
import com.axiom.platform.process.api.dto.ProcessDefinitionResponse;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface ProcessDefinitionService {

    Mono<ProcessDefinitionResponse> createProcess(CreateProcessDefinitionRequest request);

    Flux<ProcessDefinitionResponse> listByWorkspace(UUID workspaceId);

    Mono<UUID> createVersion(CreateProcessVersionRequest request);

    Mono<ImpactAnalysisResponse> analyzeImpact(UUID processDefinitionId, int depth);
}
