package com.axiom.platform.governance.domain;

import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.workspaces")
public class WorkspaceEntity extends AuditableEntity {

    @Column("org_unit_id")
    private UUID orgUnitId;

    private String code;
    private String name;

    @Column("domain_type")
    private String domainType;

    private String status;

    public UUID getOrgUnitId() { return orgUnitId; }
    public void setOrgUnitId(UUID orgUnitId) { this.orgUnitId = orgUnitId; }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getDomainType() { return domainType; }
    public void setDomainType(String domainType) { this.domainType = domainType; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
