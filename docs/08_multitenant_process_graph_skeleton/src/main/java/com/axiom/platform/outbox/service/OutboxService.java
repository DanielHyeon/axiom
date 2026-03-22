package com.axiom.platform.outbox.service;

import java.util.UUID;

import reactor.core.publisher.Mono;

public interface OutboxService {
    Mono<Void> enqueue(UUID tenantId, String aggregateType, UUID aggregateId, String eventType, Object payload);
}
