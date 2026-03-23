package com.axiom.platform.twin.repository;

import java.util.UUID;

import com.axiom.platform.twin.domain.TwinEventEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;

public interface TwinEventRepository extends ReactiveCrudRepository<TwinEventEntity, UUID> {
    Flux<TwinEventEntity> findByTenantIdAndAggregateTypeAndAggregateIdOrderByEventTimeDesc(
            UUID tenantId, String aggregateType, UUID aggregateId
    );
}
