package com.axiom.platform.common.context;

import java.util.UUID;

public record TenantContext(
        UUID tenantId,
        UUID orgUnitId,
        UUID workspaceId,
        String userId
) {
}
