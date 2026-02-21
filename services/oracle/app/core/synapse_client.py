import httpx
import structlog
import asyncio
from app.core.config import settings
from typing import Dict, Any, Optional
import json

logger = structlog.get_logger()

class SynapseClient:
    def __init__(self):
        self.base_url = settings.SYNAPSE_API_URL
        self.schema_edit_base = settings.SYNAPSE_SCHEMA_EDIT_BASE
        self.token = settings.SERVICE_TOKEN_ORACLE

    def _get_headers(self, tenant_id: str = "") -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        return headers

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        tenant_id: str = "",
        max_retries: int = 3,
        **kwargs,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._get_headers(tenant_id)
        
        async with httpx.AsyncClient() as client:
            for attempt in range(max_retries):
                try:
                    res = await client.request(method, url, headers=headers, **kwargs)
                    res.raise_for_status()
                    return res.json()
                except httpx.RequestError as exc:
                    logger.error("synapse_api_error", attempt=attempt+1, error=str(exc))
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(1)
                except httpx.HTTPStatusError as exc:
                    logger.error("synapse_api_http_error", attempt=attempt + 1, status=exc.response.status_code)
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(0.5)

    async def search_graph(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        tenant_id: str = "",
    ) -> Dict[str, Any]:
        logger.info("synapse_api_request", action="search_graph")
        fallback = {"tables": {"vector_matched": [], "fk_related": []}, "similar_queries": [], "value_mappings": []}
        payload: Dict[str, Any] = {"query": query}
        if context:
            payload["context"] = context
            case_id = context.get("case_id")
            if case_id:
                payload["case_id"] = case_id
        try:
            response = await self._request_with_retry(
                "POST",
                "/api/v3/synapse/graph/search",
                tenant_id=tenant_id,
                json=payload,
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning("synapse_search_graph_fallback", reason=str(exc))
            return fallback
        data = response.get("data") if isinstance(response, dict) else None
        if isinstance(data, dict):
            return data
        return fallback

    async def reflect_cache(self, question: str, sql: str, confidence: float, datasource_id: str) -> Dict[str, Any]:
        logger.info("synapse_api_request", action="reflect_cache")
        return {"success": True}

    def list_datasources(self) -> list[dict[str, Any]]:
        try:
            payload = json.loads(settings.ORACLE_DATASOURCES_JSON)
            if isinstance(payload, list):
                return [item for item in payload if isinstance(item, dict)]
        except json.JSONDecodeError:
            logger.warning("invalid_datasource_registry_json")
        return [
            {
                "id": "ds_business_main",
                "name": "Business Main DB",
                "type": "postgresql",
                "host": "localhost",
                "database": "insolvency_os",
                "status": "active",
            }
        ]

    async def list_schema_tables(self, tenant_id: str) -> dict[str, Any]:
        return await self._request_with_retry("GET", f"{self.schema_edit_base}/tables", tenant_id=tenant_id)

    async def get_schema_table(self, tenant_id: str, table_name: str) -> dict[str, Any]:
        return await self._request_with_retry("GET", f"{self.schema_edit_base}/tables/{table_name}", tenant_id=tenant_id)

    async def update_table_description(self, tenant_id: str, table_name: str, description: str) -> dict[str, Any]:
        return await self._request_with_retry(
            "PUT",
            f"{self.schema_edit_base}/tables/{table_name}/description",
            tenant_id=tenant_id,
            json={"description": description},
        )

    async def update_column_description(
        self,
        tenant_id: str,
        table_name: str,
        column_name: str,
        description: str,
    ) -> dict[str, Any]:
        return await self._request_with_retry(
            "PUT",
            f"{self.schema_edit_base}/columns/{table_name}/{column_name}/description",
            tenant_id=tenant_id,
            json={"description": description},
        )

synapse_client = SynapseClient()
