package com.axiom.platform.process.repository;

import java.util.UUID;

import com.axiom.platform.process.domain.ProcessInterfaceEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;

public interface ProcessInterfaceRepository extends ReactiveCrudRepository<ProcessInterfaceEntity, UUID> {
    Flux<ProcessInterfaceEntity> findByProcessVersionId(UUID processVersionId);
}
