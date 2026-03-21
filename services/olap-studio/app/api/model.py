"""스타 스키마 모델 API — Dimension/Fact/Join 관리."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

from app.core.context import get_request_context, require_capability
from app.core.database import execute_query, execute_command

router = APIRouter(prefix="/models", tags=["모델"])


class ModelCreate(BaseModel):
    name: str
    description: str = ""
    source_id: UUID | None = None


class DimensionCreate(BaseModel):
    name: str
    physical_table_name: str
    grain_description: str = ""
    column_map: dict = Field(default_factory=dict)
    hierarchies: list = Field(default_factory=list)
    attributes: list = Field(default_factory=list)


class FactCreate(BaseModel):
    name: str
    physical_table_name: str
    grain_description: str = ""
    measures: list = Field(default_factory=list)
    degenerate_dimensions: list = Field(default_factory=list)


class JoinCreate(BaseModel):
    left_entity_type: str  # FACT, DIMENSION
    left_entity_id: UUID
    right_entity_type: str
    right_entity_id: UUID
    join_type: str = "INNER"
    join_expression: str = ""
    cardinality: str = "1:N"


@router.get("")
async def list_models(request: Request):
    """모델 목록 조회."""
    ctx = get_request_context(request)
    rows = await execute_query(
        """SELECT id, name, description, model_status, semantic_version, created_at
        FROM olap.models
        WHERE tenant_id = $1 AND project_id = $2 AND deleted_at IS NULL
        ORDER BY created_at DESC""",
        [ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": rows}


@router.post("")
async def create_model(body: ModelCreate, request: Request):
    """스타 스키마 모델 생성."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:write")
    rows = await execute_query(
        """INSERT INTO olap.models (tenant_id, project_id, name, description, source_id, created_by, updated_by)
        VALUES ($1, $2, $3, $4, $5, $6, $6)
        RETURNING id, name, description, model_status, created_at""",
        [ctx.tenant_id, ctx.project_id, body.name, body.description,
         str(body.source_id) if body.source_id else None, ctx.user_id],
    )
    return {"success": True, "data": rows[0] if rows else None}


@router.get("/{model_id}")
async def get_model(model_id: UUID, request: Request):
    """모델 상세 + 차원/팩트/조인 목록 조회."""
    ctx = get_request_context(request)
    model_rows = await execute_query(
        """SELECT id, name, description, model_status, semantic_version, source_id, published_at, created_at
        FROM olap.models WHERE id = $1 AND tenant_id = $2 AND project_id = $3 AND deleted_at IS NULL""",
        [str(model_id), ctx.tenant_id, ctx.project_id],
    )
    if not model_rows:
        raise HTTPException(status_code=404, detail="모델을 찾을 수 없습니다")

    dims = await execute_query(
        "SELECT id, name, physical_table_name, grain_description FROM olap.dimensions WHERE model_id = $1",
        [str(model_id)],
    )
    facts = await execute_query(
        "SELECT id, name, physical_table_name, grain_description FROM olap.facts WHERE model_id = $1",
        [str(model_id)],
    )
    joins = await execute_query(
        "SELECT id, left_entity_type, left_entity_id, right_entity_type, right_entity_id, join_type, cardinality FROM olap.joins WHERE model_id = $1",
        [str(model_id)],
    )
    return {"success": True, "data": {**model_rows[0], "dimensions": dims, "facts": facts, "joins": joins}}


@router.post("/{model_id}/dimensions")
async def add_dimension(model_id: UUID, body: DimensionCreate, request: Request):
    """모델에 차원 추가."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:write")
    import json
    rows = await execute_query(
        """INSERT INTO olap.dimensions (model_id, name, physical_table_name, grain_description, column_map, hierarchies, attributes)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb)
        RETURNING id, name, physical_table_name""",
        [str(model_id), body.name, body.physical_table_name, body.grain_description,
         json.dumps(body.column_map), json.dumps(body.hierarchies), json.dumps(body.attributes)],
    )
    return {"success": True, "data": rows[0] if rows else None}


@router.post("/{model_id}/facts")
async def add_fact(model_id: UUID, body: FactCreate, request: Request):
    """모델에 팩트 테이블 추가."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:write")
    import json
    rows = await execute_query(
        """INSERT INTO olap.facts (model_id, name, physical_table_name, grain_description, measures, degenerate_dimensions)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
        RETURNING id, name, physical_table_name""",
        [str(model_id), body.name, body.physical_table_name, body.grain_description,
         json.dumps(body.measures), json.dumps(body.degenerate_dimensions)],
    )
    return {"success": True, "data": rows[0] if rows else None}


@router.post("/{model_id}/joins")
async def add_join(model_id: UUID, body: JoinCreate, request: Request):
    """모델에 조인 정의 추가."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:write")
    rows = await execute_query(
        """INSERT INTO olap.joins (model_id, left_entity_type, left_entity_id, right_entity_type, right_entity_id, join_type, join_expression, cardinality)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, join_type, cardinality""",
        [str(model_id), body.left_entity_type, str(body.left_entity_id),
         body.right_entity_type, str(body.right_entity_id),
         body.join_type, body.join_expression, body.cardinality],
    )
    return {"success": True, "data": rows[0] if rows else None}
