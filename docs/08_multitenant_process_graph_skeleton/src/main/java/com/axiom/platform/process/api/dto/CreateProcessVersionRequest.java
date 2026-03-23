package com.axiom.platform.process.api.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.List;
import java.util.UUID;

public record CreateProcessVersionRequest(
        @NotNull UUID processDefinitionId,
        @NotEmpty List<@Valid StepDefinitionRequest> steps,
        List<@Valid ProcessInterfaceRequest> interfaces
) {
    public record StepDefinitionRequest(
            String stepKey,
            String name,
            String stepType,
            Integer sequenceNo,
            String ownerRoleCode,
            String inputContractCode,
            String outputContractCode,
            Integer slaMinutes,
            Boolean automated
    ) {}

    public record ProcessInterfaceRequest(
            String interfaceCode,
            String direction,
            String payloadType,
            String schemaRef,
            Boolean requiredFlag
    ) {}
}
