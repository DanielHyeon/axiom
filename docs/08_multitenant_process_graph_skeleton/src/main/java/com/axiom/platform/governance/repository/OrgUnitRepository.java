package com.axiom.platform.governance.repository;

import java.util.UUID;

import com.axiom.platform.governance.domain.OrgUnitEntity;
import org.springframework.data.repository.reactive.ReactiveCrudRepository;
import reactor.core.publisher.Flux;

public interface OrgUnitRepository extends ReactiveCrudRepository<OrgUnitEntity, UUID> {
    Flux<OrgUnitEntity> findByTenantId(UUID tenantId);
}
