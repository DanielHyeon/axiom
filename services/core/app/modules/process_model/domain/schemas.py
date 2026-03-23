"""프로세스 모델 도메인 — Pydantic 요청/응답 DTO."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.process_model.domain.enums import (
    ActorType, AggregationType, AutomationLevel, ContractType,
    Criticality, LifecycleStatus, ProcessType, RelationType,
    RuleType, StepType, TargetDirection, TransitionType,
)


# ── ProcessDomain ──────────────────────────────────────────

class ProcessDomainCreate(BaseModel):
    workspace_id: UUID
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    domain_type: str | None = None
    description: str | None = None

class ProcessDomainResponse(BaseModel):
    id: UUID
    tenant_id: str
    workspace_id: UUID
    code: str
    name: str
    domain_type: str | None
    description: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── ProcessDefinition ──────────────────────────────────────

class ProcessDefinitionCreate(BaseModel):
    workspace_id: UUID
    domain_id: UUID
    group_id: UUID | None = None
    namespace: str = Field(..., max_length=300)
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    description: str | None = None
    process_type: ProcessType
    owner_org_unit_id: UUID | None = None
    primary_role_code: str | None = None
    is_template: bool = False

class ProcessDefinitionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    owner_org_unit_id: UUID | None = None
    primary_role_code: str | None = None
    expected_version: int  # CAS용

class ProcessDefinitionResponse(BaseModel):
    id: UUID
    tenant_id: str
    workspace_id: UUID
    domain_id: UUID
    namespace: str
    code: str
    name: str
    description: str | None
    process_type: str
    lifecycle_status: str
    current_version_id: UUID | None
    is_template: bool
    version: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── ProcessVersion ─────────────────────────────────────────

class ProcessVersionResponse(BaseModel):
    id: UUID
    process_definition_id: UUID
    version_no: int
    status: str
    change_summary: str | None
    hash: str | None
    published_at: datetime | None
    valid_from: datetime | None
    valid_to: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── StepDefinition ─────────────────────────────────────────

class StepDefinitionUpsert(BaseModel):
    id: UUID | None = None  # None이면 신규 생성
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    step_type: StepType
    actor_type: ActorType
    actor_ref: str | None = None
    automation_level: AutomationLevel = AutomationLevel.MANUAL
    input_contract_id: UUID | None = None
    output_contract_id: UUID | None = None
    rule_set_id: UUID | None = None
    sla_minutes: int | None = None
    auto_executable: bool = False
    display_order: int = 0
    parent_step_id: UUID | None = None
    ui_metadata_json: dict | None = None

class BulkUpsertStepsRequest(BaseModel):
    expected_version: int  # CAS — 클라이언트가 본 process_version.version
    steps: list[StepDefinitionUpsert]

class StepDefinitionResponse(BaseModel):
    id: UUID
    process_version_id: UUID
    code: str
    name: str
    step_type: str
    actor_type: str
    automation_level: str
    sla_minutes: int | None
    display_order: int
    created_at: datetime
    model_config = {"from_attributes": True}


# ── ProcessRelation ────────────────────────────────────────

class ProcessRelationCreate(BaseModel):
    workspace_id: UUID
    source_entity_type: str
    source_entity_id: UUID
    target_entity_type: str
    target_entity_id: UUID
    relation_type: RelationType
    criticality: Criticality = Criticality.MEDIUM
    propagation_mode: str | None = None
    weight: float | None = None

class ProcessRelationResponse(BaseModel):
    id: UUID
    source_entity_type: str
    source_entity_id: UUID
    target_entity_type: str
    target_entity_id: UUID
    relation_type: str
    criticality: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── InterfaceContract ──────────────────────────────────────

class InterfaceContractCreate(BaseModel):
    workspace_id: UUID
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    contract_type: ContractType
    schema_json: dict
    semantic_type: str | None = None
    version_label: str | None = None

class InterfaceContractResponse(BaseModel):
    id: UUID
    code: str
    name: str
    contract_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── RuleDefinition ─────────────────────────────────────────

class RuleDefinitionCreate(BaseModel):
    workspace_id: UUID
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    rule_type: RuleType
    expression_language: str
    expression_text: str
    severity: str | None = None
    description: str | None = None

class RuleDefinitionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    rule_type: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── KpiDefinition ──────────────────────────────────────────

class KpiDefinitionCreate(BaseModel):
    workspace_id: UUID
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    unit: str | None = None
    target_direction: TargetDirection
    aggregation_type: AggregationType
    formula_text: str | None = None

class KpiDefinitionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    unit: str | None
    target_direction: str
    aggregation_type: str
    created_at: datetime
    model_config = {"from_attributes": True}
