"""
품질 수집 API — 시멘틱 계약 대상의 데이터 품질 측정 + 조회

엔드포인트:
  POST /api/quality/scan          — 테이블 품질 스캔 실행
  GET  /api/quality/scores        — 최신 품질 점수 목록
  GET  /api/quality/scores/{id}   — 특정 대상 최신 점수
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field

from app.services.insight_store import insight_store
from app.services.quality_collector import QualityCollector

router = APIRouter(prefix="/api/quality", tags=["Quality"])

_collector = QualityCollector(insight_store)


def _tenant(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if not tid:
        raise HTTPException(status_code=401, detail="tenant_id not resolved")
    return tid


class ScanRequest(BaseModel):
    """품질 스캔 요청"""
    datasource_id: str
    table_name: str
    freshness_sla_minutes: int | None = Field(None, description="SLA (분) — 없으면 24시간 기본")
    owner_team: str | None = None


@router.post("/scan")
async def scan_table_quality(request: Request, body: ScanRequest):
    """테이블 품질 스캔 — freshness, completeness, uniqueness 측정 후 저장"""
    try:
        result = await _collector.collect_table_quality(
            tenant_id=_tenant(request),
            datasource_id=body.datasource_id,
            table_name=body.table_name,
            freshness_sla_minutes=body.freshness_sla_minutes,
            owner_team=body.owner_team,
        )
        return {"success": True, "data": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"품질 스캔 실패: {str(exc)}") from exc


@router.get("/scores")
async def list_quality_scores(
    request: Request,
    target_type: str | None = None,
    target_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    """최신 품질 점수 목록 — 대상별 최신 1건씩"""
    try:
        data = await _collector.get_latest_scores(
            tenant_id=_tenant(request),
            target_type=target_type,
            target_id=target_id,
            limit=limit,
        )
        return {"success": True, "data": data, "count": len(data)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/scores/{target_type}/{target_id:path}")
async def get_quality_score(request: Request, target_type: str, target_id: str):
    """특정 대상의 최신 품질 점수"""
    try:
        data = await _collector.get_score_for_target(
            tenant_id=_tenant(request),
            target_type=target_type,
            target_id=target_id,
        )
        if not data:
            raise HTTPException(status_code=404, detail=f"'{target_type}:{target_id}'의 품질 점수가 없습니다")
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
