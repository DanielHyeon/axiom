package com.axiom.platform.process.api;

import java.util.UUID;

import com.axiom.platform.process.api.dto.CreateProcessDefinitionRequest;
import com.axiom.platform.process.api.dto.CreateProcessVersionRequest;
import com.axiom.platform.process.api.dto.ImpactAnalysisResponse;
import com.axiom.platform.process.api.dto.ProcessDefinitionResponse;
import com.axiom.platform.process.service.ProcessDefinitionService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@RestController
@RequestMapping("/api/process-definitions")
public class ProcessDefinitionController {

    private final ProcessDefinitionService processDefinitionService;

    public ProcessDefinitionController(ProcessDefinitionService processDefinitionService) {
        this.processDefinitionService = processDefinitionService;
    }

    @PostMapping
    public Mono<ProcessDefinitionResponse> create(@Valid @RequestBody CreateProcessDefinitionRequest request) {
        return processDefinitionService.createProcess(request);
    }

    @GetMapping
    public Flux<ProcessDefinitionResponse> listByWorkspace(@RequestParam UUID workspaceId) {
        return processDefinitionService.listByWorkspace(workspaceId);
    }

    @PostMapping("/versions")
    public Mono<UUID> createVersion(@Valid @RequestBody CreateProcessVersionRequest request) {
        return processDefinitionService.createVersion(request);
    }

    @GetMapping("/{processDefinitionId}/impact")
    public Mono<ImpactAnalysisResponse> analyzeImpact(
            @PathVariable UUID processDefinitionId,
            @RequestParam(defaultValue = "3") int depth
    ) {
        return processDefinitionService.analyzeImpact(processDefinitionId, depth);
    }
}
