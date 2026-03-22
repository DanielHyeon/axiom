package com.axiom.platform.twin.domain;

import java.util.UUID;

import com.axiom.platform.common.model.AuditableEntity;
import org.springframework.data.relational.core.mapping.Column;
import org.springframework.data.relational.core.mapping.Table;

@Table("axiom.twin_scenarios")
public class TwinScenarioEntity extends AuditableEntity {

    @Column("scenario_key")
    private String scenarioKey;

    private String name;

    @Column("base_snapshot_id")
    private UUID baseSnapshotId;

    private String status;

    @Column("assumption_json")
    private String assumptionJson;

    @Column("created_by")
    private String createdBy;

    public String getScenarioKey() { return scenarioKey; }
    public void setScenarioKey(String scenarioKey) { this.scenarioKey = scenarioKey; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public UUID getBaseSnapshotId() { return baseSnapshotId; }
    public void setBaseSnapshotId(UUID baseSnapshotId) { this.baseSnapshotId = baseSnapshotId; }

    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }

    public String getAssumptionJson() { return assumptionJson; }
    public void setAssumptionJson(String assumptionJson) { this.assumptionJson = assumptionJson; }

    public String getCreatedBy() { return createdBy; }
    public void setCreatedBy(String createdBy) { this.createdBy = createdBy; }
}
