package com.axiom.platform.twin.api.dto;

import java.time.LocalDateTime;
import java.util.UUID;

public record ScenarioRunResponse(
        UUID runId,
        UUID scenarioId,
        String runStatus,
        LocalDateTime startedAt,
        LocalDateTime completedAt,
        String resultJson
) {
}
