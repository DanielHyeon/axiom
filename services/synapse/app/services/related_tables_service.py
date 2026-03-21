"""RelatedTablesService — 스키마 탐색용 관련 테이블 통합 서비스 (ADR-033).

Strategy/Resolver 패턴으로 Neo4j에서 관련 테이블을 조회한다.
두 가지 모드를 지원한다:
  - ROBO  : 코드 분석 기반 테이블 (datasource_name 없는 :Table 노드)
  - TEXT2SQL : 데이터 패브릭 메타데이터 (datasource_name 있는 :Table 노드)

실제 Neo4j 스키마 (metadata_graph_service.py 참조):
  (:DataSource) -[:HAS_SCHEMA]-> (:Schema) -[:HAS_TABLE]-> (:Table) -[:HAS_COLUMN]-> (:Column)
  Table 프로퍼티: tenant_id, datasource_name, schema_name, name
  Column 프로퍼티: tenant_id, datasource_name, schema_name, table_name, name, dtype, nullable
  FK 관계: (:Column)-[:FK_TO]->(:Column), (:Table)-[:FK_TO_TABLE]->(:Table)

Step 4 기능:
  - 4-1: 가중치 기반 스코어링 (FK 수 + 방향 + hop 거리)
  - 4-2: 허브 테이블 감지 (FK 10개 이상 → autoAddRecommended=false)
  - 4-3: Multi-hop 탐색 (depth=1~3)
  - tenant_id 멀티테넌트 격리
"""
from __future__ import annotations

from enum import Enum

import structlog
from pydantic import BaseModel, ConfigDict, Field

from app.core.neo4j_client import neo4j_client

logger = structlog.get_logger(__name__)

# ────────────────────────────────────────────────────────
# 상수
# ────────────────────────────────────────────────────────

# 허브 테이블 판정 기준: FK_TO_TABLE 관계가 이 수 이상이면 허브
HUB_FK_THRESHOLD = 10


# ────────────────────────────────────────────────────────
# 유틸리티 함수
# ────────────────────────────────────────────────────────

def build_node_key(mode: str, datasource: str | None, schema: str | None, table: str) -> str:
    """노드 키를 만든다. 프론트엔드와 백엔드가 같은 규칙으로 키를 생성한다.

    형식: {mode}:{datasource 또는 빈 문자열}:{schema 또는 'public'}:{table}
    """
    ds = datasource or ""
    sc = schema or "public"
    # 프론트엔드는 소문자('robo', 'text2sql')를 사용하므로 통일한다
    return f"{mode.lower()}:{ds}:{sc}:{table}"


def _compute_score(
    base_score: float,
    fk_count: int,
    hop_distance: int = 1,
) -> float:
    """관련도 점수를 계산한다 (Step 4-1).

    가중치 요소:
      - base_score: 관계 방향에 따른 기본 점수 (FK_OUT=1.0, FK_IN=0.85 등)
      - fk_count: FK 컬럼 수가 많을수록 가산 (최대 +0.09)
      - hop_distance: 홉 거리가 멀수록 감점 (2홉=-0.15, 3홉=-0.30)
    """
    # FK 수 보너스: 최대 0.09까지 (1개=0.02, 2개=0.04, ... 5개 이상=0.09)
    fk_bonus = min(fk_count * 0.02, 0.09)
    # 홉 거리 페널티: 1홉=0, 2홉=-0.15, 3홉=-0.30
    hop_penalty = max(0, (hop_distance - 1)) * 0.15
    return round(base_score + fk_bonus - hop_penalty, 3)


def _row_to_item(
    row: dict,
    mode: str,
    relation_type: str,
    base_score: float,
    datasource_name: str = "",
    hop_distance: int = 1,
) -> RelatedTableItem:
    """Neo4j 결과 행 하나를 RelatedTableItem으로 변환하는 공통 헬퍼."""
    fk_count = int(row.get("fk_count", 0) or 0)
    rel_ds = str(row.get("related_ds") or datasource_name or "")
    rel_schema = str(row.get("related_schema") or "public")
    rel_table = str(row["related_table"])
    hop = int(row.get("hop_distance", hop_distance) or hop_distance)

    # FK 컬럼 쌍 구성 — 소스/타겟 컬럼 리스트를 zip하여 ColumnPair로 변환
    src_cols = row.get("source_cols") or []
    tgt_cols = row.get("target_cols") or []
    pairs = [
        ColumnPair(sourceColumn=s, targetColumn=t)
        for s, t in zip(src_cols, tgt_cols)
        if s and t
    ]

    return RelatedTableItem(
        tableId=build_node_key(mode, rel_ds, rel_schema, rel_table),
        tableName=rel_table,
        schemaName=rel_schema,
        datasourceName=rel_ds,
        relationType=relation_type,
        score=_compute_score(base_score, fk_count, hop),
        fkCount=fk_count,
        sourceColumns=src_cols,
        targetColumns=tgt_cols,
        columnPairs=pairs,
        hopDistance=hop,
        autoAddRecommended=True,  # 허브 감지 후 후처리에서 변경됨
    )


