from pydantic import BaseModel
import structlog

from app.core.synapse_client import synapse_client

logger = structlog.get_logger()


class GateDecision(BaseModel):
    status: str
    confidence: float


class CachePostProcessor:
    async def quality_gate(self, question: str, sql: str, result_preview: list, datasource_id: str) -> GateDecision:
        """
        품질 게이트: 신뢰도 점수를 기준으로 캐싱 여부 결정.
        현재는 휴리스틱 상수값(0.95)을 사용하며, 향후 LLM 기반 심사로 교체 가능.
        """
        confidence = 0.95
        if confidence >= 0.90:
            return GateDecision(status="APPROVE", confidence=confidence)
        if confidence >= 0.80:
            return GateDecision(status="PENDING", confidence=confidence)
        return GateDecision(status="REJECT", confidence=confidence)

    async def persist_query(
        self,
        question: str,
        sql: str,
        confidence: float,
        datasource_id: str,
        tenant_id: str | None = None,
    ):
        try:
            await synapse_client.reflect_cache(question, sql, confidence, datasource_id)
            logger.info(
                "cache_persisted",
                question=question,
                datasource_id=datasource_id,
                confidence=confidence,
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
    ):
        decision = await self.quality_gate(question, sql, result_preview, datasource_id)
        if decision.status == "APPROVE":
            await self.persist_query(question, sql, decision.confidence, datasource_id, tenant_id)


cache_postprocessor = CachePostProcessor()
