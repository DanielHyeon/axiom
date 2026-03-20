"""SynapseOntologyClient — Synapse 온톨로지 API를 호출하는 HTTP 클라이언트.

Weaver Insight 기능이 Synapse 온톨로지 레이어(KPI, Measure, Process, Resource)에서
노드와 관계 정보를 가져올 때 사용한다.

주요 기능:
  - KPI 레이어 노드 목록 조회
  - 특정 노드의 이웃(CAUSES/INFLUENCES 관계) 조회
  - 노드 상세 + 관계 정보 조회
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger("weaver.synapse_ontology_client")

# Synapse 온톨로지 API 기본 경로
_ONTOLOGY_PREFIX = "/api/v3/synapse/ontology"
_TIMEOUT = 15.0


class SynapseOntologyClientError(RuntimeError):
    """Synapse 온톨로지 API 호출 실패 시 발생하는 예외."""
    pass


class SynapseOntologyClient:
    """Synapse 온톨로지 API를 호출하는 비동기 HTTP 클라이언트.

    모든 메서드는 Synapse 서비스가 다운되어도 빈 결과를 반환하며,
    호출부에서 fallback 처리가 가능하도록 설계되었다.
    """

    def __init__(self) -> None:
        self._base_url = settings.synapse_base_url.rstrip("/")

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        tenant_id: str = "",
    ) -> dict[str, Any]:
        """Synapse API GET 요청 공통 헬퍼.

        응답이 정상이면 JSON body를 반환, 실패 시 SynapseOntologyClientError 발생.
        """
        url = f"{self._base_url}{_ONTOLOGY_PREFIX}{path}"
        headers: dict[str, str] = {}
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Synapse 온톨로지 API 오류: %s %s → %d",
                "GET", url, exc.response.status_code,
            )
            raise SynapseOntologyClientError(
                f"Synapse returned {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Synapse 온톨로지 API 연결 실패: %s", exc)
            raise SynapseOntologyClientError(str(exc)) from exc

    # ── KPI 레이어 노드 목록 ───────────────────────────────────

    async def fetch_kpi_nodes(
        self,
        case_id: str,
        tenant_id: str = "",
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Synapse에서 KPI 레이어 노드 목록을 가져온다.

        GET /api/v3/synapse/ontology/cases/{case_id}/ontology?layer=kpi
        응답에서 nodes 배열만 추출하여 반환한다.
        """
        try:
            data = await self._get(
                f"/cases/{case_id}/ontology",
                params={"layer": "kpi", "limit": limit},
                tenant_id=tenant_id,
            )
            # Synapse 응답 구조: { success: true, data: { nodes: [...], relations: [...] } }
            inner = data.get("data", data)
            return inner.get("nodes", [])
        except SynapseOntologyClientError:
            # Synapse 연결 실패 시 빈 목록 반환 (graceful degradation)
            logger.info("Synapse KPI 노드 조회 실패 — 빈 목록 반환")
            return []

    # ── 특정 노드의 이웃(Driver) 조회 ──────────────────────────

    async def fetch_node_neighbors(
        self,
        node_id: str,
        tenant_id: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """특정 노드의 이웃 노드 + 관계 정보를 가져온다.

        GET /api/v3/synapse/ontology/nodes/{node_id}/neighbors
        CAUSES, INFLUENCES 등 관계로 연결된 이웃을 반환한다.
        """
        try:
            data = await self._get(
                f"/nodes/{node_id}/neighbors",
                params={"limit": limit},
                tenant_id=tenant_id,
            )
            inner = data.get("data", data)
            # neighbors는 { nodes: [...], relations: [...] } 형태일 수 있음
            if isinstance(inner, dict):
                return inner.get("nodes", inner.get("neighbors", []))
            if isinstance(inner, list):
                return inner
            return []
        except SynapseOntologyClientError:
            logger.info("Synapse 이웃 노드 조회 실패 (node=%s) — 빈 목록 반환", node_id)
            return []

    async def fetch_node_neighbors_full(
        self,
        node_id: str,
        tenant_id: str = "",
        limit: int = 100,
    ) -> dict[str, Any]:
        """특정 노드의 이웃 + 관계 전체 데이터를 가져온다.

        nodes와 relations 모두 포함한 dict 반환.
        """
        try:
            data = await self._get(
                f"/nodes/{node_id}/neighbors",
                params={"limit": limit},
                tenant_id=tenant_id,
            )
            inner = data.get("data", data)
            if isinstance(inner, dict):
                return {
                    "nodes": inner.get("nodes", inner.get("neighbors", [])),
                    "relations": inner.get("relations", inner.get("edges", [])),
                }
            return {"nodes": inner if isinstance(inner, list) else [], "relations": []}
        except SynapseOntologyClientError:
            logger.info("Synapse 이웃 전체 조회 실패 (node=%s)", node_id)
            return {"nodes": [], "relations": []}

    # ── 노드 상세 정보 조회 ────────────────────────────────────

    async def fetch_node_detail(
        self,
        node_id: str,
        tenant_id: str = "",
    ) -> dict[str, Any] | None:
        """특정 온톨로지 노드의 상세 정보를 가져온다.

        GET /api/v3/synapse/ontology/nodes/{node_id}
        """
        try:
            data = await self._get(
                f"/nodes/{node_id}",
                tenant_id=tenant_id,
            )
            return data.get("data", data)
        except SynapseOntologyClientError:
            logger.info("Synapse 노드 상세 조회 실패 (node=%s)", node_id)
            return None

    # ── 케이스의 온톨로지 요약 정보 ─────────────────────────────

    async def fetch_case_summary(
        self,
        case_id: str,
        tenant_id: str = "",
    ) -> dict[str, Any]:
        """케이스의 온톨로지 요약(레이어별 노드 수 등)을 가져온다."""
        try:
            data = await self._get(
                f"/cases/{case_id}/ontology/summary",
                tenant_id=tenant_id,
            )
            return data.get("data", data)
        except SynapseOntologyClientError:
            logger.info("Synapse 케이스 요약 조회 실패 (case=%s)", case_id)
            return {}

    async def fetch_all_ontology_nodes(
        self,
        case_id: str,
        tenant_id: str = "",
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """케이스의 전체 온톨로지 노드를 가져온다 (스키마 커버리지 등에 사용)."""
        try:
            data = await self._get(
                f"/cases/{case_id}/ontology",
                params={"layer": "all", "limit": limit},
                tenant_id=tenant_id,
            )
            inner = data.get("data", data)
            return inner.get("nodes", []) if isinstance(inner, dict) else []
        except SynapseOntologyClientError:
            logger.info("Synapse 전체 노드 조회 실패 (case=%s)", case_id)
            return []


# 싱글톤 인스턴스 — Weaver 서비스 전체에서 공유
synapse_ontology_client = SynapseOntologyClient()
