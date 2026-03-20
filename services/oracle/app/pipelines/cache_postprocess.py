"""캐시 후처리 파이프라인.

NL2SQL 결과를 품질 게이트로 심사한 뒤,
APPROVE된 쿼리만 Neo4j 캐시에 저장한다.

변경 이력:
- v1: confidence=0.95 고정값 (스텁)
- v2: QualityJudge LLM 기반 N-라운드 심사 (#12 P1-2)

feature flag: ENABLE_QUALITY_GATE
- True: LLM 기반 심사 (기본값)
- False: 항상 APPROVE (개발/테스트용)
"""

from __future__ import annotations

from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.quality_judge import QualityJudge
from app.infrastructure.acl.synapse_acl import oracle_synapse_acl

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# 게이트 판정 모델
# ---------------------------------------------------------------------------


class GateDecision(BaseModel):
    """품질 게이트 판정 결과.

    status:
      - APPROVE: 검증 통과 -> 캐시 저장 (verified=True)
      - PENDING: 부분 통과 -> 캐시 저장 (verified=False, 수동 검토 대기)
      - REJECT: 검증 실패 -> 캐시 미저장
    """

    status: str  # APPROVE | PENDING | REJECT
    confidence: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# 캐시 후처리기
# ---------------------------------------------------------------------------


class CachePostProcessor:
    """품질 게이트 심사 후 캐시 저장을 관리한다."""

    def __init__(self) -> None:
        # LLM 기반 품질 심사기
        self._judge = QualityJudge()

    @staticmethod
    def _format_preview(result_preview: list) -> dict[str, Any]:
        """실행 결과 미리보기를 품질 게이트 입력 형태로 변환한다.

        result_preview: [[val1, val2, ...], ...] 형태의 행 목록
        """
        if not result_preview:
            return {"columns": [], "rows": [], "row_count": 0}

        # 행 데이터만 있으면 컬럼명은 비워둠 (호출자가 별도 전달 가능)
        rows = result_preview if isinstance(result_preview, list) else []
        return {
            "columns": [],
            "rows": rows[:10],  # 최대 10행
            "row_count": len(rows),
        }

    async def quality_gate(
        self,
        question: str,
        sql: str,
        result_preview: list,
        datasource_id: str,
        *,
        execution_time_ms: float | None = None,
        metadata: dict | None = None,
        preview_columns: list[str] | None = None,
    ) -> GateDecision:
        """LLM N-라운드 심사를 수행하여 캐시 저장 여부를 결정한다.

        feature flag ENABLE_QUALITY_GATE=False 시 항상 APPROVE 반환.

        APPROVE (>=0.80): 검증 통과 -> 캐시 저장
        PENDING (>=0.60): 부분 통과 -> 캐시 저장 (verified=False)
        REJECT  (<0.60):  검증 실패 -> 캐시 미저장
        """
        # feature flag: 비활성화 시 항상 APPROVE
        if not settings.ENABLE_QUALITY_GATE:
            logger.info("quality_gate_disabled_bypass")
            return GateDecision(
                status="APPROVE",
                confidence=0.95,
                reasons=["품질 게이트 비활성화"],
            )

        # preview를 심사 입력 형태로 변환
        preview = self._format_preview(result_preview)
        if preview_columns:
            preview["columns"] = preview_columns

        # LLM N-라운드 심사 수행
        judge_result = await self._judge.multi_round_judge(
            question=question,
            sql=sql,
            row_count=preview.get("row_count"),
            execution_time_ms=execution_time_ms,
            preview=preview,
            metadata=metadata,
            max_rounds=2,
        )

        # 판정 임계값 기반 status 결정
        if judge_result.accept and judge_result.confidence >= QualityJudge.THRESHOLD_APPROVE:
            status = "APPROVE"
        elif judge_result.accept and judge_result.confidence >= QualityJudge.THRESHOLD_PENDING:
            status = "PENDING"
        else:
            status = "REJECT"

        decision = GateDecision(
            status=status,
            confidence=judge_result.confidence,
            reasons=judge_result.reasons,
            risk_flags=judge_result.risk_flags,
            summary=judge_result.summary,
        )

        logger.info(
            "quality_gate_decision",
            status=decision.status,
            confidence=decision.confidence,
            reasons=decision.reasons[:3],
            risk_flags=decision.risk_flags[:2],
        )

        return decision

    async def persist_query(
        self,
        question: str,
        sql: str,
        confidence: float,
        datasource_id: str,
        tenant_id: str | None = None,
        *,
        verified: bool = True,
        quality_gate_json: str | None = None,
    ) -> None:
        """검증된 쿼리를 Neo4j 캐시에 저장한다.

        Synapse ACL을 경유하여 캐시를 반영한다.
        verified 플래그로 품질 게이트 통과 여부를 구분한다.
        """
        try:
            await oracle_synapse_acl.reflect_cache(question, sql, confidence, datasource_id)
            logger.info(
                "cache_persisted",
                question=question[:80],
                datasource_id=datasource_id,
                confidence=confidence,
                verified=verified,
                tenant_id=tenant_id or "",
            )
        except Exception as exc:
            logger.warning("cache_persist_failed", error=str(exc))

    async def process(
        self,
        question: str,
        sql: str,
        result_preview: list,
        datasource_id: str,
        tenant_id: str | None = None,
        *,
        execution_time_ms: float | None = None,
        metadata: dict | None = None,
        preview_columns: list[str] | None = None,
    ) -> GateDecision:
        """품질 게이트 심사 + 캐시 저장을 일괄 수행한다.

        APPROVE: 캐시 저장 (verified=True)
        PENDING: 캐시 저장 (verified=False, 수동 검토 대기)
        REJECT:  캐시 미저장 + 로그만 기록
        """
        decision = await self.quality_gate(
            question=question,
            sql=sql,
            result_preview=result_preview,
            datasource_id=datasource_id,
            execution_time_ms=execution_time_ms,
            metadata=metadata,
            preview_columns=preview_columns,
        )

        if decision.status == "APPROVE":
            # 검증 통과 -> 캐시 저장 (verified=True)
            await self.persist_query(
                question=question,
                sql=sql,
                confidence=decision.confidence,
                datasource_id=datasource_id,
                tenant_id=tenant_id,
                verified=True,
                quality_gate_json=decision.model_dump_json(),
            )
        elif decision.status == "PENDING":
            # 부분 통과 -> 캐시 저장하되 verified=False (수동 검토 대기)
            await self.persist_query(
                question=question,
                sql=sql,
                confidence=decision.confidence,
                datasource_id=datasource_id,
                tenant_id=tenant_id,
                verified=False,
                quality_gate_json=decision.model_dump_json(),
            )
        else:
            # REJECT -> 캐시 미저장, 로그만 기록
            logger.info(
                "cache_rejected",
                question=question[:80],
                reasons=decision.reasons[:3],
                risk_flags=decision.risk_flags[:2],
            )

        return decision


# 모듈 레벨 싱글턴
cache_postprocessor = CachePostProcessor()
