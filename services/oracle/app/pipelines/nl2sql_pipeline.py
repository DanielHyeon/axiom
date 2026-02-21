from app.core.synapse_client import synapse_client
from app.core.sql_guard import sql_guard, GuardConfig
from app.core.sql_exec import sql_executor
from app.core.auth import CurrentUser
from typing import Dict, Any

class NL2SQLPipeline:
    async def execute(self, question: str, datasource_id: str, options: dict = None, user: CurrentUser = None) -> Dict[str, Any]:
        options = options or {}
        row_limit = options.get("row_limit", 1000)
        dialect = options.get("dialect", "postgres")
        
        # Inject Tenant for isolated Synapse Graph Searches securely
        tenant_id = str(user.tenant_id) if user else ""
        schema = await synapse_client.search_graph("mock-query", tenant_id=tenant_id)
        
        # Base generated sql mock
        generated_sql = f"SELECT * FROM sales_records"
        
        guard_cfg = GuardConfig(row_limit=row_limit, dialect=dialect)
        guard_res = sql_guard.guard_sql(generated_sql, guard_cfg)
        
        if guard_res.status == "REJECT":
            return {
                "success": False,
                "error": {
                    "code": "SQL_GUARD_REJECT",
                    "details": {"violations": guard_res.violations}
                }
            }
            
        # Execute natively after the validated results
        exec_res = await sql_executor.execute_sql(guard_res.sql, datasource_id, user)
        
        return {
            "success": True,
            "data": {
                "question": question,
                "sql": guard_res.sql,
                "result": exec_res.model_dump(),
                "metadata": {
                    "execution_time_ms": exec_res.execution_time_ms, 
                    "guard_status": guard_res.status,
                    "guard_fixes": guard_res.fixes
                }
            }
        }

nl2sql_pipeline = NL2SQLPipeline()
