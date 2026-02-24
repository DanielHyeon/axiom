"""SynapseMetadataClient — Synapse 메타데이터 그래프 API 클라이언트 (DDD-P2-05).

Weaver가 Neo4j에 직접 접근하지 않고 Synapse API를 통해 메타데이터 그래프에 접근한다.
Neo4jMetadataStore와 동일한 인터페이스를 제공하여 호출부 변경을 최소화한다.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import httpx

SYNAPSE_BASE_URL = os.getenv("SYNAPSE_BASE_URL", "http://synapse-svc:8003")
_API_PREFIX = "/api/v1/metadata/graph"
_TIMEOUT = 30.0


class SynapseMetadataClientError(RuntimeError):
    pass


class SynapseMetadataClient:
    """Synapse 메타데이터 그래프 API를 호출하는 HTTP 클라이언트."""

    def __init__(self) -> None:
        self._base = SYNAPSE_BASE_URL.rstrip("/") + _API_PREFIX

    @asynccontextmanager
    async def _session(self, tenant_id: str = "") -> AsyncIterator[httpx.AsyncClient]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base,
                headers={"X-Tenant-ID": tenant_id},
                timeout=_TIMEOUT,
            ) as c:
                yield c
        except httpx.HTTPError as exc:
            raise SynapseMetadataClientError(str(exc)) from exc

    async def health_check(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{SYNAPSE_BASE_URL.rstrip('/')}/health")
                r.raise_for_status()
        except httpx.HTTPError as exc:
            raise SynapseMetadataClientError(str(exc)) from exc

    # ──── Snapshot ──── #

    async def save_snapshot(self, item: dict[str, Any], tenant_id: str | None = None) -> None:
        async with self._session(tenant_id or "") as c:
            r = await c.post("/snapshots", json=item)
            r.raise_for_status()

    async def list_snapshots(self, case_id: str, datasource: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        async with self._session(tenant_id or "") as c:
            r = await c.get("/snapshots", params={"case_id": case_id, "datasource": datasource})
            r.raise_for_status()
            return r.json().get("data", [])

    async def get_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        async with self._session(tenant_id or "") as c:
            r = await c.get(f"/snapshots/{snapshot_id}", params={"case_id": case_id, "datasource": datasource})
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json().get("data")

    async def delete_snapshot(self, case_id: str, datasource: str, snapshot_id: str, tenant_id: str | None = None) -> bool:
        async with self._session(tenant_id or "") as c:
            r = await c.delete(f"/snapshots/{snapshot_id}", params={"case_id": case_id, "datasource": datasource})
            r.raise_for_status()
            return r.json().get("deleted", False)

    # ──── Glossary ──── #

    async def save_glossary_term(self, item: dict[str, Any], tenant_id: str | None = None) -> None:
        async with self._session(tenant_id or "") as c:
            r = await c.post("/glossary", json=item)
            r.raise_for_status()

    async def list_glossary_terms(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        async with self._session(tenant_id or "") as c:
            r = await c.get("/glossary")
            r.raise_for_status()
            return r.json().get("data", [])

    async def get_glossary_term(self, term_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        async with self._session(tenant_id or "") as c:
            r = await c.get(f"/glossary/{term_id}")
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json().get("data")

    async def delete_glossary_term(self, term_id: str, tenant_id: str | None = None) -> bool:
        async with self._session(tenant_id or "") as c:
            r = await c.delete(f"/glossary/{term_id}")
            r.raise_for_status()
            return r.json().get("deleted", False)

    async def search_glossary_terms(self, q: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        async with self._session(tenant_id or "") as c:
            r = await c.get("/glossary", params={"q": q})
            r.raise_for_status()
            return r.json().get("data", [])

    # ──── Entity Tags ──── #

    async def add_entity_tag(self, entity_key: str, entity_type: str, metadata: dict[str, Any], tag: str) -> list[str]:
        tid = metadata.get("tenant_id", "")
        async with self._session(tid) as c:
            r = await c.post("/tags", json={
                "entity_key": entity_key, "entity_type": entity_type,
                "metadata": metadata, "tag": tag,
            })
            r.raise_for_status()
            return r.json().get("tags", [])

    async def list_entity_tags(self, entity_key: str) -> list[str]:
        async with self._session() as c:
            r = await c.get("/tags", params={"entity_key": entity_key})
            r.raise_for_status()
            return r.json().get("tags", [])

    async def remove_entity_tag(self, entity_key: str, tag: str) -> bool:
        async with self._session() as c:
            r = await c.delete("/tags", params={"entity_key": entity_key, "tag": tag})
            r.raise_for_status()
            return r.json().get("removed", False)

    async def entities_by_tag(self, tag: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
        async with self._session(tenant_id or "") as c:
            r = await c.get("/tags/entities", params={"tag": tag})
            r.raise_for_status()
            return r.json().get("data", [])

    # ──── Datasource ──── #

    async def upsert_datasource(self, name: str, engine: str, tenant_id: str | None = None) -> None:
        async with self._session(tenant_id or "") as c:
            r = await c.post("/datasources/upsert", json={"name": name, "engine": engine})
            r.raise_for_status()

    async def delete_datasource(self, name: str, tenant_id: str | None = None) -> None:
        async with self._session(tenant_id or "") as c:
            r = await c.delete(f"/datasources/{name}")
            r.raise_for_status()

    async def save_extracted_catalog(
        self, tenant_id: str, datasource_name: str,
        catalog: dict[str, dict[str, list[dict[str, Any]]]],
        engine: str = "postgresql", *, foreign_keys: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        async with self._session(tenant_id) as c:
            r = await c.post("/datasources/catalog", json={
                "datasource_name": datasource_name, "catalog": catalog,
                "engine": engine, "foreign_keys": foreign_keys,
            })
            r.raise_for_status()
            return r.json().get("data", {})

    # ──── Stats ──── #

    async def stats(self, tenant_id: str | None = None) -> dict[str, int]:
        async with self._session(tenant_id or "") as c:
            r = await c.get("/stats")
            r.raise_for_status()
            return r.json().get("data", {"datasources": 0, "glossary_terms": 0, "snapshots": 0})


synapse_metadata_client = SynapseMetadataClient()
