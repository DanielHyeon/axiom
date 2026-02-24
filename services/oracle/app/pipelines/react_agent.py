import json
from typing import AsyncGenerator, Dict, Any, List

import structlog
from pydantic import BaseModel

from app.core.auth import CurrentUser
from app.core.llm_factory import llm_factory
from app.core.sql_guard import GuardConfig, sql_guard
from app.core.sql_exec import sql_executor
from app.infrastructure.acl.synapse_acl import oracle_synapse_acl
from app.core.visualize import recommend_visualization

logger = structlog.get_logger()


class TriageDecision(BaseModel):
    action: str  # COMPLETE | CONTINUE | FAIL
    next_question: str = ""
    reason: str = ""


class ValidateResult(BaseModel):
    passed: bool
    sql: str = ""
    next_step: str = ""
    violations: List[str] = []
    fixes: List[str] = []


class ReactSession(BaseModel):
    question: str
    datasource_id: str
    case_id: str | None = None  # O3: ontology context
    options: Dict[str, Any]
    max_iterations: int = 5
    current_iteration: int = 0
    status: str = "running"


def _step_line(step: str, iteration: int, data: Dict[str, Any]) -> str:
    return json.dumps({"step": step, "iteration": iteration, "data": data}) + "\n"


def _error_step(iteration: int, code: str, message: str) -> str:
    return _step_line("error", iteration, {"code": code, "message": message})


