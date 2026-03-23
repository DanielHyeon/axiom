package com.axiom.platform.outbox.service.impl;

import java.time.LocalDateTime;
import java.util.UUID;

import com.axiom.platform.outbox.domain.OutboxEventEntity;
import com.axiom.platform.outbox.repository.OutboxEventRepository;
import com.axiom.platform.outbox.service.OutboxService;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public class OutboxServiceImpl implements OutboxService {

    private final OutboxEventRepository outboxEventRepository;
    private final ObjectMapper objectMapper;

    public OutboxServiceImpl(OutboxEventRepository outboxEventRepository, ObjectMapper objectMapper) {
        this.outboxEventRepository = outboxEventRepository;
        this.objectMapper = objectMapper;
    }

    @Override
    public Mono<Void> enqueue(UUID tenantId, String aggregateType, UUID aggregateId, String eventType, Object payload) {
        return Mono.fromCallable(() -> {
                    OutboxEventEntity entity = new OutboxEventEntity();
                    entity.setId(UUID.randomUUID());
                    entity.setTenantId(tenantId);
                    entity.setAggregateType(aggregateType);
                    entity.setAggregateId(aggregateId);
                    entity.setEventType(eventType);
                    entity.setPayloadJson(writeJson(payload));
                    entity.setStatus("PENDING");
                    entity.setOccurredAt(LocalDateTime.now());
                    entity.setCreatedAt(LocalDateTime.now());
                    entity.setUpdatedAt(LocalDateTime.now());
                    return entity;
                })
                .flatMap(outboxEventRepository::save)
                .then();
    }

    private String writeJson(Object payload) {
        try {
            return objectMapper.writeValueAsString(payload);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Failed to serialize outbox payload", e);
        }
    }
}
