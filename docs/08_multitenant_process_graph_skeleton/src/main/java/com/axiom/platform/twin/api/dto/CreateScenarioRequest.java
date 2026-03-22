package com.axiom.platform.twin.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.UUID;

public record CreateScenarioRequest(
        @NotBlank String scenarioKey,
        @NotBlank String name,
        @NotNull UUID baseSnapshotId,
        @NotBlank String assumptionJson
) {
}
