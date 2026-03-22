package com.axiom.platform.governance.domain;

import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.org_units")
public class OrgUnitEntity extends AuditableEntity {

    @Column("parent_org_unit_id")
    private UUID parentOrgUnitId;

    private String code;
    private String name;

    @Column("org_type")
    private String orgType;

    private String status;

    public UUID getParentOrgUnitId() { return parentOrgUnitId; }
    public void setParentOrgUnitId(UUID parentOrgUnitId) { this.parentOrgUnitId = parentOrgUnitId; }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getOrgType() { return orgType; }
    public void setOrgType(String orgType) { this.orgType = orgType; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