# ────────────────────────────────────────────────────────
# Enum & Pydantic 모델
# ────────────────────────────────────────────────────────

class SchemaMode(str, Enum):
    """스키마 탐색 모드 — ROBO는 코드 분석, TEXT2SQL은 데이터 패브릭"""
    ROBO = "ROBO"
    TEXT2SQL = "TEXT2SQL"


class ColumnPair(BaseModel):
    """FK 컬럼 매핑 한 쌍 — 소스 컬럼이 타겟 컬럼을 참조한다."""
    model_config = ConfigDict(populate_by_name=True)
    source_column: str = Field(alias="sourceColumn")
    target_column: str = Field(alias="targetColumn")


class RelatedTableRequest(BaseModel):
    """관련 테이블 조회 요청 — 프론트엔드에서 보내는 JSON과 매핑된다."""
    model_config = ConfigDict(populate_by_name=True)

    mode: SchemaMode
    table_name: str = Field(alias="tableName")
    schema_name: str = Field(default="public", alias="schemaName")
    datasource_name: str = Field(default="", alias="datasourceName")
    node_key: str | None = Field(default=None, alias="nodeKey")
    already_loaded_table_ids: list[str] = Field(default_factory=list, alias="alreadyLoadedTableIds")
    limit: int = Field(default=5, ge=1, le=20)
    depth: int = Field(default=1, ge=1, le=3)

    def get_node_key(self) -> str:
        """nodeKey가 있으면 그대로, 없으면 새로 만든다."""
        if self.node_key:
            return self.node_key
        return build_node_key(self.mode.value, self.datasource_name, self.schema_name, self.table_name)


class RelatedTableItem(BaseModel):
    """관련 테이블 하나의 정보 — FK 관계, 점수, 컬럼 매핑 등을 담는다."""
    model_config = ConfigDict(populate_by_name=True)

    table_id: str = Field(alias="tableId")
    table_name: str = Field(alias="tableName")
    schema_name: str = Field(default="public", alias="schemaName")
    datasource_name: str = Field(default="", alias="datasourceName")
    relation_type: str = Field(alias="relationType")       # FK_OUT, FK_IN
    score: float = 1.0
    fk_count: int = Field(default=0, alias="fkCount")
    source_columns: list[str] = Field(default_factory=list, alias="sourceColumns")
    target_columns: list[str] = Field(default_factory=list, alias="targetColumns")
    column_pairs: list[ColumnPair] = Field(default_factory=list, alias="columnPairs")
    hop_distance: int = Field(default=1, alias="hopDistance")
    auto_add_recommended: bool = Field(default=True, alias="autoAddRecommended")


class RelatedTableResponse(BaseModel):
    """관련 테이블 조회 응답 — 소스 테이블 정보 + 관련 테이블 목록 + 메타."""
    model_config = ConfigDict(populate_by_name=True)

    source_table: dict = Field(alias="sourceTable")
    related_tables: list[RelatedTableItem] = Field(alias="relatedTables")
    meta: dict


class SchemaAvailabilityResponse(BaseModel):
    """스키마 모드별 사용 가능한 테이블 개수를 알려준다."""
    robo: dict   # {"table_count": int}
    text2sql: dict  # {"table_count": int}


# ────────────────────────────────────────────────────────
# 서비스 함수: 스키마 가용성 조회
# ────────────────────────────────────────────────────────

