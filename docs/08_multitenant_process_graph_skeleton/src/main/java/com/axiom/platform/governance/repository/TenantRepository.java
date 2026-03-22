package com.axiom.platform.governance.repository;

import java.util.UUID;

import com.axiom.platform.governance.domain.TenantEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Mono;

public interface TenantRepository extends ReactiveCrudRepository<TenantEntity, UUID> {
    Mono<TenantEntity> findByCode(String code);
}
