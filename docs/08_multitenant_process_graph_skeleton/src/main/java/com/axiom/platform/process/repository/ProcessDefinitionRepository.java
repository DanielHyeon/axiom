package com.axiom.platform.process.repository;

import java.util.UUID;

import com.axiom.platform.process.domain.ProcessDefinitionEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface ProcessDefinitionRepository extends ReactiveCrudRepository<ProcessDefinitionEntity, UUID> {

    Flux<ProcessDefinitionEntity> findByTenantIdAndWorkspaceId(UUID tenantId, UUID workspaceId);

    Mono<ProcessDefinitionEntity> findByTenantIdAndWorkspaceIdAndProcessKey(UUID tenantId, UUID workspaceId, String processKey);
}