async def fetch_schema_availability(
    datasource_name: str | None = None,
    tenant_id: str = "",
) -> SchemaAvailabilityResponse:
    """Neo4j에서 :Table 노드 개수를 모드별로 세서 돌려준다.

    ROBO 모드: datasource_name이 비어있는 Table 노드 (코드 분석 결과)
    TEXT2SQL 모드: datasource_name이 있는 Table 노드 (DB 메타데이터)
    """
    # 테넌트 필터 조건 — 비어있으면 무시 (개발 환경 호환)
    tid_clause = "AND t.tenant_id = $tid" if tenant_id else ""

    # ROBO: datasource_name이 없는 Table
    robo_query = f"""
    MATCH (t:Table)
    WHERE (t.datasource_name IS NULL OR t.datasource_name = '')
    {tid_clause}
    RETURN count(t) AS cnt
    """
    robo_rows = await neo4j_client.execute_read(robo_query, {"tid": tenant_id})
    robo_count = robo_rows[0]["cnt"] if robo_rows else 0

    # TEXT2SQL: datasource_name이 있는 Table
    if datasource_name:
        fabric_query = f"""
        MATCH (t:Table)
        WHERE t.datasource_name = $ds AND t.datasource_name <> ''
        {tid_clause}
        RETURN count(t) AS cnt
        """
        fabric_rows = await neo4j_client.execute_read(fabric_query, {"ds": datasource_name, "tid": tenant_id})
    else:
        fabric_query = f"""
        MATCH (t:Table)
        WHERE t.datasource_name IS NOT NULL AND t.datasource_name <> ''
        {tid_clause}
        RETURN count(t) AS cnt
        """
        fabric_rows = await neo4j_client.execute_read(fabric_query, {"tid": tenant_id})

    fabric_count = fabric_rows[0]["cnt"] if fabric_rows else 0

    logger.info(
        "스키마 가용성 조회 완료",
        robo_count=robo_count,
        text2sql_count=fabric_count,
        datasource_filter=datasource_name,
        tenant_id=tenant_id,
    )

    return SchemaAvailabilityResponse(
        robo={"table_count": robo_count},
        text2sql={"table_count": fabric_count},
    )


# ────────────────────────────────────────────────────────
# 서비스 함수: 통합 관련 테이블 조회 (메인 진입점)
# ────────────────────────────────────────────────────────

async def fetch_related_tables_unified(
    request: RelatedTableRequest,
    tenant_id: str = "",
) -> RelatedTableResponse:
    """모드에 따라 적절한 리졸버를 호출하고, 결과를 통합해서 돌려준다.

    1) 모드별 리졸버로 후보 테이블 목록을 가져온다 (multi-hop 지원).
    2) 허브 테이블을 감지하여 autoAddRecommended=false 처리한다.
    3) 이미 로드된 테이블을 제외한다.
    4) 점수 내림차순 정렬 후 limit만큼 잘라낸다.
    """
    node_key = request.get_node_key()

    logger.info(
        "관련 테이블 조회 시작",
        mode=request.mode.value,
        table=request.table_name,
        schema=request.schema_name,
        datasource=request.datasource_name,
        depth=request.depth,
        node_key=node_key,
        already_loaded=len(request.already_loaded_table_ids),
        tenant_id=tenant_id,
    )

    # 모드별 분기 — Strategy 패턴
    if request.mode == SchemaMode.ROBO:
        candidates = await _resolve_robo(
            request.table_name, request.schema_name,
            depth=request.depth, tenant_id=tenant_id,
        )
    else:
        candidates = await _resolve_text2sql(
            request.table_name, request.schema_name, request.datasource_name,
            depth=request.depth, tenant_id=tenant_id,
        )

    # Step 4-2: 허브 테이블 감지 — FK가 많은 테이블은 자동 추가 비추천
    if candidates:
        hub_set = await _detect_hub_tables(
            [c.table_name for c in candidates], tenant_id=tenant_id,
        )
        for item in candidates:
            if item.table_name in hub_set:
                item.auto_add_recommended = False

    # 이미 로드된 테이블 제외
    already_set = set(request.already_loaded_table_ids)
    filtered = [item for item in candidates if item.table_id not in already_set]
    excluded_count = len(candidates) - len(filtered)

    # 점수 내림차순 정렬 후 limit 적용
    filtered.sort(key=lambda x: x.score, reverse=True)
    result_items = filtered[: request.limit]

    logger.info(
        "관련 테이블 조회 완료",
        mode=request.mode.value,
        total_candidates=len(candidates),
        excluded=excluded_count,
        hub_detected=sum(1 for c in candidates if not c.auto_add_recommended),
        returned=len(result_items),
    )

    return RelatedTableResponse(
        sourceTable={
            "tableId": node_key,
            "tableName": request.table_name,
            "schemaName": request.schema_name,
            "datasourceName": request.datasource_name,
        },
        relatedTables=result_items,
        meta={
            "mode": request.mode.value,
            "limitApplied": request.limit,
            "excludedAlreadyLoaded": excluded_count,
            "depthUsed": request.depth,
        },
    )


