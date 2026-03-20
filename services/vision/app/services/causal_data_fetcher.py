"""
인과 분석용 데이터 수집기.

역할:
1. Synapse -> 온톨로지 노드/관계 조회 (case_id 기준)
2. Weaver -> 바인딩된 데이터소스에서 시계열 데이터 조회
3. DataFrame 조립 + relation_hints 생성

CausalDataFetcher는 Vision 서비스에서 Synapse/Weaver를 호출하여
인과 분석 엔진에 필요한 입력 데이터를 수집하는 어댑터 계층이다.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx
import pandas as pd

from app.engines.causal_analysis_engine import DETERMINISTIC_RELATION_TYPES
from app.services._utils import utc_now_iso as _now

logger = logging.getLogger(__name__)

# 서비스 URL 기본값 (docker-compose 기준)
_DEFAULT_SYNAPSE_URL = "http://synapse:8003"
_DEFAULT_WEAVER_URL = "http://weaver:8001"


@dataclass
class CausalAnalysisInput:
    """
    인과 분석 엔진 입력 데이터 패키지.

    data: 시계열 데이터프레임 (컬럼 = node_id:field 형식)
    target_var: 타겟 변수명
    relation_hints: (source, target) -> "dynamic"|"deterministic"
    node_metadata: node_id -> {name, layer, ...}
    """
    data: pd.DataFrame
    target_var: str
    relation_hints: dict[tuple[str, str], str] = field(default_factory=dict)
    node_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)


class CausalDataFetcher:
    """
    Synapse/Weaver에서 인과 분석용 데이터를 수집하는 어댑터.

    - Synapse: 온톨로지 노드/관계 조회 (타겟 노드의 이웃)
    - Weaver: SQL 실행 API를 통해 시계열 데이터 조회
    """

    def __init__(
        self,
        synapse_url: str | None = None,
        weaver_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._synapse_url = (
            synapse_url or os.getenv("SYNAPSE_BASE_URL", _DEFAULT_SYNAPSE_URL)
        ).rstrip("/")
        self._weaver_url = (
            weaver_url or os.getenv("WEAVER_BASE_URL", _DEFAULT_WEAVER_URL)
        ).rstrip("/")
        self._timeout = timeout

    async def fetch(
        self,
        case_id: str,
        target_node_id: str,
        target_field: str,
        tenant_id: str,
        max_neighbors: int = 20,
    ) -> CausalAnalysisInput:
        """
        인과 분석에 필요한 데이터를 수집하여 CausalAnalysisInput으로 반환.

        흐름:
        1. Synapse에서 target 노드의 이웃 조회 (관계 포함)
        2. 각 노드의 dataSource 확인
        3. Weaver를 통해 각 dataSource에서 시계열 데이터 조회
        4. DataFrame 조립 + relation_hints 매핑
        """
        headers = {"X-Tenant-Id": tenant_id}

        # (1) Synapse에서 이웃 노드 조회 — 리뷰 #5: case_id 파라미터 미전달
        neighbors_data = await self._get_ontology_neighbors(
            client=None,
            node_id=target_node_id,
            limit=max_neighbors,
            headers=headers,
        )
        nodes = neighbors_data.get("nodes", [])
        relations = neighbors_data.get("relations", neighbors_data.get("edges", []))

        # (2) relation_hints 생성
        relation_hints = self._build_relation_hints(relations)

        # (3) 노드 메타데이터 수집
        node_metadata: dict[str, dict[str, Any]] = {}
        for node in nodes:
            nid = node.get("id") or node.get("node_id", "")
            node_metadata[nid] = {
                "name": node.get("name", nid),
                "layer": node.get("layer", "unknown"),
                "properties": node.get("properties", {}),
            }

        # (4) 시계열 데이터 조회 (Weaver SQL 실행)
        # 각 노드에서 바인딩된 데이터소스/테이블/컬럼 정보를 추출하여 조회
        columns_data: dict[str, pd.Series] = {}
        target_var = f"{target_node_id}:{target_field}"

        # httpx.AsyncClient를 한 번만 생성하여 하위 호출에 재사용
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for node in nodes:
                nid = node.get("id") or node.get("node_id", "")
                props = node.get("properties", {})
                datasource = props.get("datasource") or props.get("dataSource", "")
                table = props.get("table", "")
                value_column = props.get("value_column") or props.get("valueColumn", target_field)
                time_column = props.get("time_column") or props.get("timeColumn", "timestamp")

                if datasource and table:
                    try:
                        series = await self._query_timeseries_column(
                            client=client,
                            datasource=datasource,
                            table=table,
                            column=value_column,
                            time_column=time_column,
                            tenant_id=tenant_id,
                        )
                        if series is not None and len(series) > 0:
                            col_name = f"{nid}:{value_column}"
                            columns_data[col_name] = series
                    except Exception as e:
                        logger.warning("시계열 데이터 조회 실패 (node=%s): %s", nid, e)

        # DataFrame 조립
        if columns_data:
            data = pd.DataFrame(columns_data)
        else:
            # 데이터가 없으면 빈 DataFrame 반환 (엔진에서 경고 발생)
            logger.warning("시계열 데이터를 수집하지 못했습니다. 빈 DataFrame 반환.")
            data = pd.DataFrame()

        return CausalAnalysisInput(
            data=data,
            target_var=target_var,
            relation_hints=relation_hints,
            node_metadata=node_metadata,
        )

    async def _get_ontology_neighbors(
        self,
        *,
        client: httpx.AsyncClient | None,
        node_id: str,
        limit: int,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """
        Synapse /api/v3/synapse/ontology/nodes/{node_id}/neighbors 호출.

        리뷰 #5: Synapse neighbors API는 case_id 파라미터가 없으므로 제거.
        client가 None이면 내부에서 일회성 클라이언트를 생성한다.
        """
        url = f"{self._synapse_url}/api/v3/synapse/ontology/nodes/{node_id}/neighbors"
        try:
            # 외부에서 전달받은 클라이언트가 있으면 재사용, 없으면 새로 생성
            if client is not None:
                resp = await client.get(url, params={"limit": limit}, headers=headers)
                if resp.status_code == 200:
                    return resp.json().get("data", resp.json())
                logger.warning("Synapse neighbors 조회 실패: status=%d", resp.status_code)
                return {"nodes": [], "relations": []}
            else:
                async with httpx.AsyncClient(timeout=self._timeout) as _client:
                    resp = await _client.get(url, params={"limit": limit}, headers=headers)
                    if resp.status_code == 200:
                        return resp.json().get("data", resp.json())
                    logger.warning("Synapse neighbors 조회 실패: status=%d", resp.status_code)
                    return {"nodes": [], "relations": []}
        except Exception as e:
            logger.warning("Synapse neighbors 조회 예외: %s", e)
            return {"nodes": [], "relations": []}

    async def _query_timeseries_column(
        self,
        *,
        client: httpx.AsyncClient,
        datasource: str,
        table: str,
        column: str,
        time_column: str,
        tenant_id: str,
        limit: int = 1000,
    ) -> pd.Series | None:
        """
        Weaver SQL 실행 API를 통해 시계열 데이터의 단일 컬럼을 조회.

        최근 N행만 가져온다 (성능 보호).
        외부에서 전달받은 httpx.AsyncClient를 재사용한다.
        """
        # SQL Injection 방지: 식별자 검증 (영숫자 + 언더스코어만 허용)
        import re
        _SAFE_ID = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,127}$')
        for name in (table, column, time_column):
            if not _SAFE_ID.match(name):
                logger.warning("안전하지 않은 식별자 거부: %s", name)
                return None

        sql = (
            f'SELECT "{time_column}", "{column}" '
            f'FROM "{table}" '
            f'ORDER BY "{time_column}" DESC '
            f"LIMIT {limit}"
        )
        url = f"{self._weaver_url}/api/v3/weaver/datasources/{datasource}/query"
        try:
            resp = await client.post(
                url,
                json={"sql": sql},
                headers={"X-Tenant-Id": tenant_id},
            )
            if resp.status_code == 200:
                rows = resp.json().get("data", {}).get("rows", [])
                if rows:
                    values = [r.get(column) for r in rows if r.get(column) is not None]
                    return pd.Series(values, dtype=float, name=column)
            return None
        except Exception as e:
            logger.warning("Weaver 시계열 조회 실패 (table=%s, col=%s): %s", table, column, e)
            return None

    async def save_causal_edges_to_synapse(
        self,
        case_id: str,
        edges: list[dict[str, Any]],
        tenant_id: str,
        analysis_id: str,
    ) -> int:
        """
        인과 분석 결과 엣지를 Synapse에 CAUSES 관계로 저장.

        리뷰 #4: source/target에서 :{field} 접미사 제거 후 저장.
        """
        saved_count = 0
        now = _now()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for edge in edges:
                # :{field} 접미사 제거 — Synapse에는 node_id만 저장
                source_id = edge["source"].split(":")[0] if ":" in edge["source"] else edge["source"]
                target_id = edge["target"].split(":")[0] if ":" in edge["target"] else edge["target"]

                payload = {
                    "case_id": case_id,
                    "source_id": source_id,
                    "target_id": target_id,
                    "type": "CAUSES",
                    "properties": {
                        "weight": edge["strength"],
                        "lag": edge["lag"],
                        "confidence": round(1.0 - edge["p_value"], 4),
                        "method": edge["method"],
                        "direction": edge["direction"],
                        "analysis_id": analysis_id,
                        "analyzed_at": now,
                        "engine_version": "1.0.0",
                    },
                }
                try:
                    resp = await client.post(
                        f"{self._synapse_url}/api/v3/synapse/ontology/relations",
                        json=payload,
                        headers={"X-Tenant-Id": tenant_id},
                    )
                    if resp.status_code in (200, 201):
                        saved_count += 1
                    else:
                        logger.warning(
                            "인과 관계 저장 실패: %s -> %s (status=%d)",
                            source_id, target_id, resp.status_code,
                        )
                except Exception as e:
                    logger.warning("인과 관계 저장 예외: %s -> %s: %s", source_id, target_id, e)
        return saved_count

    @staticmethod
    def _build_relation_hints(
        relations: list[dict[str, Any]],
    ) -> dict[tuple[str, str], str]:
        """
        온톨로지 관계 타입을 relation_hints로 변환.

        FORMULA, DERIVED_FROM, AGGREGATES -> "deterministic"
        그 외 -> "dynamic"
        """
        hints: dict[tuple[str, str], str] = {}
        for rel in relations:
            rel_type = (rel.get("type") or "").upper()
            source_id = rel.get("source_id") or rel.get("source", "")
            target_id = rel.get("target_id") or rel.get("target", "")
            if source_id and target_id:
                hint_type = "deterministic" if rel_type in DETERMINISTIC_RELATION_TYPES else "dynamic"
                hints[(source_id, target_id)] = hint_type
        return hints
