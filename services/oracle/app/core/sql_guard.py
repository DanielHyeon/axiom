import sqlglot
from pydantic import BaseModel
from typing import List, Optional

class GuardResult(BaseModel):
    status: str
    sql: str
    violations: List[str] = []
    fixes: List[str] = []

class GuardConfig(BaseModel):
    dialect: str = "postgres"
    max_join_depth: int = 5
    max_subquery_depth: int = 3
    row_limit: int = 1000

class SQLGuard:
    FORBIDDEN_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT",
        "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME",
        "GRANT", "REVOKE",
        "SLEEP", "BENCHMARK", "LOAD_FILE", "INTO OUTFILE",
        "INTO DUMPFILE", "INFORMATION_SCHEMA",
        "EXEC", "EXECUTE", "xp_cmdshell", "sp_",
        "--", "/*", "*/"
    ]

    def _measure_subquery_depth(self, node: sqlglot.exp.Expression) -> int:
        depth = 0
        for child_node in node.find_all(sqlglot.exp.Subquery):
            if child_node is not node:
                depth = max(depth, self._measure_subquery_depth(child_node) + 1)
        if depth == 0 and any(isinstance(node, sqlglot.exp.Subquery) for _ in [1]):
            return 1
        return depth if not isinstance(node, sqlglot.exp.Subquery) else depth + 1

    def _measure_subquery_depth_simple(self, ast: sqlglot.exp.Expression) -> int:
        # Compatibility path for lightweight local sqlglot fallback.
        if hasattr(ast, "_subqueries"):
            return len(getattr(ast, "_subqueries") or [])

        # Simplified depth calculation: just looking at nested Selects mostly, 
        # but sqlglot provides find_all which traverses the entire tree.
        # Actually a simple list and check path if needed.
        # For simplicity in this mock wrapper, we will just count total Subqueries as a proxy for depth 
        # or do a basic recursive descent tracking depth.
        def walk(node, current_depth):
            max_d = current_depth
            if isinstance(node, sqlglot.exp.Subquery):
                current_depth += 1
                max_d = current_depth
            for k, v in node.args.items():
                if isinstance(v, list):
                    for child in v:
                        if isinstance(child, sqlglot.exp.Expression):
                            max_d = max(max_d, walk(child, current_depth))
                elif isinstance(v, sqlglot.exp.Expression):
                    max_d = max(max_d, walk(v, current_depth))
            return max_d
        return walk(ast, 0)

    def guard_sql(self, sql_query: str, config: Optional[GuardConfig] = None) -> GuardResult:
        if config is None:
            config = GuardConfig()
            
        sql_upper = sql_query.upper()
        found = []
        for keyword in self.FORBIDDEN_KEYWORDS:
            if keyword in sql_upper:
                # Basic context check: could improve by stripping strings/columns
                found.append(keyword)
                
        if found:
            return GuardResult(status="REJECT", sql=sql_query, violations=[f"금지 키워드 발견: {', '.join(found)}"])
            
        try:
            parsed = sqlglot.parse_one(sql_query, dialect=config.dialect)
            if not isinstance(parsed, sqlglot.exp.Select):
                return GuardResult(status="REJECT", sql=sql_query, violations=[f"SELECT 문만 허용됩니다. 감지된 유형: {type(parsed).__name__}"])
                
            joins = list(parsed.find_all(sqlglot.exp.Join))
            if len(joins) > config.max_join_depth:
                return GuardResult(status="REJECT", sql=sql_query, violations=[f"JOIN 깊이 초과: {len(joins)} > {config.max_join_depth}"])
                
            sq_depth = self._measure_subquery_depth_simple(parsed)
            if sq_depth > config.max_subquery_depth:
                return GuardResult(status="REJECT", sql=sql_query, violations=[f"서브쿼리 깊이 초과: {sq_depth} > {config.max_subquery_depth}"])
            
            # Layer 4 auto fix
            fixes = []
            fixed_ast = parsed.copy()
            if not fixed_ast.args.get("limit"):
                # Missing limit
                fixed_ast = fixed_ast.limit(config.row_limit)
                fixes.append(f"LIMIT {config.row_limit} 자동 추가")
                
            fixed_sql = fixed_ast.sql(dialect=config.dialect)
            if fixes:
                return GuardResult(status="FIX", sql=fixed_sql, fixes=fixes)
                
            return GuardResult(status="PASS", sql=fixed_sql)
            
        except tuple([sqlglot.errors.ParseError, sqlglot.errors.TokenError]) as e:
            return GuardResult(status="REJECT", sql=sql_query, violations=[f"SQL 파싱 실패: {str(e)}"])

sql_guard = SQLGuard()