# ────────────────────────────────────────────────────────
# Step 4-2: 허브 테이블 감지
# ────────────────────────────────────────────────────────

async def _detect_hub_tables(
    table_names: list[str],
    tenant_id: str = "",
) -> set[str]:
    """FK_TO_TABLE 관계가 HUB_FK_THRESHOLD개 이상인 테이블을 찾는다.

    users, organizations 같은 허브 테이블은 거의 모든 테이블과 연결되어 있어
    자동 추가하면 캔버스가 복잡해진다. 이런 테이블은 autoAddRecommended=false로 표시한다.
    """
    if not table_names:
        return set()

    tid_clause = "AND t.tenant_id = $tid" if tenant_id else ""

    # 후보 테이블들의 FK 연결 수를 한번에 조회
    query = f"""
    UNWIND $names AS table_name
    MATCH (t:Table {{name: table_name}})
    WHERE true {tid_clause}
    OPTIONAL MATCH (t)-[r:FK_TO_TABLE]-()
    WITH t.name AS name, count(r) AS fk_degree
    WHERE fk_degree >= $threshold
    RETURN name
    """
    rows = await neo4j_client.execute_read(
        query, {"names": table_names, "tid": tenant_id, "threshold": HUB_FK_THRESHOLD},
    )
    hub_names = {str(row["name"]) for row in rows}

    if hub_names:
        logger.info("허브 테이블 감지", hub_tables=list(hub_names), threshold=HUB_FK_THRESHOLD)

    return hub_names


# ────────────────────────────────────────────────────────
# 내부 리졸버: ROBO 모드
# ────────────────────────────────────────────────────────

async def _resolve_robo(
    table_name: str,
    schema_name: str,
    depth: int = 1,
    tenant_id: str = "",
) -> list[RelatedTableItem]:
    """:Table 노드 중 datasource_name이 없는 것들에서 FK_TO_TABLE 관계를 찾는다.

    depth=1이면 직접 연결만, depth>=2이면 가변 길이 경로를 사용한다 (Step 4-3).
    """
    params: dict = {"table_name": table_name, "schema_name": schema_name, "tid": tenant_id}

    # depth 범위 강제 — Cypher 인젝션 방어 (C2 수정)
    safe_depth = max(1, min(int(depth), 3))

    if safe_depth == 1:
        # 1홉: 별칭 t1/t2 사용
        tid_t1 = "AND t1.tenant_id = $tid" if tenant_id else ""
        tid_t2 = "AND t2.tenant_id = $tid" if tenant_id else ""
        out_query = f"""
        MATCH (t1:Table)-[r:FK_TO_TABLE]->(t2:Table)
        WHERE t1.name = $table_name
          AND COALESCE(t1.schema_name, 'public') = $schema_name
          AND (t1.datasource_name IS NULL OR t1.datasource_name = '')
          {tid_t1}
        RETURN t2.name AS related_table,
               COALESCE(t2.schema_name, 'public') AS related_schema,
               count(r) AS fk_count,
               1 AS hop_distance
        """
        in_query = f"""
        MATCH (t1:Table)-[r:FK_TO_TABLE]->(t2:Table)
        WHERE t2.name = $table_name
          AND COALESCE(t2.schema_name, 'public') = $schema_name
          AND (t2.datasource_name IS NULL OR t2.datasource_name = '')
          {tid_t2}
        RETURN t1.name AS related_table,
               COALESCE(t1.schema_name, 'public') AS related_schema,
               count(r) AS fk_count,
               1 AS hop_distance
        """
        out_rows = await neo4j_client.execute_read(out_query, params)
        in_rows = await neo4j_client.execute_read(in_query, params)

        items: list[RelatedTableItem] = []
        for row in out_rows:
            items.append(_row_to_item(row, "ROBO", "FK_OUT", 1.0))
        for row in in_rows:
            items.append(_row_to_item(row, "ROBO", "FK_IN", 0.85))
        return items
    else:
        # Multi-hop (Step 4-3): 가변 길이 경로 [:FK_TO_TABLE*1..N]
        # start, related, 중간 노드 모두 tenant_id 필터 적용
        tid_start = "AND start.tenant_id = $tid" if tenant_id else ""
        tid_all = "AND ALL(n IN nodes(path) WHERE n.tenant_id = $tid)" if tenant_id else ""
        multi_query = f"""
        MATCH (start:Table {{name: $table_name}})
        WHERE COALESCE(start.schema_name, 'public') = $schema_name
          AND (start.datasource_name IS NULL OR start.datasource_name = '')
          {tid_start}
        MATCH path = (start)-[:FK_TO_TABLE*1..{safe_depth}]-(related:Table)
        WHERE related <> start
          {tid_all}
        RETURN DISTINCT related.name AS related_table,
               COALESCE(related.schema_name, 'public') AS related_schema,
               length(path) AS hop_distance
        ORDER BY hop_distance ASC
        """
        rows = await neo4j_client.execute_read(multi_query, params)

        # Multi-hop에서는 FK 수를 개별 집계하지 않으므로 fk_count=0 (기본값)
        seen: set[str] = set()
        items = []
        for row in rows:
            rel_table = str(row["related_table"])
            if rel_table in seen:
                continue
            seen.add(rel_table)
            hop = int(row.get("hop_distance", 1))
            # 방향 정보가 없으므로 FK_OUT으로 통일
            items.append(_row_to_item(row, "ROBO", "FK_OUT", 1.0, hop_distance=hop))
        return items


