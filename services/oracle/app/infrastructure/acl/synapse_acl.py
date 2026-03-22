"""Anti-Corruption Layer: Synapse BC → Oracle internal domain models.

Oracle의 NL2SQL 파이프라인이 Synapse API 응답 형식에 직접 의존하지 않도록
모든 Synapse 응답을 Oracle 내부 도메인 모델로 변환한다.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Oracle 내부 도메인 모델 (Synapse 응답 형식에 의존하지 않음)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnInfo:
    """테이블 컬럼 정보."""

    name: str
    data_type: str = "varchar"
    description: str | None = None
    is_key: bool = False


@dataclass(frozen=True)
class TableInfo:
    """테이블 메타 정보."""

    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    description: str | None = None
    row_count: int = 0
    has_embedding: bool = False


@dataclass(frozen=True)
class ValueMapping:
    """자연어 → DB 값 매핑."""

    natural_language: str
    db_value: str
    column: str = ""
    table: str = ""


@dataclass(frozen=True)
class CachedQuery:
    """유사 쿼리 캐시."""

    question: str
    sql: str
    confidence: float = 0.0


@dataclass(frozen=True)
class SchemaSearchResult:
    """Synapse 그래프 검색의 Oracle 내부 표현.

    NL2SQL 파이프라인에서 사용하는 스키마 컨텍스트.
    """

    tables: list[TableInfo] = field(default_factory=list)
    value_mappings: list[ValueMapping] = field(default_factory=list)
    cached_queries: list[CachedQuery] = field(default_factory=list)


@dataclass(frozen=True)
class DatasourceInfo:
    """Oracle이 알고 있는 데이터소스 정보."""

    id: str
    name: str
    type: str
    host: str = ""
    database: str = ""
    schema: str = "public"
    status: str = "active"


@dataclass(frozen=True)
class SchemaUpdateResult:
    """테이블/컬럼 설명 업데이트 결과."""

    name: str
    description: str
    vector_updated: bool = False


# ---------------------------------------------------------------------------
# O3: Ontology Context 도메인 모델
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MappedTarget:
    """온톨로지 노드가 매핑된 테이블/컬럼."""

    table: str
    columns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TermMapping:
    """자연어 용어 → 온톨로지 노드 → 테이블 매핑."""

    term: str
    matched_node: str
    layer: str
    confidence: float
    targets: list[MappedTarget] = field(default_factory=list)


@dataclass(frozen=True)
class ContextProvenance:
    """온톨로지 컨텍스트 출처 메타데이터."""

    source: str = "synapse_ontology_v1"
    search_version: str = "2"


@dataclass(frozen=True)
class OntologyContext:
    """NL2SQL 파이프라인에서 사용하는 온톨로지 컨텍스트."""

    term_mappings: list[TermMapping] = field(default_factory=list)
    preferred_tables: list[str] = field(default_factory=list)
    preferred_columns: list[str] = field(default_factory=list)
    provenance: ContextProvenance = field(default_factory=ContextProvenance)


# ---------------------------------------------------------------------------
# P3: 시멘틱 계약 컨텍스트 도메인 모델
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SemanticMeasureDef:
    """시멘틱 지표 정의 — LLM이 raw SQL 대신 사용할 표준 지표."""

    measure_id: str
    name: str
    description: str | None
    measure_type: str
    sql_expression: str
    filter_expression: str | None
    additive_type: str | None
    entity_id: str
    bound_concept_id: str | None = None


@dataclass(frozen=True)
class SemanticDimensionDef:
    """시멘틱 차원 정의."""

    dimension_id: str
    name: str
    sql_expression: str
    value_type: str | None
    hierarchy_path: str | None
    entity_id: str


@dataclass(frozen=True)
class SemanticJoinRule:
    """시멘틱 조인 규칙 — 허용/금지 조인 가드레일."""

    join_id: str
    left_entity_id: str
    right_entity_id: str
    join_type: str
    join_condition: str
    relationship_type: str
    fanout_risk_score: float = 0.0


@dataclass(frozen=True)
class SemanticContractContext:
    """시멘틱 계약 기반 AI 컨텍스트 — raw schema를 대체한다.

    Oracle NL2SQL은 이 컨텍스트를 통해:
    1. 승인된 지표 정의(sql_expression)를 LLM에 제공
    2. 허용된 조인만 사용하도록 가드레일 적용
    3. 동의어 맵으로 사용자 질문을 정규화
    4. 품질 경고를 응답에 포함
    """

    measures: list[SemanticMeasureDef] = field(default_factory=list)
    dimensions: list[SemanticDimensionDef] = field(default_factory=list)
    allowed_joins: list[SemanticJoinRule] = field(default_factory=list)
    banned_entity_pairs: list[tuple[str, str]] = field(default_factory=list)
    synonym_map: dict[str, str] = field(default_factory=dict)
    concept_definitions: dict[str, str] = field(default_factory=dict)
    entity_sources: dict[str, str] = field(default_factory=dict)  # entity_id → physical_source_ref
    quality_warnings: list[str] = field(default_factory=list)
    provenance: str = "synapse_semantic_contract_v1"


@dataclass(frozen=True)
class ResolvedContextPack:
    """해석된 AI 컨텍스트 팩 — 의도별 LLM 컨텍스트 프리셋.

    Oracle은 사용자 질문의 의도를 분류한 후,
    해당 의도에 매칭되는 ContextPack을 조회하여 LLM 프롬프트를 구성한다.
    """
    context_pack_id: str
    intent_type: str
    semantic_context: SemanticContractContext  # 실제 시멘틱 객체
    prompt_rules: list[str] = field(default_factory=list)  # 프롬프트 정책 규칙 텍스트 (우선순위순)
    answer_guardrails: list[str] = field(default_factory=list)  # 응답 가드레일
    quality_gate_min_score: float = 0.0


# ---------------------------------------------------------------------------
# ACL 구현
# ---------------------------------------------------------------------------


class OracleSynapseACL:
    """Anti-Corruption Layer: Synapse BC의 응답을 Oracle NL2SQL 도메인 모델로 변환.

    기존 SynapseClient의 단순 HTTP 호출을 대체하여,
    외부 BC 응답 → 내부 도메인 모델 변환 책임을 집중한다.
    """

    _SEARCH_FALLBACK = SchemaSearchResult()

    def __init__(
        self,
        base_url: str | None = None,
        schema_edit_base: str | None = None,
        service_token: str | None = None,
    ):
        self._base_url = (base_url or settings.SYNAPSE_API_URL).rstrip("/")
        self._schema_edit_base = schema_edit_base or settings.SYNAPSE_SCHEMA_EDIT_BASE
        self._service_token = service_token or settings.SERVICE_TOKEN_ORACLE
        self._datasources_json = settings.ORACLE_DATASOURCES_JSON

    def _headers(self, tenant_id: str = "") -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._service_token}",
            "Content-Type": "application/json",
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
        **kwargs: Any,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        headers = self._headers(tenant_id)
        async with httpx.AsyncClient() as client:
            for attempt in range(max_retries):
                try:
                    res = await client.request(method, url, headers=headers, **kwargs)
                    res.raise_for_status()
                    return res.json()
                except httpx.RequestError as exc:
                    logger.error("synapse_acl_error", attempt=attempt + 1, error=str(exc))
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(1)
                except httpx.HTTPStatusError as exc:
                    logger.error(
                        "synapse_acl_http_error",
                        attempt=attempt + 1,
                        status=exc.response.status_code,
                    )
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(0.5)
        return {}  # unreachable but keeps type checker happy

    # -- Graph Search (NL2SQL 스키마 탐색) ---------------------------------

    async def search_schema_context(
        self,
        query: str,
        tenant_id: str = "",
        context: dict[str, Any] | None = None,
    ) -> SchemaSearchResult:
        """Synapse 그래프 검색 결과를 Oracle SchemaSearchResult로 변환."""
        payload: dict[str, Any] = {"query": query}
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
            logger.warning("synapse_acl_search_fallback", reason=str(exc))
            return self._SEARCH_FALLBACK

        data = response.get("data") if isinstance(response, dict) else None
        if isinstance(data, dict):
            return self._translate_search_result(data)
        return self._SEARCH_FALLBACK

    @staticmethod
    def _translate_search_result(data: dict[str, Any]) -> SchemaSearchResult:
        """Synapse 그래프 검색 응답 → Oracle SchemaSearchResult 변환 (ACL 핵심)."""
        tables_raw = data.get("tables") or {}
        vector_matched = tables_raw.get("vector_matched") or []
        fk_related = tables_raw.get("fk_related") or []

        tables: list[TableInfo] = []
        seen: set[str] = set()

        for t in vector_matched + fk_related:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)

            columns: list[ColumnInfo] = []
            for c in t.get("columns") or []:
                if isinstance(c, dict) and c.get("name"):
                    columns.append(
                        ColumnInfo(
                            name=str(c["name"]).strip(),
                            data_type=str(c.get("data_type", "varchar")),
                            description=c.get("description"),
                            is_key=bool(c.get("is_key", False)),
                        )
                    )
            if not columns:
                columns = [ColumnInfo(name="id"), ColumnInfo(name="name")]

            tables.append(
                TableInfo(
                    name=name,
                    columns=columns,
                    description=t.get("description"),
                    has_embedding=bool(t.get("has_embedding", False)),
                )
            )

        value_mappings = [
            ValueMapping(
                natural_language=str(vm.get("natural_language", vm.get("nl", ""))),
                db_value=str(vm.get("db_value", vm.get("value", ""))),
                column=str(vm.get("column", "")),
                table=str(vm.get("table", "")),
            )
            for vm in (data.get("value_mappings") or [])
            if isinstance(vm, dict)
        ]

        cached_queries = [
            CachedQuery(
                question=str(cq.get("question", "")),
                sql=str(cq.get("sql", "")),
                confidence=float(cq.get("confidence", 0.0)),
            )
            for cq in (data.get("similar_queries") or [])
            if isinstance(cq, dict)
        ]

        return SchemaSearchResult(
            tables=tables,
            value_mappings=value_mappings,
            cached_queries=cached_queries,
        )

    # -- Ontology Context (O3) ------------------------------------------------

    async def search_ontology_context(
        self,
        case_id: str,
        query: str,
        tenant_id: str = "",
    ) -> OntologyContext | None:
        """Synapse ontology context → Oracle OntologyContext 변환. 실패 시 None."""
        try:
            response = await self._request_with_retry(
                "POST",
                "/api/v3/synapse/graph/ontology/context",
                tenant_id=tenant_id,
                json={"case_id": case_id, "query": query},
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning("synapse_acl_ontology_context_failed", reason=str(exc))
            return None

        data = (response or {}).get("data")
        if not data:
            return None
        return self._translate_ontology_context(data)

    @staticmethod
    def _translate_ontology_context(data: dict[str, Any]) -> OntologyContext:
        """Synapse OntologyContextV1 → Oracle OntologyContext 변환."""
        term_mappings: list[TermMapping] = []
        for tm in data.get("term_mappings") or []:
            targets = [
                MappedTarget(table=t, columns=[])
                for t in (tm.get("tables") or [])
            ]
            term_mappings.append(TermMapping(
                term=tm.get("term", ""),
                matched_node=tm.get("matched_node", ""),
                layer=tm.get("layer", ""),
                confidence=float(tm.get("confidence", 0)),
                targets=targets,
            ))
        return OntologyContext(
            term_mappings=term_mappings,
            preferred_tables=data.get("preferred_tables") or [],
            preferred_columns=data.get("preferred_columns") or [],
        )

    # -- Schema Table Catalog ----------------------------------------------

    async def list_tables(self, tenant_id: str) -> list[TableInfo]:
        """Synapse 스키마 테이블 목록을 Oracle TableInfo로 변환."""
        response = await self._request_with_retry(
            "GET", f"{self._schema_edit_base}/tables", tenant_id=tenant_id
        )
        return self._translate_table_list(response)

    @staticmethod
    def _translate_table_list(response: dict[str, Any]) -> list[TableInfo]:
        rows = (response.get("data") or {}).get("tables") or []
        tables: list[TableInfo] = []
        for row in rows:
            name = str(row.get("name") or "").strip()
            if not name:
                continue
            tables.append(
                TableInfo(
                    name=name,
                    description=row.get("description"),
                    row_count=int(row.get("row_count", 0)),
                    has_embedding=bool(row.get("has_embedding", False)),
                )
            )
        return tables

    async def get_table_detail(self, tenant_id: str, table_name: str) -> TableInfo | None:
        """개별 테이블 상세 정보를 Oracle TableInfo로 변환."""
        response = await self._request_with_retry(
            "GET",
            f"{self._schema_edit_base}/tables/{table_name}",
            tenant_id=tenant_id,
        )
        return self._translate_table_detail(response, table_name)

    @staticmethod
    def _translate_table_detail(response: dict[str, Any], table_name: str) -> TableInfo | None:
        data = response.get("data") or {}
        columns: list[ColumnInfo] = []
        for col in data.get("columns") or []:
            col_name = str(col.get("name") or "").strip()
            if col_name:
                columns.append(
                    ColumnInfo(
                        name=col_name,
                        data_type=str(col.get("data_type", "varchar")),
                        description=col.get("description"),
                        is_key=col_name == "id",
                    )
                )
        if not columns:
            return None
        return TableInfo(
            name=table_name,
            columns=columns,
            description=data.get("description"),
            has_embedding=bool(data.get("has_embedding", False)),
        )

    # -- Schema Update Operations ------------------------------------------

    async def update_table_description(
        self, tenant_id: str, table_name: str, description: str
    ) -> SchemaUpdateResult:
        """테이블 설명 업데이트 결과를 Oracle 내부 모델로 변환."""
        response = await self._request_with_retry(
            "PUT",
            f"{self._schema_edit_base}/tables/{table_name}/description",
            tenant_id=tenant_id,
            json={"description": description},
        )
        data = response.get("data") or {}
        return SchemaUpdateResult(
            name=str(data.get("table_name", table_name)),
            description=str(data.get("description", description)),
            vector_updated=bool(data.get("embedding_updated", False)),
        )

    async def update_column_description(
        self,
        tenant_id: str,
        table_name: str,
        column_name: str,
        description: str,
    ) -> SchemaUpdateResult:
        """컬럼 설명 업데이트 결과를 Oracle 내부 모델로 변환."""
        response = await self._request_with_retry(
            "PUT",
            f"{self._schema_edit_base}/columns/{table_name}/{column_name}/description",
            tenant_id=tenant_id,
            json={"description": description},
        )
        data = response.get("data") or {}
        return SchemaUpdateResult(
            name=str(data.get("column_name", column_name)),
            description=str(data.get("description", description)),
            vector_updated=bool(data.get("embedding_updated", False)),
        )

    # -- Query Cache (Reflect) ---------------------------------------------

    async def reflect_cache(
        self,
        question: str,
        sql: str,
        confidence: float,
        datasource_id: str,
    ) -> None:
        """캐시 반영. Oracle은 결과를 사용하지 않으므로 변환 불필요."""
        payload = {
            "question": question or "",
            "sql": sql or "",
            "confidence": float(confidence),
            "datasource_id": datasource_id or "",
        }
        try:
            await self._request_with_retry(
                "POST",
                "/api/v3/synapse/graph/query-cache",
                json=payload,
            )
        except Exception as exc:
            logger.warning("synapse_acl_reflect_cache_failed", error=str(exc))

    # -- Value Mapping Operations (#13 P1-2) ------------------------------------

    async def save_value_mapping(
        self,
        natural_value: str,
        code_value: str,
        column_fqn: str,
        verified: bool = False,
        verified_confidence: float | None = None,
    ) -> None:
        """Neo4j :ValueMapping 노드를 MERGE한다 (Synapse 경유).

        자연어 값과 실제 DB 값의 매핑을 저장하여,
        향후 동일한 자연어 표현이 등장했을 때 재사용한다.
        """
        payload: dict[str, Any] = {
            "natural_value": natural_value or "",
            "code_value": code_value or "",
            "column_fqn": column_fqn or "",
            "verified": verified,
        }
        if verified_confidence is not None:
            payload["verified_confidence"] = float(verified_confidence)

        try:
            await self._request_with_retry(
                "POST",
                "/api/v3/synapse/graph/value-mapping",
                json=payload,
            )
        except Exception as exc:
            logger.warning("synapse_acl_save_value_mapping_failed", error=str(exc))

    async def find_value_mappings(
        self,
        term: str,
        tenant_id: str = "",
    ) -> list[dict[str, Any]]:
        """Neo4j :ValueMapping 노드에서 CONTAINS 검색한다.

        반환: [{natural_value, code_value, column_fqn, verified, usage_count}, ...]
        """
        try:
            response = await self._request_with_retry(
                "POST",
                "/api/v3/synapse/graph/value-mapping/search",
                tenant_id=tenant_id,
                json={"term": term},
            )
            data = response.get("data") or {}
            return data.get("mappings") or []
        except Exception as exc:
            logger.warning("synapse_acl_find_value_mappings_failed", error=str(exc))
            return []

    # -- Datasource Registry -----------------------------------------------

    def list_datasources(self) -> list[DatasourceInfo]:
        """로컬 설정에서 데이터소스 목록을 Oracle DatasourceInfo로 변환."""
        import json as _json

        try:
            raw_list = _json.loads(self._datasources_json)
            if not isinstance(raw_list, list):
                raw_list = []
        except _json.JSONDecodeError:
            logger.warning("invalid_datasource_registry_json")
            raw_list = []

        if not raw_list:
            logger.warning("no_datasources_configured", hint="Set ORACLE_DATASOURCES_JSON env var")

        return [
            DatasourceInfo(
                id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                type=str(item.get("type", "")),
                host=str(item.get("host", "")),
                database=str(item.get("database", "")),
                schema=str(item.get("schema", "public")),
                status=str(item.get("status", "active")),
            )
            for item in raw_list
            if isinstance(item, dict) and item.get("id")
        ]


    # -----------------------------------------------------------------
    # P3: 시멘틱 계약 컨텍스트 조회
    # -----------------------------------------------------------------

    async def fetch_semantic_contract_context(
        self, tenant_id: str, case_id: str | None = None,
    ) -> SemanticContractContext | None:
        """Synapse 시멘틱 계약 API에서 approved 컨텍스트를 가져온다.

        실패 시 None을 반환하여 기존 raw schema 경로로 폴백할 수 있도록 한다.
        """
        params: dict[str, str] = {}
        if case_id:
            params["case_id"] = case_id

        try:
            body = await self._request_with_retry(
                "GET", "/api/v3/synapse/semantic/ai-context",
                tenant_id=tenant_id, params=params,
            )
        except Exception as exc:
            logger.warning("semantic_contract_context_fetch_failed", error=str(exc))
            return None

        data = body.get("data") or {}
        if not data.get("measures") and not data.get("entities"):
            # 승인된 계약이 없으면 None → 폴백
            return None

        # 도메인 모델로 변환
        measures = [
            SemanticMeasureDef(
                measure_id=m.get("measure_id", ""),
                name=m.get("name", ""),
                description=m.get("description"),
                measure_type=m.get("measure_type", "sum"),
                sql_expression=m.get("sql_expression", ""),
                filter_expression=m.get("filter_expression"),
                additive_type=m.get("additive_type"),
                entity_id=m.get("entity_id", ""),
                bound_concept_id=m.get("bound_concept_id"),
            )
            for m in (data.get("measures") or [])
        ]

        dimensions = [
            SemanticDimensionDef(
                dimension_id=d.get("dimension_id", ""),
                name=d.get("name", ""),
                sql_expression=d.get("sql_expression", ""),
                value_type=d.get("value_type"),
                hierarchy_path=d.get("hierarchy_path"),
                entity_id=d.get("entity_id", ""),
            )
            for d in (data.get("dimensions") or [])
        ]

        allowed_joins = [
            SemanticJoinRule(
                join_id=j.get("join_id", ""),
                left_entity_id=j.get("left_entity_id", ""),
                right_entity_id=j.get("right_entity_id", ""),
                join_type=j.get("join_type", "LEFT"),
                join_condition=j.get("join_condition", ""),
                relationship_type=j.get("relationship_type", "1:N"),
                fanout_risk_score=float(j.get("fanout_risk_score") or 0),
            )
            for j in (data.get("allowed_joins") or [])
        ]

        banned = [
            (bj.get("left_entity_id", ""), bj.get("right_entity_id", ""))
            for bj in (data.get("banned_joins") or [])
        ]

        entity_sources = {
            e.get("entity_id", ""): e.get("physical_source_ref", "")
            for e in (data.get("entities") or [])
        }

        concept_defs = {
            c.get("concept_id", ""): c.get("business_definition") or c.get("name_ko", "")
            for c in (data.get("concepts") or [])
        }

        # 품질 경고: completeness_threshold < 90인 계약이 있으면 경고
        quality_warnings = []
        for q in (data.get("quality_contracts") or []):
            threshold = float(q.get("completeness_threshold") or 100)
            if threshold < 90:
                quality_warnings.append(
                    f"⚠ {q.get('target_type')} '{q.get('target_id')}'의 완전성 임계치가 낮습니다 ({threshold}%)"
                )

        return SemanticContractContext(
            measures=measures,
            dimensions=dimensions,
            allowed_joins=allowed_joins,
            banned_entity_pairs=banned,
            synonym_map=data.get("synonym_map") or {},
            concept_definitions=concept_defs,
            entity_sources=entity_sources,
            quality_warnings=quality_warnings,
        )

    # -----------------------------------------------------------------
    # P4: ContextPack resolve (의도별 AI 컨텍스트 프리셋)
    # -----------------------------------------------------------------

    async def resolve_context_pack(
        self, tenant_id: str, context_pack_id: str,
    ) -> ResolvedContextPack | None:
        """Synapse에서 ContextPack을 해석하여 Oracle 도메인 모델로 변환한다."""
        try:
            body = await self._request_with_retry(
                "GET", f"/api/v3/synapse/semantic/context-packs/{context_pack_id}/resolve",
                tenant_id=tenant_id,
            )
        except Exception as exc:
            logger.warning("context_pack_resolve_failed", error=str(exc), pack_id=context_pack_id)
            return None

        data = body.get("data") or {}
        if not data:
            return None

        # 시멘틱 객체 변환
        measures = [
            SemanticMeasureDef(
                measure_id=m.get("measure_id", ""), name=m.get("name", ""),
                description=m.get("description"), measure_type=m.get("measure_type", "sum"),
                sql_expression=m.get("sql_expression", ""),
                filter_expression=m.get("filter_expression"),
                additive_type=m.get("additive_type"), entity_id=m.get("entity_id", ""),
                bound_concept_id=m.get("bound_concept_id"),
            )
            for m in (data.get("measures") or [])
        ]
        dimensions = [
            SemanticDimensionDef(
                dimension_id=d.get("dimension_id", ""), name=d.get("name", ""),
                sql_expression=d.get("sql_expression", ""),
                value_type=d.get("value_type"), hierarchy_path=d.get("hierarchy_path"),
                entity_id=d.get("entity_id", ""),
            )
            for d in (data.get("dimensions") or [])
        ]
        allowed_joins = [
            SemanticJoinRule(
                join_id=j.get("join_id", ""), left_entity_id=j.get("left_entity_id", ""),
                right_entity_id=j.get("right_entity_id", ""),
                join_type=j.get("join_type", "LEFT"), join_condition=j.get("join_condition", ""),
                relationship_type=j.get("relationship_type", "1:N"),
                fanout_risk_score=float(j.get("fanout_risk_score") or 0),
            )
            for j in (data.get("allowed_joins") or [])
        ]
        banned = [
            (bj.get("left_entity_id", ""), bj.get("right_entity_id", ""))
            for bj in (data.get("banned_joins") or [])
        ]
        entity_sources = {}
        for e in (data.get("concepts") or []):
            # resolve 응답의 entities에서 physical_source_ref 추출
            pass
        # measures에서 entity_id → source 매핑 재구성 (resolve 응답에 entities가 직접 없을 수 있음)
        for m_data in (data.get("measures") or []):
            eid = m_data.get("entity_id", "")
            if eid and eid not in entity_sources:
                entity_sources[eid] = m_data.get("physical_source_ref", eid)

        semantic = SemanticContractContext(
            measures=measures,
            dimensions=dimensions,
            allowed_joins=allowed_joins,
            banned_entity_pairs=banned,
            synonym_map=data.get("synonym_map") or {},
            concept_definitions={},
            entity_sources=entity_sources,
        )

        # 프롬프트 정책 규칙 텍스트 (우선순위순)
        prompt_rules = [p.get("rule_text", "") for p in (data.get("prompt_policies") or [])]

        return ResolvedContextPack(
            context_pack_id=context_pack_id,
            intent_type=data.get("intent_type", "general"),
            semantic_context=semantic,
            prompt_rules=prompt_rules,
            answer_guardrails=data.get("answer_guardrails") or [],
            quality_gate_min_score=float(data.get("quality_gate_min_score") or 0),
        )

    async def find_context_pack_by_intent(
        self, tenant_id: str, intent_type: str, case_id: str | None = None,
    ) -> ResolvedContextPack | None:
        """의도 유형으로 ContextPack을 검색하여 첫 번째 매칭을 resolve한다."""
        try:
            params: dict[str, str] = {"intent_type": intent_type}
            if case_id:
                params["case_id"] = case_id
            body = await self._request_with_retry(
                "GET", "/api/v3/synapse/semantic/context-packs",
                tenant_id=tenant_id, params=params,
            )
        except Exception as exc:
            logger.warning("context_pack_search_failed", error=str(exc), intent=intent_type)
            return None

        packs = body.get("data") or []
        if not packs:
            return None
        # 첫 번째 매칭 팩을 resolve
        first_id = packs[0].get("context_pack_id")
        if not first_id:
            return None
        return await self.resolve_context_pack(tenant_id, first_id)


# Singleton
oracle_synapse_acl = OracleSynapseACL()
