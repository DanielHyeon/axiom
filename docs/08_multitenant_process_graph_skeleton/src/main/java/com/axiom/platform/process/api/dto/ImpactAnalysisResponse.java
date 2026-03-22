package com.axiom.platform.process.api.dto;

import java.util.List;
import java.util.UUID;

public record ImpactAnalysisResponse(
        UUID processId,
        String processKey,
        String processName,
        int downstreamDepth,
        int upstreamDepth,
        List<ImpactNode> upstream,
        List<ImpactNode> downstream
) {
    public record ImpactNode(
            UUID processId,
            String processKey,
            String processName,
            String relationType,
            Double weight,
            int depth
    ) {}
}
