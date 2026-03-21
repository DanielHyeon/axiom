"""큐브 API — 큐브 CRUD + 검증 + 게시."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.core.context import get_request_context, require_capability
from app.core.database import execute_query, execute_command
from app.events.publisher import emit_cube_published

router = APIRouter(prefix="/cubes", tags=["큐브"])


class CubeCreate(BaseModel):
    name: str
    description: str = ""
    model_id: UUID | None = None
    ai_generated: bool = False


@router.get("")
async def list_cubes(request: Request):
    """큐브 목록 조회."""
    ctx = get_request_context(request)
    rows = await execute_query(
        """SELECT id, name, description, cube_status, ai_generated, model_id, created_at, version_no
        FROM olap.cubes
        WHERE tenant_id = $1 AND project_id = $2 AND deleted_at IS NULL
        ORDER BY created_at DESC""",
        [ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": rows}


@router.post("")
async def create_cube(body: CubeCreate, request: Request):
    """큐브 생성."""
    ctx = get_request_context(request)
    require_capability(ctx, "datasource:write")
    rows = await execute_query(
        """INSERT INTO olap.cubes (tenant_id, project_id, name, description, model_id, ai_generated, created_by, updated_by)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
        RETURNING id, name, description, cube_status, created_at""",
        [ctx.tenant_id, ctx.project_id, body.name, body.description,
         str(body.model_id) if body.model_id else None, body.ai_generated, ctx.user_id],
    )
    return {"success": True, "data": rows[0] if rows else None}


@router.get("/{cube_id}")
async def get_cube(cube_id: UUID, request: Request):
    """큐브 상세 조회 (차원/측정값 포함)."""
    ctx = get_request_context(request)
    cube_rows = await execute_query(
        """SELECT id, name, description, cube_status, model_id, ai_generated, metadata, created_at, version_no
        FROM olap.cubes WHERE id = $1 AND tenant_id = $2 AND project_id = $3 AND deleted_at IS NULL""",
        [str(cube_id), ctx.tenant_id, ctx.project_id],
    )
    if not cube_rows:
        raise HTTPException(status_code=404, detail="큐브를 찾을 수 없습니다")

    dims = await execute_query(
        "SELECT id, dimension_name, source_dimension_id, display_order FROM olap.cube_dimensions WHERE cube_id = $1 ORDER BY display_order",
        [str(cube_id)],
    )
    measures = await execute_query(
        "SELECT id, measure_name, aggregation_type, expression, format_string, display_order FROM olap.cube_measures WHERE cube_id = $1 ORDER BY display_order",
        [str(cube_id)],
    )
    return {"success": True, "data": {**cube_rows[0], "dimensions": dims, "measures": measures}}


@router.post("/{cube_id}/validate")
async def validate_cube(cube_id: UUID, request: Request):
    """큐브 구조 검증 — 필수 차원/측정값 존재 여부 확인."""
    ctx = get_request_context(request)
    require_capability(ctx, "cube:publish")

    # 테넌트 소유권 확인 — 다른 테넌트의 큐브 변경 방지
    cube_check = await execute_query(
        "SELECT id FROM olap.cubes WHERE id = $1 AND tenant_id = $2 AND project_id = $3 AND deleted_at IS NULL",
        [str(cube_id), ctx.tenant_id, ctx.project_id],
    )
    if not cube_check:
        raise HTTPException(status_code=404, detail="큐브를 찾을 수 없습니다")

    dims = await execute_query(
        "SELECT count(*) AS cnt FROM olap.cube_dimensions WHERE cube_id = $1", [str(cube_id)],
    )
    measures = await execute_query(
        "SELECT count(*) AS cnt FROM olap.cube_measures WHERE cube_id = $1", [str(cube_id)],
    )
    errors = []
    if not dims or dims[0]["cnt"] == 0:
        errors.append({"code": "NO_DIMENSIONS", "message": "차원이 하나도 없습니다"})
    if not measures or measures[0]["cnt"] == 0:
        errors.append({"code": "NO_MEASURES", "message": "측정값이 하나도 없습니다"})

    status = "VALIDATED" if not errors else "FAILED"
    await execute_command(
        "UPDATE olap.cubes SET cube_status = $2, updated_at = now() WHERE id = $1 AND tenant_id = $3 AND project_id = $4",
        [str(cube_id), status, ctx.tenant_id, ctx.project_id],
    )
    return {"success": True, "data": {"status": status, "errors": errors}}


@router.post("/{cube_id}/publish")
async def publish_cube(cube_id: UUID, request: Request):
    """큐브 게시 — VALIDATED 상태에서만 가능."""
    ctx = get_request_context(request)
    require_capability(ctx, "cube:publish")

    cube = await execute_query(
        "SELECT cube_status FROM olap.cubes WHERE id = $1 AND tenant_id = $2 AND project_id = $3",
        [str(cube_id), ctx.tenant_id, ctx.project_id],
    )
    if not cube:
        raise HTTPException(status_code=404, detail="큐브를 찾을 수 없습니다")
    if cube[0]["cube_status"] not in ("VALIDATED", "PUBLISHED"):
        raise HTTPException(status_code=400, detail=f"현재 상태({cube[0]['cube_status']})에서는 게시할 수 없습니다. 먼저 검증하세요.")

    await execute_command(
        """UPDATE olap.cubes SET cube_status = 'PUBLISHED', version_no = version_no + 1, updated_at = now(), updated_by = $2
        WHERE id = $1 AND tenant_id = $3 AND project_id = $4""",
        [str(cube_id), ctx.user_id, ctx.tenant_id, ctx.project_id],
    )

    # 게시 완료 이벤트 발행 — 큐브 최신 정보 조회 후 Outbox에 기록
    try:
        updated = await execute_query(
            "SELECT name, model_id, version_no FROM olap.cubes WHERE id = $1",
            [str(cube_id)],
        )
        if updated:
            await emit_cube_published(
                tenant_id=ctx.tenant_id,
                project_id=ctx.project_id,
                cube_id=str(cube_id),
                model_id=updated[0].get("model_id") or "",
                cube_name=updated[0]["name"],
                version_no=updated[0]["version_no"],
            )
    except Exception:
        # 이벤트 발행 실패가 게시 응답을 방해하지 않도록 경고만 남긴다
        import structlog
        structlog.get_logger().warning(
            "cube_publish_event_emit_failed",
            cube_id=str(cube_id),
            exc_info=True,
        )

    return {"success": True, "data": {"cube_id": str(cube_id), "status": "PUBLISHED"}}