# ────────────────────────────────────────────────────────
# 내부 리졸버: TEXT2SQL 모드
# ────────────────────────────────────────────────────────

async def _resolve_text2sql(
    table_name: str,
    schema_name: str,
    datasource_name: str,
    depth: int = 1,
    tenant_id: str = "",
) -> list[RelatedTableItem]:
    """:Table 노드 중 datasource_name이 있는 것들에서 관련 테이블을 찾는다.

    1단계: 테이블 레벨 FK_TO_TABLE 관계를 먼저 시도한다.
    2단계: 결과가 없으면 컬럼 레벨 FK_TO 관계로 폴백한다 (depth=1만).
    """
    # ── 1단계: 테이블 레벨 FK_TO_TABLE 조회 ──
    table_items = await _resolve_text2sql_table_level(
        table_name, schema_name, datasource_name,
        depth=depth, tenant_id=tenant_id,
    )
    if table_items:
        logger.debug("TEXT2SQL 테이블 레벨 FK 발견", table=table_name, found=len(table_items))
        return table_items

    # ── 2단계: 컬럼 레벨 FK_TO 폴백 (depth=1에서만 의미 있음) ──
    col_items = await _resolve_text2sql_column_level(
        table_name, schema_name, datasource_name, tenant_id=tenant_id,
    )
    logger.debug("TEXT2SQL 컬럼 레벨 FK_TO 폴백", table=table_name, found=len(col_items))
    return col_items


async def _resolve_text2sql_table_level(
    table_name: str,
    schema_name: str,
    datasource_name: str,
    depth: int = 1,
    tenant_id: str = "",
) -> list[RelatedTableItem]:
    """:Table 간의 FK_TO_TABLE 관계를 조회한다."""
    tid_clause = "AND st.tenant_id = $tid" if tenant_id else ""
    params: dict = {
        "table_name": table_name, "schema_name": schema_name,
        "ds": datasource_name, "tid": tenant_id,
    }

    # depth 범위 강제 — Cypher 인젝션 방어 (C2 수정)
    safe_depth = max(1, min(int(depth), 3))

    if safe_depth == 1:
        # 1홉: 나가는 + 들어오는 FK
        out_query = f"""
        MATCH (st:Table)-[r:FK_TO_TABLE]->(tt:Table)
        WHERE st.name = $table_name
          AND COALESCE(st.schema_name, 'public') = $schema_name
          AND ($ds = '' OR st.datasource_name = $ds)
          AND ($ds = '' OR tt.datasource_name = $ds)
          {tid_clause}
        RETURN tt.name AS related_table,
               COALESCE(tt.schema_name, 'public') AS related_schema,
               tt.datasource_name AS related_ds,
               count(r) AS fk_count,
               1 AS hop_distance
        """
        in_query = f"""
        MATCH (st:Table)-[r:FK_TO_TABLE]->(tt:Table)
        WHERE tt.name = $table_name
          AND COALESCE(tt.schema_name, 'public') = $schema_name
          AND ($ds = '' OR st.datasource_name = $ds)
          AND ($ds = '' OR tt.datasource_name = $ds)
          {tid_clause}
        RETURN st.name AS related_table,
               COALESCE(st.schema_name, 'public') AS related_schema,
               st.datasource_name AS related_ds,
               count(r) AS fk_count,
               1 AS hop_distance
        """
        out_rows = await neo4j_client.execute_read(out_query, params)
        in_rows = await neo4j_client.execute_read(in_query, params)

        items: list[RelatedTableItem] = []
        for row in out_rows:
            items.append(_row_to_item(row, "TEXT2SQL", "FK_OUT", 0.9, datasource_name))
        for row in in_rows:
            items.append(_row_to_item(row, "TEXT2SQL", "FK_IN", 0.85, datasource_name))
        return items
    else:
        # Multi-hop (Step 4-3) — start, 중간 노드, related 모두 tenant 격리
        tid_start = "AND start.tenant_id = $tid" if tenant_id else ""
        tid_all = "AND ALL(n IN nodes(path) WHERE n.tenant_id = $tid)" if tenant_id else ""
        multi_query = f"""
        MATCH (start:Table {{name: $table_name}})
        WHERE COALESCE(start.schema_name, 'public') = $schema_name
          AND ($ds = '' OR start.datasource_name = $ds)
          {tid_start}
        MATCH path = (start)-[:FK_TO_TABLE*1..{safe_depth}]-(related:Table)
        WHERE related <> start
          AND ($ds = '' OR related.datasource_name = $ds)
          {tid_all}
        RETURN DISTINCT related.name AS related_table,
               COALESCE(related.schema_name, 'public') AS related_schema,
               related.datasource_name AS related_ds,
               length(path) AS hop_distance
        ORDER BY hop_distance ASC
        """
        rows = await neo4j_client.execute_read(multi_query, params)

        seen: set[str] = set()
        items = []
        for row in rows:
            rel_table = str(row["related_table"])
            if rel_table in seen:
                continue
            seen.add(rel_table)
            hop = int(row.get("hop_distance", 1))
            items.append(_row_to_item(row, "TEXT2SQL", "FK_OUT", 0.9, datasource_name, hop))
        return items


