import json
import asyncio
from typing import AsyncGenerator, Dict, Any, List
from pydantic import BaseModel
import structlog
from app.core.llm_factory import llm_factory
from app.core.sql_guard import sql_guard, GuardConfig

logger = structlog.get_logger()

class TriageDecision(BaseModel):
    action: str # COMPLETE | CONTINUE | FAIL
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
    options: Dict[str, Any]
    max_iterations: int = 5
    current_iteration: int = 0
    status: str = "running"

from app.core.auth import CurrentUser

class ReactAgent:
    """Implement the 6-step loop: Select -> Generate -> Validate -> Fix -> Quality -> Triage"""
    
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
        except:
            return {"score": 0.5, "is_complete": False, "reason": "Failed to parse json."}

    async def run_step_triage(self, quality_result: Dict[str, Any], iteration: int, max_iterations: int) -> TriageDecision:
        score = quality_result.get("score", 0.0)
        is_complete = quality_result.get("is_complete", False)
        
        if is_complete and score >= 0.8:
            return TriageDecision(action="COMPLETE")
        if iteration >= max_iterations:
            return TriageDecision(action="FAIL", reason=f"최대 반복 횟수({max_iterations})에 도달했습니다")
        if score < 0.5:
            return TriageDecision(action="FAIL", reason="결과 품질이 기준에 미달합니다")
            
        return TriageDecision(action="CONTINUE", next_question=quality_result.get("next_question", ""))

    async def stream_react_loop(self, session: ReactSession, user: CurrentUser = None) -> AsyncGenerator[str, None]:
        row_limit = session.options.get("row_limit", 1000)
        
        for iteration in range(1, session.max_iterations + 1):
            session.current_iteration = iteration
            
            # Step 1: Select
            yield json.dumps({"step": "select", "iteration": iteration, "data": {"tables": ["sales_records"]}}) + "\n"
            
            # Step 2: Generate
            gen_prompt = f"Generate SQL for {session.question}"
            sql = await llm_factory.generate(gen_prompt)
            yield json.dumps({"step": "generate", "iteration": iteration, "data": {"sql": sql}}) + "\n"
            
            # Step 3: Validate
            val_res = await self.run_step_validate(sql, row_limit)
            if not val_res.passed:
                yield json.dumps({"step": "validate", "iteration": iteration, "data": {"passed": False, "violations": val_res.violations}}) + "\n"
                
                # Step 4: Fix (Max 3 retries in Validate-Fix loop simulated securely)
                fixed_sql = await llm_factory.generate(f"Fix this SQL based on {val_res.violations}")
                val_res = await self.run_step_validate(fixed_sql, row_limit)
                yield json.dumps({"step": "fix", "iteration": iteration, "data": {"passed": val_res.passed}}) + "\n"

                if not val_res.passed:
                    yield json.dumps({"step": "triage", "iteration": iteration, "data": {"action": "FAIL", "reason": "Fix loop failed repeatedly"}}) + "\n"
                    break
            else:
                yield json.dumps({"step": "validate", "iteration": iteration, "data": {"passed": True, "fixes": val_res.fixes}}) + "\n"
                
            # Simulate mocked execution
            # Step 5: Quality
            qual = await self.run_step_quality(session.question, val_res.sql)
            yield json.dumps({"step": "quality", "iteration": iteration, "data": {"score": qual.get("score")}}) + "\n"
            
            # Step 6: Triage
            triage = await self.run_step_triage(qual, iteration, session.max_iterations)
            yield json.dumps({"step": "triage", "iteration": iteration, "data": triage.model_dump()}) + "\n"
            
            if triage.action == "COMPLETE":
                session.status = "completed"
                break
            elif triage.action == "FAIL":
                session.status = "failed"
                break
            
            # If CONTINUE, loop processes next step naturally
            session.question = triage.next_question

react_agent = ReactAgent()
