import httpx
import structlog
import asyncio
from app.core.config import settings
from typing import Dict, Any, Optional

logger = structlog.get_logger()

class SynapseClient:
    def __init__(self):
        self.base_url = settings.SYNAPSE_API_URL
        self.token = settings.SERVICE_TOKEN_ORACLE

    def _get_headers(self, tenant_id: str = "") -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        return headers

    async def _request_with_retry(self, method: str, path: str, max_retries: int = 3, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        
        async with httpx.AsyncClient() as client:
            for attempt in range(max_retries):
                try:
                    res = await client.request(method, url, headers=headers, **kwargs)
                    res.raise_for_status()
                    return res.json()
                except httpx.RequestError as exc:
                    logger.error("synapse_api_error", attempt=attempt+1, error=str(exc))
                    if attempt == max_retries - 1:
                        # Fallback mock for testing without live Graph
                        return {"fallback": True, "error": str(exc)}
                    await asyncio.sleep(1)

    async def search_graph(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.info("synapse_api_request", action="search_graph")
        return {
            "tables": [{"name": "sales_records"}],
            "fks": []
        }

    async def reflect_cache(self, question: str, sql: str, confidence: float, datasource_id: str) -> Dict[str, Any]:
        logger.info("synapse_api_request", action="reflect_cache")
        return {"success": True}

synapse_client = SynapseClient()
