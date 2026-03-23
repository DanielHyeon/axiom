package com.axiom.platform.outbox.repository;

import java.util.UUID;

import com.axiom.platform.outbox.domain.OutboxEventEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;

public interface OutboxEventRepository extends ReactiveCrudRepository<OutboxEventEntity, UUID> {
    Flux<OutboxEventEntity> findByStatusOrderByOccurredAtAsc(String status);
}
