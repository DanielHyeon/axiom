package com.axiom.platform.process.service.impl;

import java.time.LocalDateTime;
import java.util.UUID;

import com.axiom.platform.common.context.TenantContextHolder;
import com.axiom.platform.graph.service.ProcessGraphProjectionService;
import com.axiom.platform.outbox.service.OutboxService;
import com.axiom.platform.process.api.dto.CreateProcessDefinitionRequest;
import com.axiom.platform.process.api.dto.CreateProcessVersionRequest;
import com.axiom.platform.process.api.dto.ImpactAnalysisResponse;
import com.axiom.platform.process.api.dto.ProcessDefinitionResponse;
import com.axiom.platform.process.domain.ProcessDefinitionEntity;
import com.axiom.platform.process.domain.ProcessVersionEntity;
import com.axiom.platform.process.repository.ProcessDefinitionRepository;
import com.axiom.platform.process.repository.ProcessInterfaceRepository;
import com.axiom.platform.process.repository.ProcessVersionRepository;
import com.axiom.platform.process.repository.StepDefinitionRepository;
import com.axiom.platform.process.service.ProcessDefinitionService;
import org.springframework.stereotype.Service;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Service
public class ProcessDefinitionServiceImpl implements ProcessDefinitionService {

    private final ProcessDefinitionRepository processDefinitionRepository;
    private final ProcessVersionRepository processVersionRepository;
    private final StepDefinitionRepository stepDefinitionRepository;
    private final ProcessInterfaceRepository processInterfaceRepository;
    private final ProcessGraphProjectionService processGraphProjectionService;
    private final OutboxService outboxService;

    public ProcessDefinitionServiceImpl(
            ProcessDefinitionRepository processDefinitionRepository,
            ProcessVersionRepository processVersionRepository,
            StepDefinitionRepository stepDefinitionRepository,
            ProcessInterfaceRepository processInterfaceRepository,
            ProcessGraphProjectionService processGraphProjectionService,
            OutboxService outboxService
    ) {
        this.processDefinitionRepository = processDefinitionRepository;
        this.processVersionRepository = processVersionRepository;
        this.stepDefinitionRepository = stepDefinitionRepository;
        this.processInterfaceRepository = processInterfaceRepository;
        this.processGraphProjectionService = processGraphProjectionService;
        this.outboxService = outboxService;
    }

    @Override
    public Mono<ProcessDefinitionResponse> createProcess(CreateProcessDefinitionRequest request) {
        return TenantContextHolder.getCurrent()
                .flatMap(context -> {
                    ProcessDefinitionEntity entity = new ProcessDefinitionEntity();
                    entity.setId(UUID.randomUUID());
                    entity.setTenantId(context.tenantId());
                    entity.setOrgUnitId(request.orgUnitId());
                    entity.setWorkspaceId(request.workspaceId());
                    entity.setProcessKey(request.processKey());
                    entity.setName(request.name());
                    entity.setDescription(request.description());
                    entity.setDomainCode(request.domainCode());
                    entity.setOwnerRoleCode(request.ownerRoleCode());
                    entity.setStatus("DRAFT");
                    entity.setCreatedAt(LocalDateTime.now());
                    entity.setUpdatedAt(LocalDateTime.now());

                    return processDefinitionRepository.save(entity)
                            .flatMap(saved -> outboxService.enqueue(
                                    context.tenantId(),
                                    "ProcessDefinition",
                                    saved.getId(),
                                    "process.definition.created",
                                    saved
                            ).thenReturn(saved))
                            .flatMap(processGraphProjectionService::upsertProcessNode)
                            .map(this::toResponse);
                });
    }

    @Override
    public Flux<ProcessDefinitionResponse> listByWorkspace(UUID workspaceId) {
        return TenantContextHolder.getCurrent()
                .flatMapMany(context -> processDefinitionRepository
                        .findByTenantIdAndWorkspaceId(context.tenantId(), workspaceId)
                        .map(this::toResponse));
    }

    @Override
    public Mono<UUID> createVersion(CreateProcessVersionRequest request) {
        return TenantContextHolder.getCurrent()
                .flatMap(context -> processVersionRepository.findByProcessDefinitionId(request.processDefinitionId())
                        .count()
                        .map(count -> {
                            ProcessVersionEntity version = new ProcessVersionEntity();
                            version.setId(UUID.randomUUID());
                            version.setTenantId(context.tenantId());
                            version.setProcessDefinitionId(request.processDefinitionId());
                            version.setVersionNo((int) count + 1);
                            version.setIsCurrent(Boolean.TRUE);
                            version.setStatus("DRAFT");
                            version.setCreatedAt(LocalDateTime.now());
                            version.setUpdatedAt(LocalDateTime.now());
                            return version;
                        })
                        .flatMap(processVersionRepository::save)
                        .flatMap(saved -> outboxService.enqueue(
                                context.tenantId(),
                                "ProcessVersion",
                                saved.getId(),
                                "process.version.created",
                                saved
                        ).thenReturn(saved.getId()))
                );
    }

    @Override
    public Mono<ImpactAnalysisResponse> analyzeImpact(UUID processDefinitionId, int depth) {
        return processGraphProjectionService.analyzeImpact(processDefinitionId, depth);
    }

    private ProcessDefinitionResponse toResponse(ProcessDefinitionEntity entity) {
        return new ProcessDefinitionResponse(
                entity.getId(),
                entity.getTenantId(),
                entity.getOrgUnitId(),
                entity.getWorkspaceId(),
                entity.getProcessKey(),
                entity.getName(),
                entity.getDescription(),
                entity.getDomainCode(),
                entity.getOwnerRoleCode(),
                entity.getStatus(),
                entity.getCreatedAt(),
                entity.getUpdatedAt()
        );
    }
}
