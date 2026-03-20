"""
모델 그래프 로더 (Synapse API → model_graph 구성)
=====================================================

Vision 서비스에서 What-if DAG 시뮬레이션을 실행하려면,
Synapse의 온톨로지에서 BehaviorModel + READS_FIELD + PREDICTS_FIELD 구조를 가져와야 한다.

이 모듈은:
1. Synapse API (/api/v3/synapse/ontology/cases/{case_id}/model-graph) 호출
2. 응답을 model_graph 형식으로 변환
3. Redis 캐시 (TTL 5분) 로 성능 최적화

Synapse 장애 시에도 캐시된 데이터가 있으면 사용 가능.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Redis 캐시 TTL (초)
MODEL_GRAPH_CACHE_TTL = int(os.getenv("MODEL_GRAPH_CACHE_TTL", "300"))  # 5분


class ModelGraphFetcher:
    """
    Synapse API에서 모델 그래프를 가져오는 클라이언트.

    model_graph 구조:
    {
        "models": [{"id", "name", "status", "modelType", ...}],
        "reads": [{"modelId", "sourceNodeId", "field", "lag", "featureName"}],
        "predicts": [{"modelId", "targetNodeId", "field", "confidence"}]
    }
    """

    def __init__(
        self,
        synapse_base_url: str | None = None,
        redis_client: Any | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.synapse_base_url = (
            synapse_base_url
            or os.getenv("SYNAPSE_BASE_URL", "http://synapse-svc:8003")
        ).rstrip("/")
        self._redis = redis_client
        self._timeout = timeout
        # lazy 초기화되는 공유 HTTP 클라이언트
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """공유 httpx.AsyncClient를 lazy 생성하여 반환한다.

        매 요청마다 새 클라이언트를 생성하지 않고 재사용하여
        TCP 커넥션 오버헤드를 줄인다.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        """공유 HTTP 클라이언트를 명시적으로 닫는다 (셧다운 시 호출)."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_model_graph(
        self,
        case_id: str,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """
        case_id에 해당하는 모델 그래프를 가져온다.

        1. Redis 캐시 확인 (use_cache=True일 때)
        2. 캐시 미스 → Synapse API 호출
        3. 결과를 Redis에 저장 (TTL 5분)

        Args:
            case_id: 온톨로지 케이스 ID
            use_cache: 캐시 사용 여부

        Returns:
            model_graph dict

        Raises:
            ModelGraphFetchError: Synapse 통신 실패 시
        """
        cache_key = f"whatif:model_graph:{case_id}"

        # 1. 캐시 확인
        if use_cache and self._redis:
            try:
                cached = await self._redis.get(cache_key)
                if cached:
                    logger.debug("모델 그래프 캐시 히트: case_id=%s", case_id)
                    return json.loads(cached)
            except Exception as e:
                logger.warning("Redis 캐시 조회 실패: %s", e)

        # 2. Synapse API 호출 — 공유 클라이언트 재사용
        url = f"{self.synapse_base_url}/api/v3/synapse/ontology/cases/{case_id}/model-graph"
        try:
            client = self._get_client()
            resp = await client.get(url)

            if resp.status_code == 404:
                # 모델 그래프 없음 → 빈 구조 반환
                logger.info("모델 그래프 없음: case_id=%s (404)", case_id)
                return {"models": [], "reads": [], "predicts": []}

            if resp.status_code != 200:
                raise ModelGraphFetchError(
                    f"Synapse API 오류: status={resp.status_code}, body={resp.text[:200]}"
                )

            data = resp.json()
            # Synapse 응답이 {"success": True, "data": {...}} 형태일 수 있음
            model_graph = data.get("data", data) if isinstance(data, dict) else data

        except httpx.ConnectError as e:
            raise ModelGraphFetchError(f"Synapse 연결 실패: {e}") from e
        except httpx.TimeoutException as e:
            raise ModelGraphFetchError(f"Synapse 타임아웃: {e}") from e

        # 3. 캐시 저장
        if self._redis:
            try:
                await self._redis.set(
                    cache_key,
                    json.dumps(model_graph),
                    ex=MODEL_GRAPH_CACHE_TTL,
                )
                logger.debug("모델 그래프 캐시 저장: case_id=%s, TTL=%ds", case_id, MODEL_GRAPH_CACHE_TTL)
            except Exception as e:
                logger.warning("Redis 캐시 저장 실패: %s", e)

        return model_graph

    async def get_baseline_snapshot(
        self,
        case_id: str,
    ) -> dict[str, float]:
        """
        온톨로지 노드의 현재 값 스냅샷 (baseline_data 구성용).

        Synapse의 온톨로지 데이터에서 각 노드의 필드 값을 추출하여
        {"nodeId::field": value} 형태로 반환.

        현재는 Synapse에 전용 엔드포인트가 없으므로,
        온톨로지 전체를 가져와서 노드별 properties에서 수치 값을 추출한다.
        """
        url = f"{self.synapse_base_url}/api/v3/synapse/ontology/cases/{case_id}/ontology"
        snapshot: dict[str, float] = {}

        try:
            client = self._get_client()
            resp = await client.get(url)

            if resp.status_code != 200:
                logger.warning("온톨로지 스냅샷 조회 실패: status=%d", resp.status_code)
                return snapshot

            data = resp.json()
            ontology = data.get("data", data) if isinstance(data, dict) else {}
            nodes = ontology.get("nodes", [])

            for node in nodes:
                node_id = node.get("id", "")
                props = node.get("properties", {})
                if isinstance(props, dict):
                    for field_name, value in props.items():
                        # 수치 값만 추출
                        if isinstance(value, (int, float)):
                            key = f"{node_id}::{field_name}"
                            snapshot[key] = float(value)

        except Exception as e:
            logger.warning("온톨로지 스냅샷 조회 실패: %s", e)

        return snapshot

    async def invalidate_cache(self, case_id: str) -> None:
        """특정 case의 모델 그래프 캐시를 무효화."""
        if self._redis:
            try:
                cache_key = f"whatif:model_graph:{case_id}"
                await self._redis.delete(cache_key)
                logger.debug("모델 그래프 캐시 무효화: case_id=%s", case_id)
            except Exception as e:
                logger.warning("Redis 캐시 무효화 실패: %s", e)


class ModelGraphFetchError(Exception):
    """Synapse에서 모델 그래프를 가져오지 못했을 때 발생하는 예외."""
    pass
