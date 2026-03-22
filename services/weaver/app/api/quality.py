"""
품질 수집 API — 시멘틱 계약 대상의 데이터 품질 측정 + 조회

엔드포인트:
  POST /api/quality/scan                          — 테이블 품질 스캔 실행
  GET  /api/quality/scores                        — 최신 품질 점수 목록
  GET  /api/quality/scores/{type}/{id}            — 특정 대상 최신 점수
  GET  /api/quality/dashboard                     — §3.4 전체 품질 요약 대시보드
  GET  /api/quality/history/{type}/{id}           — §3.4 대상별 품질 이력 시계열
  GET  /api/quality/breaches                      — §3.4 최근 임계값 위반 목록
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field

from app.services.insight_store import insight_store
from app.services.quality_collector import QualityCollector
from app.services.request_guard import rate_limiter

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
    # 스캔은 DB 비용이 높으므로 10/min 제한
    rate_limiter.check(f"{_tenant(request)}:{request.url.path}:scan", limit=10)
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
    # 일반 조회 60/min 제한
    rate_limiter.check(f"{_tenant(request)}:{request.url.path}:read", limit=60)
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
    # 개별 점수 조회 60/min 제한
    rate_limiter.check(f"{_tenant(request)}:/api/quality/scores:read", limit=60)
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


# ── §3.4 대시보드 API ──


# 품질 등급 임계값 (Green ≥ 80, Yellow ≥ 60, Red < 60)
_TIER_GREEN = 80
_TIER_YELLOW = 60


@router.get("/dashboard")
async def quality_dashboard(request: Request):
    """§3.4 전체 품질 요약 — 평균 점수, 등급별 건수, 하위 10% 대상 목록

    응답 예시:
    {
      "average_score": 78.5,
      "total_targets": 42,
      "tier_counts": {"green": 30, "yellow": 8, "red": 4},
      "worst_targets": [...]
    }
    """
    # 집계 쿼리이므로 30/min 제한
    rate_limiter.check(f"{_tenant(request)}:{request.url.path}:read", limit=30)
    tenant_id = _tenant(request)
    try:
        pool = await insight_store.get_pool()
        async with pool.acquire() as conn:
            # 대상별 최신 점수를 서브쿼리로 추출
            rows = await conn.fetch("""
                SELECT DISTINCT ON (target_type, target_id)
                    target_type, target_id, overall_score,
                    formula_version, sampled_at, created_at
                FROM weaver.quality_scores
                WHERE tenant_id = $1
                ORDER BY target_type, target_id, created_at DESC
            """, tenant_id)

        if not rows:
            # 데이터 없으면 빈 요약 반환
            return {
                "success": True,
                "data": {
                    "average_score": 0,
                    "total_targets": 0,
                    "tier_counts": {"green": 0, "yellow": 0, "red": 0},
                    "worst_targets": [],
                },
            }

        # 평균 점수 계산
        scores = [float(r["overall_score"]) for r in rows]
        avg_score = round(sum(scores) / len(scores), 2)

        # 등급별 건수 분류
        green = sum(1 for s in scores if s >= _TIER_GREEN)
        yellow = sum(1 for s in scores if _TIER_YELLOW <= s < _TIER_GREEN)
        red = sum(1 for s in scores if s < _TIER_YELLOW)

        # 하위 10% 대상 (최소 1건, 최대 20건)
        worst_count = max(1, min(20, len(rows) // 10))
        sorted_rows = sorted(rows, key=lambda r: float(r["overall_score"]))
        worst_targets = [
            {
                "target_type": r["target_type"],
                "target_id": r["target_id"],
                "overall_score": float(r["overall_score"]),
                "sampled_at": r["sampled_at"].isoformat() if r["sampled_at"] else None,
            }
            for r in sorted_rows[:worst_count]
        ]

        return {
            "success": True,
            "data": {
                "average_score": avg_score,
                "total_targets": len(rows),
                "tier_counts": {"green": green, "yellow": yellow, "red": red},
                "worst_targets": worst_targets,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/history/{target_type}/{target_id:path}")
async def quality_history(
    request: Request,
    target_type: str,
    target_id: str,
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    limit: int = Query(100, ge=1, le=500),
):
    """§3.4 대상별 품질 이력 시계열 — 최근 N일간 점수 변화 추적

    응답: [{overall_score, formula_version, sampled_at}, ...]
    """
    # 일반 조회 60/min 제한
    rate_limiter.check(f"{_tenant(request)}:{request.url.path}:read", limit=60)
    tenant_id = _tenant(request)
    try:
        pool = await insight_store.get_pool()
        from datetime import datetime, timezone, timedelta
        since = datetime.now(timezone.utc) - timedelta(days=days)

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT overall_score, formula_version, sampled_at, created_at
                FROM weaver.quality_scores
                WHERE tenant_id = $1
                  AND target_type = $2
                  AND target_id = $3
                  AND created_at >= $4
                ORDER BY created_at DESC
                LIMIT $5
            """, tenant_id, target_type, target_id, since, limit)

        data = [
            {
                "overall_score": float(r["overall_score"]),
                "formula_version": r["formula_version"],
                "sampled_at": r["sampled_at"].isoformat() if r["sampled_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"success": True, "data": data, "count": len(data)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/breaches")
async def quality_breaches(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
):
    """§3.4 최근 품질 임계값 위반 목록 — overall_score < 60 인 기록

    가장 최근 위반부터 내림차순 정렬.
    """
    # 필터 쿼리이므로 30/min 제한
    rate_limiter.check(f"{_tenant(request)}:{request.url.path}:read", limit=30)
    tenant_id = _tenant(request)
    try:
        pool = await insight_store.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    target_type, target_id, overall_score,
                    freshness_score, completeness_score, uniqueness_score,
                    validity_score, ri_score,
                    formula_version, sampled_at, created_at
                FROM weaver.quality_scores
                WHERE tenant_id = $1
                  AND overall_score < 60
                ORDER BY created_at DESC
                LIMIT $2
            """, tenant_id, limit)

        data = [
            {
                "target_type": r["target_type"],
                "target_id": r["target_id"],
                "overall_score": float(r["overall_score"]),
                "freshness_score": float(r["freshness_score"]) if r["freshness_score"] is not None else None,
                "completeness_score": float(r["completeness_score"]) if r["completeness_score"] is not None else None,
                "uniqueness_score": float(r["uniqueness_score"]) if r["uniqueness_score"] is not None else None,
                "validity_score": float(r["validity_score"]) if r["validity_score"] is not None else None,
                "ri_score": float(r["ri_score"]) if r["ri_score"] is not None else None,
                "formula_version": r["formula_version"],
                "sampled_at": r["sampled_at"].isoformat() if r["sampled_at"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"success": True, "data": data, "count": len(data)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
