package com.axiom.platform.process.domain;

import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.process_interfaces")
public class ProcessInterfaceEntity extends AuditableEntity {

    @Column("process_version_id")
    private UUID processVersionId;

    @Column("interface_code")
    private String interfaceCode;

    private String direction;

    @Column("payload_type")
    private String payloadType;

    @Column("schema_ref")
    private String schemaRef;

    @Column("required_flag")
    private Boolean requiredFlag;

    public UUID getProcessVersionId() { return processVersionId; }
    public void setProcessVersionId(UUID processVersionId) { this.processVersionId = processVersionId; }

    public String getInterfaceCode() { return interfaceCode; }
    public void setInterfaceCode(String interfaceCode) { this.interfaceCode = interfaceCode; }

    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }

    public String getPayloadType() { return payloadType; }
    public void setPayloadType(String payloadType) { this.payloadType = payloadType; }

    public String getSchemaRef() { return schemaRef; }
    public void setSchemaRef(String schemaRef) { this.schemaRef = schemaRef; }

    public Boolean getRequiredFlag() { return requiredFlag; }
    public void setRequiredFlag(Boolean requiredFlag) { this.requiredFlag = requiredFlag; }
}
