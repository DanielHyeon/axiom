package com.axiom.platform.process.repository;

import java.util.UUID;

import com.axiom.platform.process.domain.ProcessVersionEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

public interface ProcessVersionRepository extends ReactiveCrudRepository<ProcessVersionEntity, UUID> {
    Flux<ProcessVersionEntity> findByProcessDefinitionId(UUID processDefinitionId);
    Mono<ProcessVersionEntity> findByProcessDefinitionIdAndIsCurrent(UUID processDefinitionId, Boolean isCurrent);
}
