"""Insight 온톨로지 연동 API — P0-3 구현.

Synapse 온톨로지 서비스와 연동하여 KPI/Driver/Node 정보를 제공하는 엔드포인트.
기존 /api/insight 라우터에 추가되는 온톨로지 기반 엔드포인트들이다.

엔드포인트 목록:
  - GET  /api/insight/ontology/kpis          — 온톨로지 KPI 노드 목록
  - GET  /api/insight/ontology/drivers       — KPI의 원인 Driver 노드 목록
  - GET  /api/insight/nodes/{node_id}        — 노드 상세 + 이웃 + 관계
  - POST /api/insight/logs:auto-ingest       — Oracle 자동 수집 전용
  - GET  /api/insight/schema-coverage/datasource — 데이터소스별 스키마 커버리지
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.insight_auth import get_effective_tenant_id
from app.core.insight_errors import InsightError
from app.api.schemas.insight_schemas import (
    DatasourceSchemaCoverageResponse,
    IngestLogsResponse,
    NodeDetailResponse,
    NodeNeighborItem,
    NodeRelationItem,
    OntologyDriverItem,
    OntologyKpiItem,
    UnmappedTableItem,
)
from app.services.synapse_ontology_client import (
    synapse_ontology_client,
    SynapseOntologyClientError,
)

logger = logging.getLogger("weaver.insight_ontology_api")

router = APIRouter(prefix="/api/insight", tags=["insight-ontology"])


# ── Pydantic 요청 모델 ────────────────────────────────────────


class AutoIngestRequest(BaseModel):
    """Oracle 자동 수집 요청 모델.

    Oracle 서비스가 SQL 실행 후 자동으로 전송하는 데이터 형식.
    question(자연어 질문), sql, datasource_id 등을 포함한다.
    """
    question: Optional[str] = Field(default="", description="사용자 자연어 질문")
    sql: str = Field(..., min_length=1, description="실행된 SQL")
    datasource_id: str = Field(..., min_length=1, description="데이터소스 ID")
    execution_time_ms: Optional[int] = Field(default=None, description="SQL 실행 시간 (ms)")
    row_count: Optional[int] = Field(default=None, description="결과 행 수")


# ── 내부 헬퍼 ─────────────────────────────────────────────────


def _safe_float(val) -> float | None:
    """안전하게 float로 변환. 실패 시 None 반환."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ── GET /ontology/kpis — 온톨로지 KPI 목록 ─────────────────────


