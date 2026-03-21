"""자동 데이터소스 바인딩 API -- 온톨로지 엔티티를 DB 테이블에 매핑."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.auto_binding_service import auto_bind_entities

router = APIRouter(prefix="/api/v2/weaver/auto-binding", tags=["자동 바인딩"])


class AutoBindRequest(BaseModel):
    """자동 바인딩 요청 바디."""

    entities: list[str] = Field(description="바인딩할 온톨로지 엔티티 이름 목록")
    datasource_name: str = Field(default="", description="대상 데이터소스 이름")
    available_tables: list[dict] = Field(
        default_factory=list,
        description="사용 가능한 테이블 목록 [{name, schema, columns}]",
    )


@router.post("/bind")
async def api_auto_bind(body: AutoBindRequest):
    """온톨로지 엔티티를 데이터소스에 자동 바인딩한다.

    Phase 1 (이름 기반)을 수행하고 결과를 반환한다.
    각 엔티티의 status는 bound / partial / unbound 중 하나.
    """
    results = await auto_bind_entities(
        body.entities, body.available_tables, body.datasource_name,
    )
    return {
        "success": True,
        "data": {
            "results": [
                {
                    "entity": r.entity_name,
                    "status": r.status,
                    "best_match": {
                        "table": r.best_match.table_name,
                        "column": r.best_match.column_name,
                        "fqn": r.best_match.fqn,
                        "method": r.best_match.match_method,
                        "confidence": r.best_match.confidence,
                    } if r.best_match else None,
                    "candidate_count": len(r.candidates),
                }
                for r in results
            ],
            "summary": {
                "total": len(results),
                "bound": sum(1 for r in results if r.status == "bound"),
                "partial": sum(1 for r in results if r.status == "partial"),
                "unbound": sum(1 for r in results if r.status == "unbound"),
            },
        },
    }
