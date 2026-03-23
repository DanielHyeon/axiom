package com.axiom.platform.process.domain;

import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.step_definitions")
public class StepDefinitionEntity extends AuditableEntity {

    @Column("process_version_id")
    private UUID processVersionId;

    @Column("step_key")
    private String stepKey;

    private String name;

    @Column("step_type")
    private String stepType;

    @Column("sequence_no")
    private Integer sequenceNo;

    @Column("owner_role_code")
    private String ownerRoleCode;

    @Column("input_contract_code")
    private String inputContractCode;

    @Column("output_contract_code")
    private String outputContractCode;

    @Column("sla_minutes")
    private Integer slaMinutes;

    @Column("is_automated")
    private Boolean automated;

    private String status;

    public UUID getProcessVersionId() { return processVersionId; }
    public void setProcessVersionId(UUID processVersionId) { this.processVersionId = processVersionId; }

    public String getStepKey() { return stepKey; }
    public void setStepKey(String stepKey) { this.stepKey = stepKey; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getStepType() { return stepType; }
    public void setStepType(String stepType) { this.stepType = stepType; }

    public Integer getSequenceNo() { return sequenceNo; }
    public void setSequenceNo(Integer sequenceNo) { this.sequenceNo = sequenceNo; }

    public String getOwnerRoleCode() { return ownerRoleCode; }
    public void setOwnerRoleCode(String ownerRoleCode) { this.ownerRoleCode = ownerRoleCode; }

    public String getInputContractCode() { return inputContractCode; }
    public void setInputContractCode(String inputContractCode) { this.inputContractCode = inputContractCode; }

    public String getOutputContractCode() { return outputContractCode; }
    public void setOutputContractCode(String outputContractCode) { this.outputContractCode = outputContractCode; }

    public Integer getSlaMinutes() { return slaMinutes; }
    public void setSlaMinutes(Integer slaMinutes) { this.slaMinutes = slaMinutes; }

    public Boolean getAutomated() { return automated; }
    public void setAutomated(Boolean automated) { this.automated = automated; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
