package com.axiom.platform.governance.domain;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.tenants")
public class TenantEntity extends AuditableEntity {

    private String code;
    private String name;
    private String status;
    private String industryCode;
    private String defaultTimezone;

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getIndustryCode() { return industryCode; }
    public void setIndustryCode(String industryCode) { this.industryCode = industryCode; }

    public String getDefaultTimezone() { return defaultTimezone; }
    public void setDefaultTimezone(String defaultTimezone) { this.defaultTimezone = defaultTimezone; }
}