@router.get("/ontology/kpis")
async def list_ontology_kpis(
    request: Request,
    case_id: str = Query(..., description="온톨로지가 속한 케이스 ID"),
    limit: int = Query(default=200, le=500),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """온톨로지에서 KPI 레이어 노드 목록을 반환한다.

    Synapse 온톨로지 API를 호출하여 KPI 레이어의 모든 노드를 가져온다.
    각 노드에서 id, name, description, unit 등을 추출하여 표준 형식으로 반환.

    Synapse 연결 실패 시 빈 목록을 반환한다 (graceful degradation).
    """
    nodes = await synapse_ontology_client.fetch_kpi_nodes(
        case_id=case_id,
        tenant_id=tenant_id,
        limit=limit,
    )

    # Synapse 노드 데이터를 표준 KPI 항목으로 변환
    kpis: list[dict] = []
    for node in nodes:
        props = node.get("properties", {}) or {}
        kpi_item = OntologyKpiItem(
            id=node.get("id", ""),
            name=node.get("name", node.get("label", "")),
            description=props.get("description", ""),
            unit=props.get("unit", ""),
            current_value=_safe_float(props.get("current_value")),
            source="ontology",
            primary=True,
            fingerprint=node.get("id", ""),
            datasource=props.get("datasource", ""),
            query_count=0,
            last_seen=None,
            trend=props.get("trend"),
            aliases=props.get("aliases", []),
        )
        kpis.append(kpi_item.model_dump())

    return {
        "kpis": kpis,
        "total": len(kpis),
        "source": "ontology",
        "case_id": case_id,
    }


# ── GET /ontology/drivers — KPI 원인 Driver 목록 ──────────────


@router.get("/ontology/drivers")
async def list_ontology_drivers(
    request: Request,
    kpi_id: str = Query(..., description="KPI 노드 ID"),
    limit: int = Query(default=100, le=200),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """특정 KPI에 영향을 미치는 Driver(원인) 노드 목록을 반환한다.

    Synapse에서 KPI 노드의 이웃을 조회하여 CAUSES, INFLUENCES, DERIVED_FROM 등
    인과 관계로 연결된 노드를 추출한다.

    weight와 confidence 정보가 있으면 함께 반환한다.
    """
    # 이웃 노드 + 관계 전체 데이터 조회
    full_data = await synapse_ontology_client.fetch_node_neighbors_full(
        node_id=kpi_id,
        tenant_id=tenant_id,
        limit=limit,
    )

    neighbor_nodes = full_data.get("nodes", [])
    relations = full_data.get("relations", [])

    # 관계 정보를 노드 ID 기준으로 매핑 (target → relation)
    relation_map: dict[str, dict] = {}
    for rel in relations:
        # KPI가 source이면 target이 driver, KPI가 target이면 source가 driver
        if rel.get("source") == kpi_id:
            relation_map[rel.get("target", "")] = rel
        elif rel.get("target") == kpi_id:
            relation_map[rel.get("source", "")] = rel

    # 인과 관계 타입 필터링 (driver에 해당하는 관계만)
    causal_types = {
        "CAUSES", "INFLUENCES", "DERIVED_FROM", "OBSERVED_IN",
        "IMPACTS", "AFFECTS", "CORRELATES",
    }

    drivers: list[dict] = []
    for node in neighbor_nodes:
        node_id_val = node.get("id", "")
        rel = relation_map.get(node_id_val, {})
        rel_type = rel.get("type", "")

        # 인과 관계가 아닌 이웃은 건너뛰기 (관계 타입 필터)
        # 관계 타입이 없으면 모든 이웃을 포함 (Synapse 응답 구조에 따라)
        if rel_type and rel_type.upper() not in causal_types:
            continue

        props = rel.get("properties", {}) or {}
        driver_item = OntologyDriverItem(
            id=node_id_val,
            name=node.get("name", node.get("label", "")),
            layer=node.get("layer", node.get("labels", [""])[0] if node.get("labels") else ""),
            relation_type=rel_type,
            weight=_safe_float(props.get("weight", rel.get("weight"))),
            confidence=_safe_float(props.get("confidence", rel.get("confidence"))),
        )
        drivers.append(driver_item.model_dump())

    # weight 기준 내림차순 정렬
    drivers.sort(key=lambda d: d.get("weight") or 0, reverse=True)

    return {
        "drivers": drivers,
        "total": len(drivers),
        "kpi_id": kpi_id,
        "source": "ontology",
    }


# ── GET /nodes/{node_id} — 노드 상세 정보 ─────────────────────


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
async def get_node_detail(
    node_id: str,
    request: Request,
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """특정 온톨로지 노드의 상세 정보를 반환한다.

    Synapse 온톨로지에서 노드 기본 정보와 이웃 + 관계를 조회하여 반환한다.
    노드가 존재하지 않으면 404를 반환한다.
    """
    # 노드 상세 정보 조회
    node_data = await synapse_ontology_client.fetch_node_detail(
        node_id=node_id,
        tenant_id=tenant_id,
    )

    if node_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"노드 '{node_id}'를 찾을 수 없습니다",
        )

    # 이웃 + 관계 조회
    full_neighbors = await synapse_ontology_client.fetch_node_neighbors_full(
        node_id=node_id,
        tenant_id=tenant_id,
    )

    # 이웃 노드를 표준 형식으로 변환
    neighbors = [
        NodeNeighborItem(
            id=n.get("id", ""),
            name=n.get("name", n.get("label", "")),
            layer=n.get("layer", ""),
            type=n.get("type", n.get("labels", [""])[0] if n.get("labels") else ""),
        )
        for n in full_neighbors.get("nodes", [])
    ]

    # 관계를 표준 형식으로 변환
    relations = [
        NodeRelationItem(
            source=r.get("source", ""),
            target=r.get("target", ""),
            type=r.get("type", ""),
            weight=_safe_float(r.get("weight")),
            confidence=_safe_float(r.get("confidence")),
        )
        for r in full_neighbors.get("relations", [])
    ]

    # 노드 데이터 정규화
    node_out = {
        "id": node_data.get("id", node_id),
        "name": node_data.get("name", node_data.get("label", "")),
        "layer": node_data.get("layer", ""),
        "properties": node_data.get("properties", {}),
    }

    return NodeDetailResponse(
        node=node_out,
        neighbors=neighbors,
        relations=relations,
    )


# ── POST /logs:auto-ingest — Oracle 자동 수집 전용 ─────────────


@router.post("/logs:auto-ingest", status_code=201, response_model=IngestLogsResponse)
async def auto_ingest_from_oracle(
    body: AutoIngestRequest,
    request: Request,
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """Oracle 서비스에서 SQL 쿼리 실행 후 자동으로 로그를 전송하는 전용 엔드포인트.

    기존 POST /logs:ingest와 유사하지만, Oracle 자동 수집에 특화된 입력 형식을 받는다.
    question(자연어 질문), sql, datasource_id, execution_time_ms, row_count를 받아
    InsightJob 로그로 변환하여 저장한다.
    """
    from app.core.insight_redis import get_insight_redis
    from app.core.rls_session import rls_session
    from app.services.insight_store import insight_store, InsightStoreUnavailableError
    from app.services.insight_query_store import insert_logs
    from app.services.sql_normalize import normalize_sql, mask_pii
    from app.services.idempotency import realtime_query_id

    try:
        pool = await insight_store.get_pool()
    except InsightStoreUnavailableError as exc:
        raise InsightError(
            status_code=503, error_code="STORE_UNAVAILABLE",
            error_message=str(exc), retryable=True, hint="DB may be starting up",
        ) from exc

    trace_id = (
        getattr(request.state, "request_id", "")
        or request.headers.get("X-Request-Id", "")
    )

    # SQL 정규화 및 해시 생성
    norm = mask_pii(normalize_sql(body.sql))
    sql_hash = hashlib.sha256(norm.encode()).hexdigest()[:16]
    now = datetime.now(timezone.utc)
    qid = realtime_query_id(norm, tenant_id, body.datasource_id, str(uuid.uuid4()))

    prepared = [{
        "query_id": qid,
        "raw_sql": body.sql,
        "normalized_sql": norm,
        "sql_hash": sql_hash,
        "datasource_id": body.datasource_id,
        "executed_at": now,
        "duration_ms": body.execution_time_ms,
        "user_id": "oracle:auto",
        "source": "oracle_auto",
    }]

    async with rls_session(pool, tenant_id) as conn:
        result = await insert_logs(conn, tenant_id, prepared)

    # Redis에 자동 수집 메타데이터 캐시 (선택적 — 실패해도 무시)
    try:
        rd = await get_insight_redis()
        if rd is not None:
            cache_data = {
                "question": body.question or "",
                "sql": body.sql,
                "datasource_id": body.datasource_id,
                "row_count": body.row_count or 0,
                "execution_time_ms": body.execution_time_ms or 0,
                "ingested_at": now.isoformat(),
            }
            await rd.setex(
                f"insight:auto_ingest:{sql_hash}",
                3600,  # 1시간 TTL
                json.dumps(cache_data),
            )
    except Exception:
        # Redis 캐시 실패는 무시 (로그 저장은 이미 완료)
        logger.debug("Auto-ingest Redis 캐시 저장 실패 (무시)", exc_info=True)

    return IngestLogsResponse(
        inserted=result["inserted"],
        deduped=result["deduped"],
        trace_id=trace_id,
    )


# ── GET /schema-coverage/datasource — 데이터소스 기반 커버리지 ──


@router.get(
    "/schema-coverage/datasource",
    response_model=DatasourceSchemaCoverageResponse,
)
async def schema_coverage_by_datasource(
    request: Request,
    datasource_id: str = Query(..., description="데이터소스 ID"),
    case_id: str = Query(default="", description="온톨로지 케이스 ID (비어있으면 커버리지 0%)"),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    """데이터소스의 스키마 커버리지 통계를 반환한다.

    Weaver 메타데이터 카탈로그에서 데이터소스의 전체 테이블/컬럼 수를 가져오고,
    Synapse 온톨로지에서 매핑된 노드 수를 비교하여 커버리지 비율을 계산한다.

    case_id가 없으면 온톨로지 매핑 정보 없이 테이블 목록만 반환한다.
    """
    from app.services.weaver_runtime import weaver_runtime

    # 1단계: Weaver 런타임에서 데이터소스 메타데이터(테이블/컬럼) 수집
    all_tables: list[dict] = []
    total_columns = 0

    # weaver_runtime.catalogs에서 데이터소스의 스키마 정보 검색
    catalog = weaver_runtime.catalogs.get(datasource_id, {})
    if not catalog:
        # PostgresMetadataStore에서 조회 시도
        try:
            from app.services.postgres_metadata_store import postgres_metadata_store
            from app.core.config import settings
            if settings.metadata_pg_mode:
                ds = await postgres_metadata_store.get_datasource(datasource_id, tenant_id)
                if ds and ds.get("catalog"):
                    catalog = ds["catalog"]
        except Exception:
            logger.debug("PG 메타데이터 조회 실패 (datasource=%s)", datasource_id)

    # 카탈로그에서 테이블/컬럼 추출
    for schema_name, tables in catalog.items():
        if not isinstance(tables, dict):
            continue
        for table_name, columns in tables.items():
            col_count = len(columns) if isinstance(columns, list) else 0
            all_tables.append({
                "table_name": table_name,
                "schema_name": schema_name,
                "column_count": col_count,
            })
            total_columns += col_count

    total_table_count = len(all_tables)

    # 2단계: Synapse 온톨로지에서 매핑된 노드 조회 (case_id가 있을 때만)
    mapped_table_names: set[str] = set()
    mapped_column_count = 0

    if case_id:
        try:
            # 온톨로지 전체 노드 조회하여 TABLE/COLUMN 매핑 확인
            ontology_nodes = await synapse_ontology_client.fetch_all_ontology_nodes(
                case_id=case_id,
                tenant_id=tenant_id,
                limit=1000,
            )

            for node in ontology_nodes:
                props = node.get("properties", {}) or {}
                # 테이블 매핑 확인 (datasource 기반 필터)
                node_ds = props.get("datasource", props.get("datasource_id", ""))
                if node_ds and node_ds != datasource_id:
                    continue

                node_type = (node.get("type") or "").upper()
                if node_type == "TABLE" or "table" in (node.get("layer") or "").lower():
                    tbl_name = props.get("table_name", node.get("name", ""))
                    if tbl_name:
                        mapped_table_names.add(tbl_name.lower())
                elif node_type == "COLUMN" or "column" in (node.get("layer") or "").lower():
                    mapped_column_count += 1

        except SynapseOntologyClientError:
            logger.info("스키마 커버리지: Synapse 온톨로지 조회 실패 (graceful)")

    mapped_table_count = sum(
        1 for t in all_tables
        if t["table_name"].lower() in mapped_table_names
    )

    # 미매핑 테이블 목록
    unmapped = [
        UnmappedTableItem(
            table_name=t["table_name"],
            schema_name=t["schema_name"],
        )
        for t in all_tables
        if t["table_name"].lower() not in mapped_table_names
    ]

    # 커버리지 비율 계산
    coverage_pct = (
        round(mapped_table_count / total_table_count * 100, 1)
        if total_table_count > 0 else 0.0
    )
    col_coverage_pct = (
        round(mapped_column_count / total_columns * 100, 1)
        if total_columns > 0 else 0.0
    )

    return DatasourceSchemaCoverageResponse(
        datasource_id=datasource_id,
        total_tables=total_table_count,
        mapped_tables=mapped_table_count,
        coverage_pct=coverage_pct,
        unmapped_tables=unmapped,
        total_columns=total_columns,
        mapped_columns=mapped_column_count,
        column_coverage_pct=col_coverage_pct,
    )
