package com.axiom.platform.graph.service.impl;

import java.util.List;
import java.util.UUID;

import com.axiom.platform.process.api.dto.ImpactAnalysisResponse;
import com.axiom.platform.process.domain.ProcessDefinitionEntity;
import com.axiom.platform.graph.service.ProcessGraphProjectionService;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Mono;

@Service
public class ProcessGraphProjectionServiceImpl implements ProcessGraphProjectionService {

    @Override
    public Mono<ProcessDefinitionEntity> upsertProcessNode(ProcessDefinitionEntity entity) {
        // TODO: Neo4j client 또는 Spring Data Neo4j로 MERGE projection 구현
        return Mono.just(entity);
    }

    @Override
    public Mono<Void> upsertDependency(UUID sourceProcessId, UUID targetProcessId, String relationType, double weight, String interfaceCode) {
        // TODO: source-[:DEPENDS_ON {relationType, weight, interfaceCode}]->target MERGE
        return Mono.empty();
    }

    @Override
    public Mono<ImpactAnalysisResponse> analyzeImpact(UUID processDefinitionId, int depth) {
        // TODO: 실제 구현에서는 upstream/downstream variable length traversal 사용
        return Mono.just(new ImpactAnalysisResponse(
                processDefinitionId,
                "placeholder.process",
                "Placeholder Process",
                depth,
                depth,
                List.of(),
                List.of()
        ));
    }
}
