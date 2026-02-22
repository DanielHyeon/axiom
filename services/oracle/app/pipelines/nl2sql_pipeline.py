from app.core.synapse_client import synapse_client
from app.core.sql_guard import sql_guard, GuardConfig
from app.core.sql_exec import sql_executor
from app.core.auth import CurrentUser
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class TableSchema:
    name: str
    columns: list[str]


class NL2SQLPipeline:
    _FALLBACK_SCHEMAS = {
        "processes": ["id", "org_id", "status", "started_at", "completed_at", "duration_seconds", "amount"],
        "organizations": ["id", "name", "region", "industry", "risk_level"],
        "event_logs": ["id", "event_type", "occurred_at", "severity", "case_id"],
    }

    async def _load_schema_catalog(self, tenant_id: str) -> list[TableSchema]:
        catalog: list[TableSchema] = []
        try:
            payload = await synapse_client.list_schema_tables(tenant_id=tenant_id)
            rows = payload.get("data", {}).get("tables", [])
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
            return catalog
        return [TableSchema(name=name, columns=cols) for name, cols in self._FALLBACK_SCHEMAS.items()]

    @staticmethod
    def _match_table(question_lower: str, tables: list[TableSchema]) -> TableSchema:
        for table in tables:
            singular = table.name[:-1] if table.name.endswith("s") else table.name
            if table.name.lower() in question_lower or singular.lower() in question_lower:
                return table
        return tables[0]

    @staticmethod
    def _select_projection(question_lower: str, table: TableSchema) -> str:
        if "count" in question_lower or "몇" in question_lower or "개수" in question_lower:
            return "COUNT(*) AS total_count"
        selected = [c for c in table.columns if c.lower() in question_lower]
        if not selected:
            priority = ["id", "name", "status", "amount", "duration_seconds", "started_at", "completed_at", "event_type"]
            selected = [c for c in priority if c in table.columns]
        if not selected:
            selected = table.columns[: min(4, len(table.columns))]
        return ", ".join(selected)

    @staticmethod
    def _build_where(question_lower: str, table: TableSchema) -> str:
        conditions: list[str] = []
        if "status" in table.columns:
            if "failed" in question_lower or "실패" in question_lower:
                conditions.append("status = 'FAILED'")
            elif "success" in question_lower or "성공" in question_lower:
                conditions.append("status = 'SUCCESS'")
        if "severity" in table.columns:
            if "critical" in question_lower:
                conditions.append("severity = 'critical'")
            elif "warning" in question_lower:
                conditions.append("severity = 'warning'")
        if "risk_level" in table.columns and ("high risk" in question_lower or "고위험" in question_lower):
            conditions.append("risk_level = 'HIGH'")
        if not conditions:
            return ""
        return " WHERE " + " AND ".join(conditions)

    def _generate_sql(self, question: str, schemas: list[TableSchema]) -> str:
        question_lower = question.lower().strip()
        target_table = self._match_table(question_lower, schemas)
        projection = self._select_projection(question_lower, target_table)
        where_clause = self._build_where(question_lower, target_table)
        order_clause = ""
        if projection.startswith("COUNT("):
            order_clause = ""
        elif "started_at" in target_table.columns and any(k in question_lower for k in ["recent", "latest", "최근", "최신"]):
            order_clause = " ORDER BY started_at DESC"
        return f"SELECT {projection} FROM {target_table.name}{where_clause}{order_clause}"

    async def execute(self, question: str, datasource_id: str, options: dict = None, user: CurrentUser = None) -> Dict[str, Any]:
        options = options or {}
        row_limit = options.get("row_limit", 1000)
        dialect = options.get("dialect", "postgres")

        tenant_id = str(user.tenant_id) if user else ""
        schema_catalog = await self._load_schema_catalog(tenant_id=tenant_id)
        generated_sql = self._generate_sql(question, schema_catalog)

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
                    "guard_fixes": guard_res.fixes,
                    "schema_source": "synapse_or_fallback",
                },
            },
        }

nl2sql_pipeline = NL2SQLPipeline()
