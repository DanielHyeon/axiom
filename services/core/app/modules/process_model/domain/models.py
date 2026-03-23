"""
프로세스 모델 도메인 — SQLAlchemy ORM 모델.

Phase 2: 12개 테이블. 기존 Column() 스타일 유지.
tenant_id는 VARCHAR (기존 tenants.id 호환), 신규 PK는 UUID.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Index, Integer, Numeric, String, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.database import Base


class ProcessDomain(Base):
    """프로세스 도메인 — 업무 영역 분류."""
    __tablename__ = "process_domains"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    domain_type = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProcessGroup(Base):
    """프로세스 그룹 — 폴더 구조."""
    __tablename__ = "process_groups"
    __table_args__ = (
        Index("idx_process_groups_tenant_domain", "tenant_id", "domain_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    domain_id = Column(UUID(as_uuid=True), ForeignKey("process_domains.id"), nullable=False)
    parent_group_id = Column(UUID(as_uuid=True), ForeignKey("process_groups.id"), nullable=True)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    path = Column(String(1000), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProcessDefinition(Base):
    """프로세스 정의 — 업무 프로세스의 설계도."""
    __tablename__ = "process_definitions"
    __table_args__ = (
        Index("idx_process_definitions_tenant_domain", "tenant_id", "domain_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    domain_id = Column(UUID(as_uuid=True), ForeignKey("process_domains.id"), nullable=False)
    group_id = Column(UUID(as_uuid=True), ForeignKey("process_groups.id"), nullable=True)
    namespace = Column(String(300), nullable=False)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    process_type = Column(String(50), nullable=False)
    lifecycle_status = Column(String(30), nullable=False, default="DRAFT", server_default=text("'DRAFT'"))
    owner_org_unit_id = Column(UUID(as_uuid=True), ForeignKey("org_units.id"), nullable=True)
    primary_role_code = Column(String(100), nullable=True)
    # FK는 process_versions 생성 후 ALTER로 추가 (DEFERRABLE)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    is_template = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    template_source_id = Column(UUID(as_uuid=True), nullable=True)
    ontology_concept_id = Column(String(128), nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ProcessVersion(Base):
    """프로세스 버전 — 정의의 스냅샷."""
    __tablename__ = "process_versions"
    __table_args__ = (
        Index("idx_process_versions_tenant_def", "tenant_id", "process_definition_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    process_definition_id = Column(UUID(as_uuid=True), ForeignKey("process_definitions.id"), nullable=False)
    version_no = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="DRAFT", server_default=text("'DRAFT'"))
    source_type = Column(String(30), nullable=False, default="MANUAL", server_default=text("'MANUAL'"))
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("process_versions.id"), nullable=True)
    change_summary = Column(Text, nullable=True)
    hash = Column(String(128), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    published_by = Column(String, nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class StepDefinition(Base):
    """단계 정의 — 프로세스 내 각 스텝."""
    __tablename__ = "step_definitions"
    __table_args__ = (
        Index("idx_step_definitions_version", "tenant_id", "process_version_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    process_version_id = Column(UUID(as_uuid=True), ForeignKey("process_versions.id"), nullable=False)
    parent_step_id = Column(UUID(as_uuid=True), ForeignKey("step_definitions.id"), nullable=True)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    step_type = Column(String(50), nullable=False)
    actor_type = Column(String(50), nullable=False)
    actor_ref = Column(String(200), nullable=True)
    automation_level = Column(String(32), nullable=False, default="MANUAL", server_default=text("'MANUAL'"))
    input_contract_id = Column(UUID(as_uuid=True), ForeignKey("interface_contracts.id"), nullable=True)
    output_contract_id = Column(UUID(as_uuid=True), ForeignKey("interface_contracts.id"), nullable=True)
    rule_set_id = Column(UUID(as_uuid=True), ForeignKey("rule_definitions.id"), nullable=True)
    sla_minutes = Column(Integer, nullable=True)
    auto_executable = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    display_order = Column(Integer, nullable=False, default=0)
    path = Column(String(1000), nullable=False)
    ui_metadata_json = Column(JSONB, nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class StepTransitionEdge(Base):
    """단계 간 전이 — 분기/병합/예외 경로."""
    __tablename__ = "step_transition_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    process_version_id = Column(UUID(as_uuid=True), ForeignKey("process_versions.id"), nullable=False)
    from_step_id = Column(UUID(as_uuid=True), ForeignKey("step_definitions.id"), nullable=False)
    to_step_id = Column(UUID(as_uuid=True), ForeignKey("step_definitions.id"), nullable=False)
    transition_type = Column(String(50), nullable=False)
    condition_expression = Column(Text, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    display_order = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSONB, nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class InterfaceContract(Base):
    """인터페이스 계약 — 입출력 스키마 정의."""
    __tablename__ = "interface_contracts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    contract_type = Column(String(50), nullable=False)
    schema_json = Column(JSONB, nullable=False)
    semantic_type = Column(String(100), nullable=True)
    version_label = Column(String(50), nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RuleDefinition(Base):
    """규칙 정의."""
    __tablename__ = "rule_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    rule_type = Column(String(50), nullable=False)
    expression_language = Column(String(50), nullable=False)
    expression_text = Column(Text, nullable=False)
    severity = Column(String(30), nullable=True)
    description = Column(Text, nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class KpiDefinition(Base):
    """KPI 정의."""
    __tablename__ = "kpi_definitions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    code = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=True)
    target_direction = Column(String(20), nullable=False)
    aggregation_type = Column(String(30), nullable=False)
    formula_text = Column(Text, nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class StepKpiBinding(Base):
    """Step ↔ KPI 바인딩 (N:M)."""
    __tablename__ = "step_kpi_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    step_definition_id = Column(UUID(as_uuid=True), ForeignKey("step_definitions.id"), nullable=False)
    kpi_definition_id = Column(UUID(as_uuid=True), ForeignKey("kpi_definitions.id"), nullable=False)
    binding_type = Column(String(30), nullable=False, default="MEASURED_BY")
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProcessRelationEdge(Base):
    """프로세스 간 관계 엣지 — Graph Projection 원천."""
    __tablename__ = "process_relation_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    source_entity_type = Column(String(50), nullable=False)
    source_entity_id = Column(UUID(as_uuid=True), nullable=False)
    target_entity_type = Column(String(50), nullable=False)
    target_entity_id = Column(UUID(as_uuid=True), nullable=False)
    relation_type = Column(String(50), nullable=False)
    criticality = Column(String(16), nullable=False, default="MEDIUM")
    propagation_mode = Column(String(16), nullable=True)
    weight = Column(Numeric(10, 4), nullable=True)
    condition_expression = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_to = Column(DateTime(timezone=True), nullable=True)
    version = Column(BigInteger, nullable=False, default=0, server_default=text("0"))
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class BpmProcessDefinitionBridge(Base):
    """기존 BPM ↔ 신규 ProcessDefinition 매핑."""
    __tablename__ = "bpm_process_definition_bridge"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    legacy_bpm_definition_id = Column(String, nullable=False, unique=True)
    new_process_definition_id = Column(UUID(as_uuid=True), ForeignKey("process_definitions.id"), nullable=False)
    migration_status = Column(String(30), nullable=False, default="MAPPED")
    migrated_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
