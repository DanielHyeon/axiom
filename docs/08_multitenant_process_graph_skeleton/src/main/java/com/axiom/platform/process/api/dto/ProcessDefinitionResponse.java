package com.axiom.platform.process.api.dto;

import java.time.LocalDateTime;
import java.util.UUID;

public record ProcessDefinitionResponse(
        UUID id,
        UUID tenantId,
        UUID orgUnitId,
        UUID workspaceId,
        String processKey,
        String name,
        String description,
        String domainCode,
        String ownerRoleCode,
        String status,
        LocalDateTime createdAt,
        LocalDateTime updatedAt
) {
}
