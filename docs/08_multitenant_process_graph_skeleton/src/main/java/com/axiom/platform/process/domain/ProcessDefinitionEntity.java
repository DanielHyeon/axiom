package com.axiom.platform.process.domain;

import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.process_definitions")
public class ProcessDefinitionEntity extends AuditableEntity {

    @Column("org_unit_id")
    private UUID orgUnitId;

    @Column("workspace_id")
    private UUID workspaceId;

    @Column("process_key")
    private String processKey;

    private String name;
    private String description;

    @Column("domain_code")
    private String domainCode;

    @Column("owner_role_code")
    private String ownerRoleCode;

    private String status;

    public UUID getOrgUnitId() { return orgUnitId; }
    public void setOrgUnitId(UUID orgUnitId) { this.orgUnitId = orgUnitId; }

    public UUID getWorkspaceId() { return workspaceId; }
    public void setWorkspaceId(UUID workspaceId) { this.workspaceId = workspaceId; }

    public String getProcessKey() { return processKey; }
    public void setProcessKey(String processKey) { this.processKey = processKey; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }

    public String getDomainCode() { return domainCode; }
    public void setDomainCode(String domainCode) { this.domainCode = domainCode; }

    public String getOwnerRoleCode() { return ownerRoleCode; }
    public void setOwnerRoleCode(String ownerRoleCode) { this.ownerRoleCode = ownerRoleCode; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
