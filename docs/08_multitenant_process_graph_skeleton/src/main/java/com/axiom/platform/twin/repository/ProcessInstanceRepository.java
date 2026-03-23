package com.axiom.platform.twin.repository;

import java.util.UUID;

import com.axiom.platform.twin.domain.ProcessInstanceEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;

public interface ProcessInstanceRepository extends ReactiveCrudRepository<ProcessInstanceEntity, UUID> {
    Flux<ProcessInstanceEntity> findByTenantIdAndProcessDefinitionId(UUID tenantId, UUID processDefinitionId);
}
