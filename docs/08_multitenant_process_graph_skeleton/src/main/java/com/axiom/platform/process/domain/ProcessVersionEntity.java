package com.axiom.platform.process.domain;

import java.time.LocalDateTime;
import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.process_versions")
public class ProcessVersionEntity extends AuditableEntity {

    @Column("process_definition_id")
    private UUID processDefinitionId;

    @Column("version_no")
    private Integer versionNo;

    @Column("is_current")
    private Boolean isCurrent;

    @Column("published_at")
    private LocalDateTime publishedAt;

    @Column("effective_from")
    private LocalDateTime effectiveFrom;

    @Column("effective_to")
    private LocalDateTime effectiveTo;

    private String status;

    public UUID getProcessDefinitionId() { return processDefinitionId; }
    public void setProcessDefinitionId(UUID processDefinitionId) { this.processDefinitionId = processDefinitionId; }

    public Integer getVersionNo() { return versionNo; }
    public void setVersionNo(Integer versionNo) { this.versionNo = versionNo; }

    public Boolean getIsCurrent() { return isCurrent; }
    public void setIsCurrent(Boolean current) { isCurrent = current; }

    public LocalDateTime getPublishedAt() { return publishedAt; }
    public void setPublishedAt(LocalDateTime publishedAt) { this.publishedAt = publishedAt; }

    public LocalDateTime getEffectiveFrom() { return effectiveFrom; }
    public void setEffectiveFrom(LocalDateTime effectiveFrom) { this.effectiveFrom = effectiveFrom; }

    public LocalDateTime getEffectiveTo() { return effectiveTo; }
    public void setEffectiveTo(LocalDateTime effectiveTo) { this.effectiveTo = effectiveTo; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
