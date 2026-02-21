from pydantic import BaseModel
import structlog
from app.core.synapse_client import synapse_client

logger = structlog.get_logger()

class GateDecision(BaseModel):
    status: str
    confidence: float

class CachePostProcessor:
    async def quality_gate(self, question: str, sql: str, result_preview: list) -> GateDecision:
        confidence = 0.95
        if confidence >= 0.90:
            return GateDecision(status="APPROVE", confidence=confidence)
        elif confidence >= 0.80:
            return GateDecision(status="PENDING", confidence=confidence)
        else:
            return GateDecision(status="REJECT", confidence=confidence)

    async def persist_query(self, question: str, sql: str, confidence: float, datasource_id: str):
        await synapse_client.reflect_cache(question, sql, confidence, datasource_id)
        logger.info("cache_persisted", question=question, sql=sql)

    async def process(self, question: str, sql: str, result_preview: list, datasource_id: str):
        decision = await self.quality_gate(question, sql, result_preview)
        if decision.status == "APPROVE":
            await self.persist_query(question, sql, decision.confidence, datasource_id)

cache_postprocessor = CachePostProcessor()
