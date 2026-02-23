from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
import asyncio

from app.core.auth import CurrentUser
from app.core.llm_factory import llm_factory
from app.core.sql_exec import sql_executor
from app.core.sql_guard import GuardConfig, sql_guard
from app.core.synapse_client import synapse_client
from app.core.visualize import recommend_visualization
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


class NL2SQLPipeline:
    _FALLBACK_SCHEMAS = {
        "processes": ["id", "org_id", "status", "started_at", "completed_at", "duration_seconds", "amount"],
        "organizations": ["id", "name", "region", "industry", "risk_level"],
        "event_logs": ["id", "event_type", "occurred_at", "severity", "case_id"],
    }

    async def _load_schema_catalog(self, tenant_id: str) -> tuple[list[TableSchema], str]:
        catalog: list[TableSchema] = []
        schema_source = "fallback"
        try:
            payload = await synapse_client.list_schema_tables(tenant_id=tenant_id)
            rows = payload.get("data", {}).get("tables", [])
            schema_source = "synapse"
        except Exception:
            rows = []
        for item in rows:
            table_name = str(item.get("name") or "").strip()
            if not table_name:
                continue
            try:
                detail = await synapse_client.get_schema_table(tenant_id=tenant_id, table_name=table_name)
                cols = [
                    str(col.get("name") or "").strip()
                    for col in detail.get("data", {}).get("columns", [])
                    if str(col.get("name") or "").strip()
                ]
            except Exception:
                cols = []
            if cols:
                catalog.append(TableSchema(name=table_name, columns=cols))
        if catalog:
            return catalog, schema_source
        return [TableSchema(name=name, columns=cols) for name, cols in self._FALLBACK_SCHEMAS.items()], "fallback"

    def _schema_from_search_result(self, data: dict[str, Any]) -> list[TableSchema]:
        catalog: list[TableSchema] = []
        tables = data.get("tables") or {}
        vector_matched = tables.get("vector_matched") or []
        fk_related = tables.get("fk_related") or []
        seen = set()
        for t in vector_matched:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            cols = []
            for c in t.get("columns") or []:
                if isinstance(c, dict) and c.get("name"):
                    cols.append(str(c["name"]).strip())
            if not cols:
                cols = ["id", "name"]
            catalog.append(TableSchema(name=name, columns=cols))
        for t in fk_related:
            if not isinstance(t, dict):
                continue
            name = str(t.get("name") or "").strip()
            if not name or name in seen:
                continue
            seen.add(name)
            raw_cols = t.get("columns")
            if isinstance(raw_cols, list) and raw_cols:
                cols = [str(c.get("name", c) if isinstance(c, dict) else c).strip() for c in raw_cols if c]
            else:
                cols = ["id", "name"]
            catalog.append(TableSchema(name=name, columns=cols or ["id", "name"]))
        return catalog

    def _format_schema_ddl(self, schemas: list[TableSchema], value_mappings: list[Any], similar_queries: list[Any]) -> str:
        lines = []
        for s in schemas:
            cols = ", ".join(f"{c} VARCHAR" for c in s.columns)
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
    ) -> tuple[list[TableSchema], str, list[Any], list[Any]]:
        value_mappings: list[Any] = []
        similar_queries: list[Any] = []
        try:
            context: dict[str, Any] = {}
            if question_vector:
                context["question_vector"] = question_vector
            search_data = await synapse_client.search_graph(question, context=context, tenant_id=tenant_id)
            if isinstance(search_data, dict):
                vector_matched = (search_data.get("tables") or {}).get("vector_matched") or []
                if vector_matched:
                    catalog = self._schema_from_search_result(search_data)
                    value_mappings = search_data.get("value_mappings") or []
                    similar_queries = search_data.get("similar_queries") or []
                    return catalog, "synapse_graph", value_mappings, similar_queries
        except Exception:
            pass
        catalog, source = await self._load_schema_catalog(tenant_id=tenant_id)
        return catalog, source, value_mappings, similar_queries

    async def _generate_sql_llm(
        self,
        question: str,
        schemas: list[TableSchema],
        value_mappings: list[Any],
        similar_queries: list[Any],
        row_limit: int,
        dialect: str,
    ) -> str:
        schema_ddl = self._format_schema_ddl(schemas, value_mappings, similar_queries)
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

        # 2. Graph search + schema catalog (O1-2)
        schema_catalog, schema_source, value_mappings, similar_queries = await self._search_and_catalog(
            question, question_vector, tenant_id, datasource_id
        )
        if not schema_catalog:
            return {
                "success": False,
                "error": {"code": "NO_SCHEMA", "message": "No schema available for this datasource."},
            }

        # 3. Schema formatting done in _format_schema_ddl
        # 4. LLM SQL generation (O1-3)
        generated_sql = await self._generate_sql_llm(
            question, schema_catalog, value_mappings, similar_queries, row_limit, dialect
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
            # 이벤트 루프 미존재 등으로 인한 비동기 태스크 실패는 응답에는 영향 주지 않음.
            pass

        return {
            "success": True,
            "data": {
                "question": question,
                "sql": guard_res.sql,
                "result": exec_res.model_dump(),
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
