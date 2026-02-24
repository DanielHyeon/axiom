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


# Singleton
oracle_synapse_acl = OracleSynapseACL()
