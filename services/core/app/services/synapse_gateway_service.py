from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings


class GatewayProxyError(Exception):
    def __init__(self, status_code: int, body: Any):
        super().__init__(str(body))
        self.status_code = status_code
        self.body = body


class SynapseGatewayService:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.SYNAPSE_BASE_URL).rstrip("/")

    def _build_url(self, path: str, query_params: dict[str, Any] | None = None) -> str:
        url = f"{self.base_url}{path}"
        if query_params:
            filtered = {k: v for k, v in query_params.items() if v is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered, doseq=True)}"
        return url

    def _headers(self, incoming_headers: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {settings.SYNAPSE_SERVICE_TOKEN}",
            "X-Tenant-Id": (incoming_headers or {}).get("X-Tenant-Id", "default"),
            "X-Request-Id": (incoming_headers or {}).get("X-Request-Id", ""),
        }
        auth = (incoming_headers or {}).get("Authorization")
        if auth:
            headers["Authorization"] = auth
        return headers

    async def request(
        self,
        method: str,
        path: str,
        incoming_headers: dict[str, str] | None = None,
        query_params: dict[str, Any] | None = None,
        json_body: Any = None,
        raw_body: bytes | None = None,
        content_type: str | None = None,
        timeout: float = 180.0,
    ) -> Any:
        url = self._build_url(path, query_params)
        headers = self._headers(incoming_headers)
        if content_type:
            headers["Content-Type"] = content_type

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body if raw_body is None else None,
                content=raw_body,
            )

        try:
            payload = response.json()
        except Exception:
            payload = {"detail": response.text}

        if response.status_code >= 400:
            raise GatewayProxyError(response.status_code, payload)
        return payload


synapse_gateway_service = SynapseGatewayService()
