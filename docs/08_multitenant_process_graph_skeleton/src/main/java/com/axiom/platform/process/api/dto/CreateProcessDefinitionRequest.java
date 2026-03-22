package com.axiom.platform.process.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.UUID;

public record CreateProcessDefinitionRequest(
        @NotNull UUID workspaceId,
        UUID orgUnitId,
        @NotBlank String processKey,
        @NotBlank String name,
        String description,
        @NotBlank String domainCode,
        String ownerRoleCode
) {
}