class ReactAgent:
    """6-step loop: Select (graph) -> Generate -> Validate -> Fix -> Execute -> Quality -> Triage; COMPLETE -> step result."""

    async def _select_tables(
        self, question: str, tenant_id: str, case_id: str | None = None,
    ) -> tuple[list[str], str]:
        """ACL을 통한 테이블 선택. O3: ontology context 우선, fallback to graph search / schema catalog."""
        # O3: ontology context 우선
        if case_id:
            try:
                ctx = await oracle_synapse_acl.search_ontology_context(
                    case_id=case_id, query=question, tenant_id=tenant_id,
                )
                if ctx and ctx.preferred_tables:
                    return ctx.preferred_tables, "온톨로지 기반 테이블 선택"
            except Exception as exc:
                logger.warning("react_ontology_fallback", reason=str(exc))
        # Existing: graph search fallback
        try:
            search_result = await oracle_synapse_acl.search_schema_context(
                query=question, tenant_id=tenant_id
            )
            if search_result.tables:
                names = [t.name for t in search_result.tables]
                return list(dict.fromkeys(names)), "그래프 검색으로 관련 테이블 선택"
        except Exception as exc:
            logger.warning("react_select_search_fallback", reason=str(exc))
        try:
            tables = await oracle_synapse_acl.list_tables(tenant_id=tenant_id)
            names = [t.name for t in tables if t.name]
            if names:
                return names, "스키마 테이블 목록 기반"
        except Exception:
            pass
        return ["sales_records"], "기본 테이블 사용"

    async def run_step_validate(self, sql: str, row_limit: int) -> ValidateResult:
        res = sql_guard.guard_sql(sql, GuardConfig(row_limit=row_limit))
        if res.status == "REJECT":
            return ValidateResult(passed=False, next_step="fix", violations=res.violations)
        return ValidateResult(passed=True, sql=res.sql, fixes=res.fixes)

    async def run_step_quality(self, question: str, sql: str) -> Dict[str, Any]:
        prompt = f"Assess quality of: {question} \nSQL: {sql}"
        system = "당신은 SQL 결과 품질 심사관입니다."
        res = await llm_factory.generate(prompt, system_prompt=system)
        try:
            return json.loads(res)
        except Exception:
            return {"score": 0.5, "is_complete": False, "reason": "Failed to parse json."}

    async def run_step_triage(
        self, quality_result: Dict[str, Any], iteration: int, max_iterations: int
    ) -> TriageDecision:
        score = quality_result.get("score", 0.0)
        is_complete = quality_result.get("is_complete", False)
        if is_complete and score >= 0.8:
            return TriageDecision(action="COMPLETE")
        if iteration >= max_iterations:
            return TriageDecision(action="FAIL", reason=f"최대 반복 횟수({max_iterations})에 도달했습니다")
        if score < 0.5:
            return TriageDecision(action="FAIL", reason="결과 품질이 기준에 미달합니다")
        return TriageDecision(action="CONTINUE", next_question=quality_result.get("next_question", ""))

    async def stream_react_loop(
        self, session: ReactSession, user: CurrentUser | None = None
    ) -> AsyncGenerator[str, None]:
        row_limit = session.options.get("row_limit", 1000)
        tenant_id = str(user.tenant_id) if user else ""
        dialect = session.options.get("dialect", "postgres")

        try:
            for iteration in range(1, session.max_iterations + 1):
                session.current_iteration = iteration

                # Step 1: Select (O3: ontology → graph → schema → fallback)
                table_names, reasoning = await self._select_tables(session.question, tenant_id, session.case_id)
                yield _step_line("select", iteration, {"tables": table_names, "reasoning": reasoning})

                # Step 2: Generate
                gen_prompt = f"Generate a single SELECT SQL for: {session.question}. Use tables: {table_names}. Add LIMIT {row_limit}."
                sql = await llm_factory.generate(gen_prompt)
                sql = (sql or "").strip()
                if sql.startswith("```"):
                    for line in sql.split("\n"):
                        if "SELECT" in line.upper():
                            sql = line.strip().strip("`")
                            break
                if not sql:
                    sql = "SELECT 1"
                yield _step_line("generate", iteration, {"sql": sql, "reasoning": ""})

                # Step 3: Validate
                val_res = await self.run_step_validate(sql, row_limit)
                if not val_res.passed:
                    yield _step_line(
                        "validate", iteration, {"status": "FAIL", "violations": val_res.violations}
                    )
                    fixed_sql = await llm_factory.generate(f"Fix this SQL based on: {val_res.violations}")
                    fixed_sql = (fixed_sql or "").strip() or sql
                    val_res = await self.run_step_validate(fixed_sql, row_limit)
                    yield _step_line(
                        "fix",
                        iteration,
                        {"original_sql": sql, "fixed_sql": val_res.sql, "fixes": val_res.fixes},
                    )
                    if not val_res.passed:
                        yield _step_line(
                            "triage", iteration, {"action": "fail", "reason": "Fix loop failed repeatedly"}
                        )
                        yield _error_step(iteration, "SQL_GUARD_REJECT", "SQL 수정 후에도 검증을 통과하지 못했습니다.")
                        return
                    yield _step_line("validate", iteration, {"status": "PASS", "sql": val_res.sql, "fixes": val_res.fixes})
                else:
                    yield _step_line("validate", iteration, {"status": "PASS", "sql": val_res.sql, "fixes": val_res.fixes})

                # Step 4: Execute (real)
                exec_res = await sql_executor.execute_sql(val_res.sql, session.datasource_id, user)
                preview = (exec_res.rows or [])[:10]
                yield _step_line(
                    "execute",
                    iteration,
                    {"row_count": exec_res.row_count, "preview": preview},
                )

                # Step 5: Quality
                qual = await self.run_step_quality(session.question, val_res.sql)
                yield _step_line(
                    "quality",
                    iteration,
                    {"score": qual.get("score"), "feedback": qual.get("feedback", "")},
                )

                # Step 6: Triage
                triage = await self.run_step_triage(qual, iteration, session.max_iterations)
                triage_data = triage.model_dump()
                triage_data["action"] = triage_data.get("action", "complete").lower()
                yield _step_line("triage", iteration, triage_data)

                if triage.action == "COMPLETE":
                    session.status = "completed"
                    # Step: result (O2-3)
                    col_dicts = [{"name": c, "type": "varchar"} for c in exec_res.columns]
                    viz = recommend_visualization(
                        col_dicts, exec_res.rows or [], exec_res.row_count
                    )
                    summary = ""
                    try:
                        summary = await llm_factory.generate(
                            f"Summarize in one sentence: columns {exec_res.columns}, first row: {preview[:1]}",
                            temperature=0.3,
                        )
                        summary = (summary or "").strip()[:500]
                    except Exception:
                        pass
                    yield _step_line(
                        "result",
                        iteration,
                        {
                            "sql": val_res.sql,
                            "result": exec_res.model_dump(),
                            "summary": summary,
                            "visualization": viz,
                        },
                    )
                    return
                if triage.action == "FAIL":
                    session.status = "failed"
                    yield _error_step(
                        iteration,
                        "MAX_ITERATIONS" if iteration >= session.max_iterations else "QUALITY_FAIL",
                        triage.reason or "ReAct 실패",
                    )
                    return

                session.question = triage.next_question or session.question

            yield _error_step(
                session.current_iteration,
                "MAX_ITERATIONS",
                f"최대 반복 횟수({session.max_iterations})에 도달했습니다.",
            )
        except Exception as exc:
            logger.exception("react_loop_error", error=str(exc))
            yield _error_step(
                session.current_iteration or 1,
                "SQL_EXECUTION_ERROR",
                str(exc)[:500] or "ReAct 루프 중 오류 발생",
            )


react_agent = ReactAgent()
