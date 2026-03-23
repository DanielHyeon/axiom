package com.axiom.platform.twin.domain;

import java.time.LocalDateTime;
import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.process_instances")
public class ProcessInstanceEntity extends AuditableEntity {

    @Column("process_definition_id")
    private UUID processDefinitionId;

    @Column("process_version_id")
    private UUID processVersionId;

    @Column("business_case_id")
    private String businessCaseId;

    private String status;

    @Column("started_at")
    private LocalDateTime startedAt;

    @Column("completed_at")
    private LocalDateTime completedAt;

    @Column("current_step_key")
    private String currentStepKey;

    @Column("current_assignee_id")
    private String currentAssigneeId;

    private String priority;

    @Column("correlation_id")
    private String correlationId;

    public UUID getProcessDefinitionId() { return processDefinitionId; }
    public void setProcessDefinitionId(UUID processDefinitionId) { this.processDefinitionId = processDefinitionId; }

    public UUID getProcessVersionId() { return processVersionId; }
    public void setProcessVersionId(UUID processVersionId) { this.processVersionId = processVersionId; }

    public String getBusinessCaseId() { return businessCaseId; }
    public void setBusinessCaseId(String businessCaseId) { this.businessCaseId = businessCaseId; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public LocalDateTime getStartedAt() { return startedAt; }
    public void setStartedAt(LocalDateTime startedAt) { this.startedAt = startedAt; }

    public LocalDateTime getCompletedAt() { return completedAt; }
    public void setCompletedAt(LocalDateTime completedAt) { this.completedAt = completedAt; }

    public String getCurrentStepKey() { return currentStepKey; }
    public void setCurrentStepKey(String currentStepKey) { this.currentStepKey = currentStepKey; }

    public String getCurrentAssigneeId() { return currentAssigneeId; }
    public void setCurrentAssigneeId(String currentAssigneeId) { this.currentAssigneeId = currentAssigneeId; }

    public String getPriority() { return priority; }
    public void setPriority(String priority) { this.priority = priority; }

    public String getCorrelationId() { return correlationId; }
    public void setCorrelationId(String correlationId) { this.correlationId = correlationId; }
}
