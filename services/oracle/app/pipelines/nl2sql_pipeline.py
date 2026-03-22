"""NL2SQL 파이프라인: 자연어 질문을 SQL로 변환하고 실행한다.

주요 단계:
1. 질문 벡터화 (임베딩)
2. 그래프 검색 + 스키마 카탈로그 + 온톨로지 컨텍스트
2.5. Value Mapping (#13 P1-2): 자연어 값 -> DB 값 매핑
3. LLM SQL 생성
4. SQL Guard 검증
5. SQL 실행
6. 품질 게이트 심사 + 캐시 저장 + Value Mapping 학습
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import uuid4

import httpx

from app.core.auth import CurrentUser
from app.core.config import settings
from app.core.llm_factory import llm_factory
from app.core.sql_exec import sql_executor
from app.core.sql_guard import GuardConfig, sql_guard
from app.core.value_mapping import value_mapping_service
from app.core.visualize import recommend_visualization
from app.infrastructure.acl.synapse_acl import oracle_synapse_acl, TableInfo, OntologyContext, SemanticContractContext, ResolvedContextPack
from app.pipelines.cache_postprocess import cache_postprocessor

logger = logging.getLogger("oracle.nl2sql_pipeline")

# Semaphore caps concurrent insight forwarding calls (E8 fix)
_INSIGHT_SEMAPHORE = asyncio.Semaphore(10)


async def _forward_to_insight(
    tenant_id: str,
    sql: str,
    datasource: str,
    duration_ms: int,
    row_count: int | None,
    nl_query: str | None,
    trace_id: str,
) -> None:
    """Fire-and-forget: POST executed SQL to Weaver /api/insight/logs (P1-B)."""
    if not settings.WEAVER_INSIGHT_TOKEN:
        return  # forwarding disabled

    entry = {
        "request_id": str(uuid4()),
        "trace_id": trace_id,
        "datasource_id": datasource,
        "dialect": "postgresql",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "duration_ms": duration_ms,
        "row_count": row_count,
        "nl_query": nl_query,
        "raw_sql": sql,
    }

    async with _INSIGHT_SEMAPHORE:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(
                    settings.WEAVER_INSIGHT_URL,
                    json={"logs": [entry], "source": "oracle-nl2sql"},
                    headers={
                        "Authorization": f"Bearer {settings.WEAVER_INSIGHT_TOKEN}",
                        "X-Tenant-Id": tenant_id,
                        "X-Source": "oracle-nl2sql",
                    },
                )
        except Exception as exc:
            # Sample 10% of failures to avoid log spam (E8)
            if random.random() < 0.1:
                logger.warning("insight_forward_failed: %s", exc)


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
    """ACL TableInfo -> pipeline TableSchema 변환."""
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

    @staticmethod
    def _classify_intent(question: str) -> str:
        """간단한 키워드 기반 의도 분류 (향후 LLM 기반으로 교체 가능)"""
        q = question.lower()
        # 한국어 + 영어 키워드 매핑
        if any(kw in q for kw in ("원인", "왜", "root cause", "why", "이유")):
            return "root_cause"
        if any(kw in q for kw in ("추세", "변화", "trend", "변동", "시계열")):
            return "trend"
        if any(kw in q for kw in ("비교", "대비", "compare", "vs", "차이")):
            return "comparison"
        if any(kw in q for kw in ("예측", "전망", "forecast", "predict")):
            return "forecast_support"
        if any(kw in q for kw in ("이상", "비정상", "anomaly", "outlier")):
            return "anomaly"
        if any(kw in q for kw in ("세그먼트", "그룹", "segment", "분류")):
            return "segment"
        if any(kw in q for kw in ("kpi", "지표", "metric", "성과", "실적")):
            return "kpi_query"
        return "general"

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

    @staticmethod
    def _sanitize_prompt_fragment(value: str, max_len: int = 500) -> str:
        """프롬프트 주입 방어 — SQL 코멘트, 제어문자, 과도한 길이 제거."""
        import re
        if not value:
            return ""
        # SQL 코멘트 제거 (-- ... 줄끝, /* ... */)
        cleaned = re.sub(r"--[^\n]*", "", value)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        # 줄바꿈/탭 → 공백 (프롬프트 구조 깨짐 방지)
        cleaned = cleaned.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        # 연속 공백 정리
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:max_len]

    @staticmethod
    def _format_semantic_contract_for_prompt(ctx: SemanticContractContext | None) -> str:
        """P3: 시멘틱 계약 컨텍스트를 LLM 프롬프트용 텍스트로 변환.

        raw DDL 대신, 승인된 지표/차원/조인 규칙을 제공한다.
        LLM은 이 정의를 그대로 사용하여 SQL을 생성해야 한다.
        """
        if not ctx or (not ctx.measures and not ctx.dimensions):
            return ""

        _s = NL2SQLPipeline._sanitize_prompt_fragment
        # 최대 항목 수 제한 (토큰 예산 관리)
        _MAX_MEASURES = 50
        _MAX_DIMS = 30
        _MAX_JOINS = 20

        lines = ["\n## Semantic Layer (approved metric definitions — USE THESE)"]

        # 동의어 맵
        if ctx.synonym_map:
            lines.append("\n### Synonym Map (user term → concept ID)")
            for term, cid in list(ctx.synonym_map.items())[:30]:
                safe_term = _s(term, 100)
                lines.append(f"  - \"{safe_term}\" → {_s(cid, 100)}")

        # 지표 정의
        if ctx.measures:
            lines.append("\n### Approved Metrics (MUST use these SQL expressions)")
            for m in ctx.measures[:_MAX_MEASURES]:
                source = _s(ctx.entity_sources.get(m.entity_id, "UNKNOWN"), 200)
                desc = f" — {_s(m.description or '', 200)}" if m.description else ""
                expr = _s(m.sql_expression, 500)
                lines.append(f"  - {_s(m.name, 100)} [{m.measure_type}]: {expr} FROM {source}{desc}")
                if m.filter_expression:
                    lines.append(f"    WHERE {_s(m.filter_expression, 500)}")

        # 차원 정의
        if ctx.dimensions:
            lines.append("\n### Approved Dimensions")
            for d in ctx.dimensions[:_MAX_DIMS]:
                lines.append(f"  - {_s(d.name, 100)} [{d.value_type or 'any'}]: {_s(d.sql_expression, 300)}")
                if d.hierarchy_path:
                    lines.append(f"    hierarchy: {_s(d.hierarchy_path, 100)}")

        # 조인 규칙
        if ctx.allowed_joins:
            lines.append("\n### Allowed Joins (ONLY use these join paths)")
            for j in ctx.allowed_joins[:_MAX_JOINS]:
                left_src = _s(ctx.entity_sources.get(j.left_entity_id, j.left_entity_id), 200)
                right_src = _s(ctx.entity_sources.get(j.right_entity_id, j.right_entity_id), 200)
                risk = f" [fanout_risk={j.fanout_risk_score}]" if j.fanout_risk_score >= 0.5 else ""
                lines.append(f"  - {left_src} {j.join_type} JOIN {right_src} ON {_s(j.join_condition, 300)}{risk}")

        if ctx.banned_entity_pairs:
            lines.append("\n### FORBIDDEN Joins (NEVER join these)")
            for left, right in ctx.banned_entity_pairs[:_MAX_JOINS]:
                lines.append(f"  - {_s(left, 100)} ✗ {_s(right, 100)}")

        # 품질 경고
        if ctx.quality_warnings:
            lines.append("\n### Quality Warnings")
            for w in ctx.quality_warnings[:10]:
                lines.append(f"  {_s(w, 200)}")

        return "\n".join(lines)

    @staticmethod
    def _format_prompt_policies(pack: ResolvedContextPack | None) -> str:
        """P4: ContextPack의 프롬프트 정책 + 응답 가드레일을 프롬프트 텍스트로 변환."""
        if not pack:
            return ""
        _s = NL2SQLPipeline._sanitize_prompt_fragment
        lines: list[str] = []

        if pack.prompt_rules:
            lines.append("\n## Prompt Policies (MANDATORY rules for this query)")
            for rule in pack.prompt_rules[:20]:
                lines.append(f"  - {_s(rule, 300)}")

        if pack.answer_guardrails:
            lines.append("\n## Answer Guardrails")
            for g in pack.answer_guardrails[:10]:
                lines.append(f"  - {_s(g, 300)}")

        if pack.quality_gate_min_score > 0:
            lines.append(f"\n## Quality Gate: minimum score = {pack.quality_gate_min_score}")

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
        semantic_ctx: SemanticContractContext | None = None,
        context_pack: ResolvedContextPack | None = None,
    ) -> str:
        schema_ddl = self._format_schema_ddl(schemas, value_mappings, similar_queries)
        # P4: ContextPack이 있으면 해당 시멘틱 컨텍스트를 우선 사용
        effective_semantic = context_pack.semantic_context if context_pack else semantic_ctx
        semantic_section = self._format_semantic_contract_for_prompt(effective_semantic)
        if semantic_section:
            schema_ddl += semantic_section
        # P4: 프롬프트 정책 주입
        policy_section = self._format_prompt_policies(context_pack)
        if policy_section:
            schema_ddl += policy_section
        # O3: ontology context 주입 (보조)
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

        # 2.5 Value Mapping 활성화 (#13 P1-2): 자연어 값을 실제 DB 값으로 매핑
        resolved_values = []
        if settings.ENABLE_VALUE_MAPPING:
            try:
                resolved_values = await value_mapping_service.resolve_values(
                    question=question,
                    datasource_id=datasource_id,
                    tenant_id=tenant_id,
                    schema_catalog=schema_catalog,
                )
                # 해석된 값을 value_mappings에 병합
                for rv in resolved_values:
                    value_mappings.append({
                        "natural_language": rv.user_term,
                        "db_value": rv.actual_value,
                        "column": rv.column_fqn.split(".")[-1] if rv.column_fqn else "",
                        "table": rv.column_fqn.split(".")[-2] if "." in (rv.column_fqn or "") else "",
                    })
            except Exception as exc:
                logger.warning("value_mapping_resolve_failed", error=str(exc))

        # 3. P3: 시멘틱 계약 컨텍스트 조회 (approved 지표/차원/조인 정의)
        semantic_ctx: SemanticContractContext | None = None
        try:
            semantic_ctx = await oracle_synapse_acl.fetch_semantic_contract_context(
                tenant_id=tenant_id, case_id=case_id,
            )
            if semantic_ctx:
                logger.info("semantic_contract_context_loaded",
                            measures=len(semantic_ctx.measures),
                            dimensions=len(semantic_ctx.dimensions),
                            joins=len(semantic_ctx.allowed_joins))
        except Exception as exc:
            logger.warning("semantic_contract_context_failed", error=str(exc))

        # 3.5 P4: 의도별 ContextPack 조회 (있으면 semantic_ctx보다 우선)
        context_pack: ResolvedContextPack | None = None
        try:
            # 간단한 의도 분류: 질문 키워드 기반 (향후 LLM 기반으로 교체 가능)
            intent = self._classify_intent(question)
            if intent != "general":
                context_pack = await oracle_synapse_acl.find_context_pack_by_intent(
                    tenant_id=tenant_id, intent_type=intent, case_id=case_id,
                )
                if context_pack:
                    logger.info("context_pack_resolved", pack_id=context_pack.context_pack_id, intent=intent)
        except Exception as exc:
            logger.warning("context_pack_resolve_failed", error=str(exc))

        # 4. LLM SQL generation (O1-3 + O3 ontology + P3/P4 semantic context)
        generated_sql = await self._generate_sql_llm(
            question, schema_catalog, value_mappings, similar_queries, row_limit, dialect,
            ontology_ctx=ontology_ctx,
            semantic_ctx=semantic_ctx,
            context_pack=context_pack,
        )

        # 4.5 SQL 리터럴 검증 (#13 P1-2): WHERE 절의 값이 실제 DB 값과 일치하는지 확인
        if settings.ENABLE_VALUE_MAPPING:
            try:
                value_hints = self._build_value_hints(schema_catalog)
                mismatches = value_mapping_service.validate_sql_literals(generated_sql, value_hints)
                if mismatches:
                    logger.warning("sql_literal_mismatch_detected", mismatches=mismatches)
            except Exception:
                pass

        # 5. Guard
        # 테이블 화이트리스트 적용 — 스키마 카탈로그에 있는 테이블만 허용
        table_names = [s.name for s in schema_catalog] if schema_catalog else None
        guard_cfg = GuardConfig(row_limit=row_limit, dialect=dialect, allowed_tables=table_names)
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

        # 9. Cache/quality gate (O4, fire-and-forget) + Value Mapping 학습 (#13)
        try:
            preview_rows = exec_res.rows[:10] if exec_res.rows else []
            asyncio.create_task(
                self._postprocess_and_learn(
                    question=question,
                    sql=guard_res.sql,
                    result_preview=preview_rows,
                    datasource_id=datasource_id,
                    tenant_id=tenant_id,
                    resolved_values=resolved_values,
                    preview_columns=exec_res.columns,
                    execution_time_ms=exec_res.execution_time_ms,
                )
            )
        except RuntimeError:
            pass

        # 10. Insight log forwarding (P1-B, fire-and-forget)
        try:
            asyncio.create_task(
                _forward_to_insight(
                    tenant_id=tenant_id,
                    sql=guard_res.sql,
                    datasource=datasource_id,
                    duration_ms=exec_res.execution_time_ms or 0,
                    row_count=exec_res.row_count,
                    nl_query=question,
                    trace_id=str(uuid4()),
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
                    # P3: 시멘틱 계약 컨텍스트 사용 여부 + 품질 경고
                    "semantic_context_used": semantic_ctx is not None or context_pack is not None,
                    "quality_warnings": (
                        (semantic_ctx.quality_warnings if semantic_ctx else [])
                        + (context_pack.answer_guardrails if context_pack else [])
                    ) or [],
                    "intent_type": context_pack.intent_type if context_pack else None,
                },
            },
        }

    @staticmethod
    def _build_value_hints(schema_catalog: list[TableSchema]) -> dict[str, set[str]]:
        """스키마 카탈로그에서 enum 힌트를 value_hints 형태로 변환한다.

        반환: {column_name_lower: {allowed_value_lower, ...}}
        향후 enum_cache_bootstrap과 통합하여 실제 enum 값을 활용할 수 있다.
        """
        hints: dict[str, set[str]] = {}
        # 현재는 간단한 빈 힌트 반환 (enum_cache_bootstrap 연동은 향후 구현)
        return hints

    async def _postprocess_and_learn(
        self,
        question: str,
        sql: str,
        result_preview: list,
        datasource_id: str,
        tenant_id: str,
        resolved_values: list,
        preview_columns: list[str] | None = None,
        execution_time_ms: int | None = None,
    ) -> None:
        """품질 게이트 심사 후, APPROVE되면 Value Mapping을 학습한다.

        fire-and-forget으로 실행된다.
        """
        try:
            # 품질 게이트 심사 + 캐시 저장
            decision = await cache_postprocessor.process(
                question=question,
                sql=sql,
                result_preview=result_preview,
                datasource_id=datasource_id,
                tenant_id=tenant_id,
                execution_time_ms=float(execution_time_ms) if execution_time_ms else None,
                preview_columns=preview_columns,
            )

            # APPROVE 시 Value Mapping 학습 (#13)
            if decision.status == "APPROVE" and resolved_values and settings.ENABLE_VALUE_MAPPING:
                for rv in resolved_values:
                    try:
                        await value_mapping_service.save_learned_mapping(
                            natural_value=rv.user_term,
                            db_value=rv.actual_value,
                            column_fqn=rv.column_fqn,
                            verified=True,
                            confidence=decision.confidence,
                        )
                    except Exception as exc:
                        logger.debug("value_mapping_learn_failed", error=str(exc))

        except Exception as exc:
            logger.warning("postprocess_and_learn_failed", error=str(exc))


nl2sql_pipeline = NL2SQLPipeline()
