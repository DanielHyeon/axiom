from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
import asyncio

from app.core.auth import CurrentUser
from app.core.llm_factory import llm_factory
from app.core.sql_exec import sql_executor
from app.core.sql_guard import GuardConfig, sql_guard
from app.core.visualize import recommend_visualization
from app.infrastructure.acl.synapse_acl import oracle_synapse_acl, TableInfo, OntologyContext
from app.pipelines.cache_postprocess import cache_postprocessor


@dataclass
class TableSchema:
    name: str
    columns: list[str]


_SQL_SYSTEM_PROMPT = """You are a {dialect} SQL expert. Generate exactly one SELECT statement from the given schema and question.
Rules:
1. Use only SELECT (no INSERT/UPDATE/DELETE).
2. Add LIMIT {row_limit} to the query.
3. Use table and column names exactly as in the schema. Use AS for aliases.
4. Use explicit casts for date filters.
5. Include GROUP BY when using aggregates.
"""


def _table_info_to_schema(t: TableInfo) -> TableSchema:
    """ACL TableInfo → pipeline TableSchema 변환."""
    cols = [c.name for c in t.columns] if t.columns else ["id", "name"]
    return TableSchema(name=t.name, columns=cols)


class NL2SQLPipeline:
    _FALLBACK_SCHEMAS = {
        "sales": [
            "id", "company_name", "department", "sale_date",
            "product_category", "revenue", "cost", "quantity", "region",
        ],
        "operations": [
            "id", "case_ref", "operation_type", "started_at",
            "completed_at", "duration_minutes", "status", "region", "operator_name",
        ],
    }

    async def _load_schema_catalog(self, tenant_id: str) -> tuple[list[TableSchema], str]:
        """ACL을 통해 스키마 카탈로그 로드."""
        catalog: list[TableSchema] = []
        schema_source = "fallback"
        try:
            tables = await oracle_synapse_acl.list_tables(tenant_id=tenant_id)
            schema_source = "synapse"
        except Exception:
            tables = []
        for table_info in tables:
            try:
                detail = await oracle_synapse_acl.get_table_detail(
                    tenant_id=tenant_id, table_name=table_info.name
                )
                if detail and detail.columns:
                    catalog.append(_table_info_to_schema(detail))
            except Exception:
                pass
        if catalog:
            return catalog, schema_source
        return [TableSchema(name=name, columns=cols) for name, cols in self._FALLBACK_SCHEMAS.items()], "fallback"

    _COLUMN_TYPE_HINTS: dict[str, str] = {
        "id": "SERIAL PRIMARY KEY",
        "sale_date": "DATE",
        "started_at": "TIMESTAMP",
        "completed_at": "TIMESTAMP",
        "revenue": "NUMERIC(15,2)",
        "cost": "NUMERIC(15,2)",
        "quantity": "INTEGER",
        "duration_minutes": "NUMERIC(10,2)",
    }

    def _format_schema_ddl(self, schemas: list[TableSchema], value_mappings: list[Any], similar_queries: list[Any]) -> str:
        lines = []
        for s in schemas:
            col_defs = []
            for c in s.columns:
                ctype = self._COLUMN_TYPE_HINTS.get(c, "VARCHAR")
                col_defs.append(f"{c} {ctype}")
            cols = ", ".join(col_defs)
            lines.append(f"CREATE TABLE {s.name} ({cols});")
        ddl = "\n".join(lines)
        if value_mappings:
            ddl += "\n\nValue mappings (natural language -> DB value):\n" + str(value_mappings)[:500]
        if similar_queries:
            ddl += "\n\nSimilar cached queries (reference only):\n" + str(similar_queries)[:500]
        return ddl

    async def _search_and_catalog(
        self,
        question: str,
        question_vector: list[float],
        tenant_id: str,
        datasource_id: str,
        case_id: str | None = None,
    ) -> tuple[list[TableSchema], str, list[Any], list[Any], OntologyContext | None]:
        """ACL을 통해 그래프 검색 + 스키마 카탈로그 + 온톨로지 컨텍스트 수행."""
        value_mappings: list[Any] = []
        similar_queries: list[Any] = []
        try:
            context: dict[str, Any] = {}
            if question_vector:
                context["question_vector"] = question_vector
            search_result = await oracle_synapse_acl.search_schema_context(
                query=question, tenant_id=tenant_id, context=context
            )
            if search_result.tables:
                catalog = [_table_info_to_schema(t) for t in search_result.tables]
                value_mappings = [
                    {"natural_language": vm.natural_language, "db_value": vm.db_value,
                     "column": vm.column, "table": vm.table}
                    for vm in search_result.value_mappings
                ]
                similar_queries = [
                    {"question": cq.question, "sql": cq.sql, "confidence": cq.confidence}
                    for cq in search_result.cached_queries
                ]
                # O3: ontology context
                ontology_ctx = await self._fetch_ontology_context(case_id, question, tenant_id)
                return catalog, "synapse_graph", value_mappings, similar_queries, ontology_ctx
        except Exception:
            pass
        catalog, source = await self._load_schema_catalog(tenant_id=tenant_id)
        ontology_ctx = await self._fetch_ontology_context(case_id, question, tenant_id)
        return catalog, source, value_mappings, similar_queries, ontology_ctx

    @staticmethod
    async def _fetch_ontology_context(
        case_id: str | None, question: str, tenant_id: str,
    ) -> OntologyContext | None:
        """O3: ontology context 조회. 실패 시 None (degraded mode)."""
        if not case_id:
            return None
        try:
            return await oracle_synapse_acl.search_ontology_context(
                case_id=case_id, query=question, tenant_id=tenant_id,
            )
        except Exception:
            return None

    @staticmethod
    def _format_ontology_context_for_prompt(ctx: OntologyContext | None) -> str:
        """O3: 온톨로지 컨텍스트를 LLM 프롬프트용 텍스트로 변환 (confidence 3-tier)."""
        if not ctx or not ctx.term_mappings:
            return ""
        lines = ["\n## Ontology Context (domain knowledge)"]
        for tm in ctx.term_mappings:
            if tm.confidence >= 0.8:
                tag = "[Confirmed]"
            elif tm.confidence >= 0.6:
                tag = "[Reference]"
            else:
                tag = "[Low Confidence]"
            tables_str = ", ".join(t.table for t in tm.targets) if tm.targets else "N/A"
            lines.append(f"- {tag} \"{tm.term}\" -> {tm.matched_node} ({tm.layer}) -> tables: {tables_str}")
        if ctx.preferred_tables:
            lines.append(f"\nPreferred tables: {', '.join(ctx.preferred_tables)}")
        return "\n".join(lines)

    async def _generate_sql_llm(
        self,
        question: str,
        schemas: list[TableSchema],
        value_mappings: list[Any],
        similar_queries: list[Any],
        row_limit: int,
        dialect: str,
        ontology_ctx: OntologyContext | None = None,
    ) -> str:
        schema_ddl = self._format_schema_ddl(schemas, value_mappings, similar_queries)
        # O3: ontology context 주입
        ontology_section = self._format_ontology_context_for_prompt(ontology_ctx)
        if ontology_section:
            schema_ddl += ontology_section
        system = _SQL_SYSTEM_PROMPT.format(dialect=dialect, row_limit=row_limit)
        user_prompt = f"Schema:\n{schema_ddl}\n\nQuestion: {question}\n\nGenerate a single SELECT SQL statement only, no explanation."
        out = await llm_factory.generate(user_prompt, system_prompt=system, temperature=0.1)
        sql = (out or "").strip()
        if sql.startswith("```"):
            for line in sql.split("\n"):
                if line.strip().startswith("SELECT"):
                    sql = line.strip()
                    break
                if line.strip() == "```":
                    continue
                sql = line.strip()
        return sql or "SELECT 1"

    async def execute(
        self,
        question: str,
        datasource_id: str,
        options: dict | None = None,
        user: CurrentUser | None = None,
        case_id: str | None = None,
    ) -> Dict[str, Any]:
        options = options or {}
        row_limit = options.get("row_limit", 1000)
        dialect = options.get("dialect", "postgres")
        include_viz = options.get("include_viz", True)

        tenant_id = str(user.tenant_id) if user else ""

        # 1. Embed (O1-1)
        question_vector: list[float] = []
        try:
            question_vector = await llm_factory.embed(question)
        except Exception:
            pass

        # 2. Graph search + schema catalog + ontology context (O1-2 + O3)
        schema_catalog, schema_source, value_mappings, similar_queries, ontology_ctx = await self._search_and_catalog(
            question, question_vector, tenant_id, datasource_id, case_id=case_id,
        )
        if not schema_catalog:
            return {
                "success": False,
                "error": {"code": "NO_SCHEMA", "message": "No schema available for this datasource."},
            }

        # 3. Schema formatting done in _format_schema_ddl
        # 4. LLM SQL generation (O1-3 + O3 ontology injection)
        generated_sql = await self._generate_sql_llm(
            question, schema_catalog, value_mappings, similar_queries, row_limit, dialect,
            ontology_ctx=ontology_ctx,
        )

        # 5. Guard
        guard_cfg = GuardConfig(row_limit=row_limit, dialect=dialect)
        guard_res = sql_guard.guard_sql(generated_sql, guard_cfg)
        if guard_res.status == "REJECT":
            return {
                "success": False,
                "error": {
                    "code": "SQL_GUARD_REJECT",
                    "details": {"violations": guard_res.violations},
                },
            }

        # 6. Execute
        exec_res = await sql_executor.execute_sql(guard_res.sql, datasource_id, user)

        # 7. Visualization (O1-4)
        visualization = None
        if include_viz and exec_res.rows is not None:
            col_dicts = [{"name": c, "type": "varchar"} for c in exec_res.columns]
            visualization = recommend_visualization(col_dicts, exec_res.rows, exec_res.row_count)

        # 8. Summary (O1-5, optional)
        summary = None
        try:
            if exec_res.row_count > 0 and exec_res.rows:
                summary_prompt = f"Summarize this query result in one short sentence (Korean or English). Columns: {exec_res.columns}. First row: {exec_res.rows[0]}."
                summary = await llm_factory.generate(summary_prompt, temperature=0.3)
                summary = (summary or "").strip()[:500]
        except Exception:
            pass

        tables_used = [s.name for s in schema_catalog]

        # 9. Cache/quality gate (O4, fire-and-forget)
        try:
            preview_rows = exec_res.rows[:10] if exec_res.rows else []
            asyncio.create_task(
                cache_postprocessor.process(
                    question=question,
                    sql=guard_res.sql,
                    result_preview=preview_rows,
                    datasource_id=datasource_id,
                    tenant_id=tenant_id,
                )
            )
        except RuntimeError:
            pass

        result_dict = exec_res.model_dump()
        result_dict["columns"] = [{"name": c, "type": "varchar"} for c in exec_res.columns]

        return {
            "success": True,
            "data": {
                "question": question,
                "sql": guard_res.sql,
                "result": result_dict,
                "visualization": visualization,
                "summary": summary,
                "metadata": {
                    "execution_time_ms": exec_res.execution_time_ms,
                    "execution_backend": exec_res.backend,
                    "guard_status": guard_res.status,
                    "guard_fixes": guard_res.fixes,
                    "schema_source": schema_source,
                    "tables_used": tables_used,
                },
            },
        }


nl2sql_pipeline = NL2SQLPipeline()
