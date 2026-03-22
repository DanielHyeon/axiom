"""Text2SQL 유효성 부트스트랩 API 엔드포인트 (#P4-16).

빈 테이블/null-only 컬럼을 감지하여 NL2SQL RAG 검색에서 제외하는
유효성 플래그를 수동으로 트리거하거나, 최근 실행 결과를 조회한다.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import structlog

from app.core.config import settings
from app.pipelines.validity_bootstrap import validity_bootstrap, get_last_report

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v2/oracle/validity", tags=["validity"])


# ──────────────────────────────────────────────────────────────
# Pydantic 요청/응답 모델
# ──────────────────────────────────────────────────────────────


class BootstrapRequest(BaseModel):
    """유효성 부트스트랩 트리거 요청."""

    # 스캔 대상 PostgreSQL 스키마 (비우면 설정값 사용)
    target_schema: str = Field(
        default="",
        description="스캔 대상 PostgreSQL 스키마. 비우면 VALIDITY_BOOTSTRAP_TARGET_SCHEMA 사용",
    )
    # 데이터소스 식별자 (Synapse 업데이트 시 전달)
    datasource_id: str = Field(
        default="",
        description="데이터소스 ID (Synapse 플래그 업데이트 시 사용)",
    )


class ValidityReportResponse(BaseModel):
    """유효성 검사 결과 응답."""

    invalid_tables: list[str] = Field(default_factory=list, description="빈 테이블 FQN 목록")
    invalid_columns: list[str] = Field(default_factory=list, description="null-only 컬럼 FQN 목록")
    scanned_tables: int = Field(default=0, description="스캔한 전체 테이블 수")
    scanned_columns: int = Field(default=0, description="스캔한 전체 컬럼 수")
    synapse_updated: int = Field(default=0, description="Synapse 플래그 업데이트 성공 횟수")
    synapse_errors: int = Field(default=0, description="Synapse 플래그 업데이트 실패 횟수")
    elapsed_ms: float = Field(default=0.0, description="실행 소요 시간 (밀리초)")


class BootstrapResponse(BaseModel):
    """부트스트랩 트리거 API 응답 래퍼."""

    success: bool
    data: ValidityReportResponse


class ReportResponse(BaseModel):
    """최근 보고서 조회 API 응답 래퍼."""

    success: bool
    data: ValidityReportResponse | None


# ──────────────────────────────────────────────────────────────
# 엔드포인트
# ──────────────────────────────────────────────────────────────


@router.post("/bootstrap", response_model=BootstrapResponse)
async def trigger_validity_bootstrap(body: BootstrapRequest | None = None):
    """유효성 부트스트랩을 수동으로 트리거한다.

    빈 테이블과 null-only 컬럼을 감지하여
    Synapse 메타데이터에 text_to_sql_is_valid = false 플래그를 설정한다.
    """
    if not settings.VALIDITY_BOOTSTRAP_ENABLED:
        raise HTTPException(
            status_code=409,
            detail="유효성 부트스트랩이 비활성화되어 있습니다 (VALIDITY_BOOTSTRAP_ENABLED=false)",
        )

    req = body or BootstrapRequest()

    logger.info(
        "validity_bootstrap_manual_trigger",
        target_schema=req.target_schema or settings.VALIDITY_BOOTSTRAP_TARGET_SCHEMA,
        datasource_id=req.datasource_id,
    )

    report = await validity_bootstrap.run(
        target_schema=req.target_schema or None,
        datasource_id=req.datasource_id,
    )

    return BootstrapResponse(
        success=True,
        data=ValidityReportResponse(
            invalid_tables=report.invalid_tables,
            invalid_columns=report.invalid_columns,
            scanned_tables=report.scanned_tables,
            scanned_columns=report.scanned_columns,
            synapse_updated=report.synapse_updated,
            synapse_errors=report.synapse_errors,
            elapsed_ms=report.elapsed_ms,
        ),
    )


@router.get("/report", response_model=ReportResponse)
async def get_validity_report():
    """마지막 유효성 부트스트랩 실행 결과를 조회한다.

    한 번도 실행한 적이 없으면 data=null을 반환한다.
    """
    report = get_last_report()

    if report is None:
        return ReportResponse(success=True, data=None)

    return ReportResponse(
        success=True,
        data=ValidityReportResponse(
            invalid_tables=report.invalid_tables,
            invalid_columns=report.invalid_columns,
            scanned_tables=report.scanned_tables,
            scanned_columns=report.scanned_columns,
            synapse_updated=report.synapse_updated,
            synapse_errors=report.synapse_errors,
            elapsed_ms=report.elapsed_ms,
        ),
    )
