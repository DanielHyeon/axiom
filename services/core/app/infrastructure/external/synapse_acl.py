"""Anti-Corruption Layer: Synapse BC → Core internal domain models.

Core가 Synapse에 의존하는 모든 지점에서 이 ACL을 통해 접근한다.
Synapse API 응답 형식이 변경되어도 Core 내부 모델은 안정.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings


# ---------------------------------------------------------------------------
# Core 내부 도메인 모델 (Synapse 응답 형식에 의존하지 않음)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OntologySearchResult:
    """Core 도메인 내부의 온톨로지 검색 결과 모델."""

    entity_id: str
    entity_type: str
    label: str
    relevance_score: float
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessModelInfo:
    """Core가 이해하는 프로세스 모델 형식."""

    model_id: str
    activities: list[str] = field(default_factory=list)
    transitions: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class IngestResult:
    """Synapse 이벤트 로그 인제스트 결과."""

    log_id: str
    status: str
    message: str = ""


class SynapseACLError(Exception):
    """ACL 변환 중 발생하는 에러."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


# ---------------------------------------------------------------------------
# ACL 구현
# ---------------------------------------------------------------------------


class SynapseACL:
    """Anti-Corruption Layer: Synapse BC의 응답을 Core 도메인 모델로 변환한다.

    기존 SynapseGatewayService의 단순 프록시 패턴을 대체하여,
    외부 BC 응답 → 내부 도메인 모델 변환 책임을 집중한다.
    """

    def __init__(self, base_url: str | None = None, service_token: str | None = None):
        self._base_url = (base_url or settings.SYNAPSE_BASE_URL).rstrip("/")
        self._service_token = service_token or settings.SYNAPSE_SERVICE_TOKEN

    def _headers(self, tenant_id: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "X-Tenant-Id": tenant_id or "default",
        }
        if extra:
            headers.update(extra)
        return headers

    # -- Ontology Search ---------------------------------------------------

    async def search_ontology(
        self, query: str, tenant_id: str, timeout: float = 10.0
    ) -> list[OntologySearchResult]:
        """Synapse 그래프 검색 결과를 Core 내부 OntologySearchResult로 변환."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/v3/synapse/graph/search",
                json={"query": query},
                headers=self._headers(tenant_id),
            )
            if resp.status_code >= 400:
                raise SynapseACLError(resp.status_code, resp.text)
            raw = resp.json()

        return self._translate_search_results(raw)

    @staticmethod
    def _translate_search_results(raw: dict[str, Any]) -> list[OntologySearchResult]:
        """Synapse 응답 형식 → Core OntologySearchResult 변환 (ACL 핵심)."""
        data = raw.get("data", raw)
        items = data.get("results", data.get("nodes", []))
        if not isinstance(items, list):
            return []

        results: list[OntologySearchResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("id", ""))
            if not entity_id:
                continue
            results.append(
                OntologySearchResult(
                    entity_id=entity_id,
                    entity_type=str(item.get("type", "unknown")),
                    label=str(item.get("name", item.get("label", ""))),
                    relevance_score=float(item.get("score", 0.0)),
                    properties={
                        k: v
                        for k, v in item.items()
                        if k not in ("id", "type", "name", "label", "score")
                    },
                )
            )
        return results

    # -- Process Model -----------------------------------------------------

    async def get_process_model(
        self, model_id: str, tenant_id: str, timeout: float = 10.0
    ) -> ProcessModelInfo | None:
        """Synapse의 프로세스 모델을 Core 내부 ProcessModelInfo로 변환."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                f"{self._base_url}/api/v1/mining/models/{model_id}",
                headers=self._headers(tenant_id),
            )
            if resp.status_code == 404:
                return None
            if resp.status_code >= 400:
                raise SynapseACLError(resp.status_code, resp.text)
            raw = resp.json()

        return self._translate_process_model(raw)

    @staticmethod
    def _translate_process_model(raw: dict[str, Any]) -> ProcessModelInfo:
        """Synapse mining 모델 형식 → Core ProcessModelInfo 변환."""
        data = raw.get("data", raw)
        transitions = []
        for t in data.get("transitions", data.get("edges", [])):
            if isinstance(t, dict):
                transitions.append(
                    {
                        "from": t.get("source", t.get("from", "")),
                        "to": t.get("target", t.get("to", "")),
                        "frequency": int(t.get("count", t.get("frequency", 0))),
                    }
                )

        return ProcessModelInfo(
            model_id=str(data.get("id", data.get("model_id", ""))),
            activities=data.get("activities", []),
            transitions=transitions,
        )

    # -- Event Log Ingest --------------------------------------------------

    async def ingest_event_log(
        self,
        tenant_id: str,
        raw_body: bytes,
        content_type: str,
        auth_header: str | None = None,
        timeout: float = 300.0,
    ) -> IngestResult:
        """이벤트 로그를 Synapse에 전달하고 결과를 Core IngestResult로 변환."""
        headers = self._headers(tenant_id)
        headers["Content-Type"] = content_type
        if auth_header:
            headers["Authorization"] = auth_header

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/v3/synapse/event-logs/ingest",
                content=raw_body,
                headers=headers,
            )

        try:
            payload = resp.json()
        except Exception:
            payload = {"detail": resp.text}

        if resp.status_code >= 400:
            raise SynapseACLError(resp.status_code, str(payload))

        return self._translate_ingest_result(payload)

    @staticmethod
    def _translate_ingest_result(raw: dict[str, Any]) -> IngestResult:
        """Synapse ingest 응답 → Core IngestResult 변환."""
        data = raw.get("data", raw)
        return IngestResult(
            log_id=str(data.get("log_id", data.get("id", ""))),
            status=str(data.get("status", "accepted")),
            message=str(data.get("message", "")),
        )

    # -- Generic Proxy (BFF 하위 호환) ------------------------------------

    async def proxy_request(
        self,
        method: str,
        path: str,
        tenant_id: str,
        json_body: Any = None,
        raw_body: bytes | None = None,
        content_type: str | None = None,
        auth_header: str | None = None,
        query_params: dict[str, Any] | None = None,
        timeout: float = 180.0,
    ) -> Any:
        """BFF 프록시 레이어: 기존 gateway/routes.py 하위 호환.

        이 메서드는 Canvas UI에서 Synapse로 직접 전달하는 BFF 프록시 용도로만 사용.
        Core 도메인 로직에서는 위의 ACL 메서드(search_ontology, get_process_model 등)를 사용해야 한다.
        """
        from urllib.parse import urlencode

        url = f"{self._base_url}{path}"
        if query_params:
            filtered = {k: v for k, v in query_params.items() if v is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered, doseq=True)}"

        headers = self._headers(tenant_id)
        if content_type:
            headers["Content-Type"] = content_type
        if auth_header:
            headers["Authorization"] = auth_header

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
            raise SynapseACLError(response.status_code, payload)
        return payload

    # -- Backward Compatibility (기존 SynapseGatewayService.request 시그니처) --

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
        """기존 SynapseGatewayService.request() 시그니처 호환 래퍼.

        gateway/routes.py에서 대량 사용하므로 하위 호환 유지.
        신규 코드에서는 proxy_request() 또는 ACL 메서드를 직접 사용해야 한다.
        """
        hdrs = incoming_headers or {}
        return await self.proxy_request(
            method=method,
            path=path,
            tenant_id=hdrs.get("X-Tenant-Id", "default"),
            json_body=json_body,
            raw_body=raw_body,
            content_type=content_type,
            auth_header=hdrs.get("Authorization"),
            query_params=query_params,
            timeout=timeout,
        )


# Singleton
synapse_acl = SynapseACL()