async def _resolve_text2sql_column_level(
    table_name: str,
    schema_name: str,
    datasource_name: str,
    tenant_id: str = "",
) -> list[RelatedTableItem]:
    """컬럼 레벨 FK_TO 관계로 관련 테이블을 찾는다 (1홉 전용 폴백).

    :Table -[:HAS_COLUMN]-> :Column -[:FK_TO]-> :Column <-[:HAS_COLUMN]- :Table
    """
    tid_clause = "AND st.tenant_id = $tid" if tenant_id else ""
    params = {
        "table_name": table_name, "schema_name": schema_name,
        "ds": datasource_name, "tid": tenant_id,
    }

    ref_query = f"""
    MATCH (st:Table)-[:HAS_COLUMN]->(sc:Column)
          -[:FK_TO]->(tc:Column)<-[:HAS_COLUMN]-(tt:Table)
    WHERE st.name = $table_name
      AND COALESCE(st.schema_name, 'public') = $schema_name
      AND ($ds = '' OR st.datasource_name = $ds)
      AND ($ds = '' OR tt.datasource_name = $ds)
      AND tt.name <> st.name
      {tid_clause}
    RETURN tt.name AS related_table,
           COALESCE(tt.schema_name, 'public') AS related_schema,
           tt.datasource_name AS related_ds,
           collect(sc.name) AS source_cols,
           collect(tc.name) AS target_cols,
           count(*) AS fk_count
    """
    rev_query = f"""
    MATCH (st:Table)-[:HAS_COLUMN]->(sc:Column)
          -[:FK_TO]->(tc:Column)<-[:HAS_COLUMN]-(tt:Table)
    WHERE tt.name = $table_name
      AND COALESCE(tt.schema_name, 'public') = $schema_name
      AND ($ds = '' OR st.datasource_name = $ds)
      AND ($ds = '' OR tt.datasource_name = $ds)
      AND st.name <> tt.name
      {tid_clause}
    RETURN st.name AS related_table,
           COALESCE(st.schema_name, 'public') AS related_schema,
           st.datasource_name AS related_ds,
           collect(sc.name) AS source_cols,
           collect(tc.name) AS target_cols,
           count(*) AS fk_count
    """

    ref_rows = await neo4j_client.execute_read(ref_query, params)
    rev_rows = await neo4j_client.execute_read(rev_query, params)

    # 양방향 중복 제거
    merged: dict[str, RelatedTableItem] = {}
    for row in ref_rows:
        item = _row_to_item(row, "TEXT2SQL", "FK_OUT", 0.9, datasource_name)
        merged[item.table_id] = item
    for row in rev_rows:
        item = _row_to_item(row, "TEXT2SQL", "FK_IN", 0.85, datasource_name)
        if item.table_id not in merged:
            merged[item.table_id] = item

    return list(merged.values())
