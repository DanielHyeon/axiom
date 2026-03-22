package com.axiom.platform.governance.repository;

import java.util.UUID;

import com.axiom.platform.governance.domain.WorkspaceEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;

public interface WorkspaceRepository extends ReactiveCrudRepository<WorkspaceEntity, UUID> {
    Flux<WorkspaceEntity> findByTenantId(UUID tenantId);
}
