package com.axiom.platform.process.repository;

import java.util.UUID;

import com.axiom.platform.process.domain.StepDefinitionEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;

public interface StepDefinitionRepository extends ReactiveCrudRepository<StepDefinitionEntity, UUID> {
    Flux<StepDefinitionEntity> findByProcessVersionIdOrderBySequenceNoAsc(UUID processVersionId);
}
