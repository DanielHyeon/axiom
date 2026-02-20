# MindsDB HTTP 클라이언트 상세

<!-- affects: backend, api -->
<!-- requires-update: 02_api/query-api.md -->

## 이 문서가 답하는 질문

- MindsDB HTTP API와 어떻게 통신하는가?
- 타임아웃, 재시도, 에러 처리는 어떻게 하는가?
- 어떤 MindsDB API 엔드포인트를 사용하는가?
- K-AIR의 mindsdb_service.py (308줄)에서 무엇을 이식하는가?

---

## 1. K-AIR 원본 분석

K-AIR의 `backend/app/services/mindsdb_service.py` (308줄)에서 이식하는 핵심 기능:

| K-AIR 메서드 | Weaver 대응 | 설명 |
|-------------|------------|------|
| `execute_query(sql)` | `query(sql)` | SQL 실행 |
| `check_connection()` | `health_check()` | MindsDB 상태 확인 |
| `get_databases()` | `list_databases()` | 등록된 DB 목록 |
| `get_tables(db)` | `list_tables(db)` | 테이블 목록 |
| `get_table_schema(db, table)` | `get_schema(db, table)` | 테이블 스키마 |
| `create_database(...)` | `create_database(...)` | DB 등록 |
| `drop_database(name)` | `drop_database(name)` | DB 삭제 |

---

## 2. 클라이언트 구현

```python
# app/mindsdb/client.py
import httpx
import logging
from typing import Optional, Any
from app.core.errors import MindsDBUnavailableError, QueryTimeoutError

logger = logging.getLogger(__name__)


class MindsDBClient:
    """MindsDB HTTP API Client

    MindsDB의 /api/sql/query 엔드포인트를 통해 SQL을 실행한다.
    모든 MindsDB 통신은 이 클라이언트를 통해서만 이루어진다.

    K-AIR 원본: backend/app/services/mindsdb_service.py (308줄)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:47334",
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_endpoint = "/api/sql/query"
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─── Core Query Execution ─────────────────────────────

    async def query(self, sql: str, database: Optional[str] = None) -> dict:
        """Execute SQL query via MindsDB HTTP API

        Args:
            sql: SQL query string
            database: Optional default database context

        Returns:
            dict with keys: columns, data, row_count

        Raises:
            MindsDBUnavailableError: MindsDB server unreachable
            QueryTimeoutError: Query exceeded timeout
        """
        payload = {"query": sql}
        if database:
            payload["context"] = {"db": database}

        try:
            response = await self.client.post(
                self.api_endpoint,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            # MindsDB returns different formats depending on query type
            if "data" in result:
                return {
                    "columns": result.get("column_names", []),
                    "data": result.get("data", []),
                    "row_count": len(result.get("data", [])),
                }
            elif "error" in result:
                raise Exception(result["error"])
            else:
                return {"columns": [], "data": [], "row_count": 0}

        except httpx.ConnectError:
            logger.error(f"Cannot connect to MindsDB at {self.base_url}")
            raise MindsDBUnavailableError()
        except httpx.TimeoutException:
            logger.warning(f"Query timed out after {self.timeout}s: {sql[:100]}...")
            raise QueryTimeoutError(self.timeout)
        except httpx.HTTPStatusError as e:
            logger.error(f"MindsDB HTTP error {e.response.status_code}: {e.response.text[:200]}")
            raise

    # ─── Database Management ──────────────────────────────

    async def create_database(
        self,
        name: str,
        engine: str,
        parameters: dict,
    ) -> bool:
        """Register a new database in MindsDB

        Executes: CREATE DATABASE {name} ENGINE = '{engine}' PARAMETERS = {params}
        """
        # Build parameter string
        params_str = ", ".join(
            f'"{k}" = "{v}"' if isinstance(v, str) else f'"{k}" = {v}'
            for k, v in parameters.items()
        )

        sql = f"""
            CREATE DATABASE `{name}`
            ENGINE = '{engine}'
            PARAMETERS = (
                {params_str}
            )
        """

        logger.info(f"Creating MindsDB database: {name} (engine={engine})")
        await self.query(sql)
        return True

    async def drop_database(self, name: str) -> bool:
        """Remove a database from MindsDB

        Executes: DROP DATABASE {name}
        """
        sql = f"DROP DATABASE `{name}`"
        logger.info(f"Dropping MindsDB database: {name}")
        await self.query(sql)
        return True

    async def list_databases(self) -> list[dict]:
        """List all registered databases in MindsDB

        Executes: SHOW DATABASES
        """
        result = await self.query("SHOW DATABASES")
        return [
            {"name": row[0], "engine": row[1] if len(row) > 1 else None}
            for row in result.get("data", [])
        ]

    async def database_exists(self, name: str) -> bool:
        """Check if a database exists in MindsDB"""
        databases = await self.list_databases()
        return any(db["name"] == name for db in databases)

    # ─── Table Operations ─────────────────────────────────

    async def list_tables(self, database: str) -> list[str]:
        """List tables in a specific database

        Executes: SHOW TABLES FROM {database}
        """
        result = await self.query(f"SHOW TABLES FROM `{database}`")
        return [row[0] for row in result.get("data", [])]

    async def get_table_schema(self, database: str, table: str) -> list[dict]:
        """Get table schema (columns info)

        Executes: DESCRIBE {database}.{table}
        """
        result = await self.query(f"DESCRIBE `{database}`.`{table}`")
        columns = result.get("columns", [])
        data = result.get("data", [])
        return [dict(zip(columns, row)) for row in data]

    # ─── ML Models ────────────────────────────────────────

    async def list_models(self) -> list[dict]:
        """List all ML models

        Executes: SHOW MODELS
        """
        result = await self.query("SHOW MODELS")
        columns = result.get("columns", [])
        data = result.get("data", [])
        return [dict(zip(columns, row)) for row in data]

    # ─── Jobs ─────────────────────────────────────────────

    async def list_jobs(self) -> list[dict]:
        """List all scheduled jobs

        Executes: SHOW JOBS
        """
        result = await self.query("SHOW JOBS")
        columns = result.get("columns", [])
        data = result.get("data", [])
        return [dict(zip(columns, row)) for row in data]

    # ─── Knowledge Bases ──────────────────────────────────

    async def list_knowledge_bases(self) -> list[dict]:
        """List all knowledge bases

        Executes: SHOW KNOWLEDGE_BASES
        """
        result = await self.query("SHOW KNOWLEDGE_BASES")
        columns = result.get("columns", [])
        data = result.get("data", [])
        return [dict(zip(columns, row)) for row in data]

    # ─── Materialized Tables ──────────────────────────────

    async def create_materialized_table(
        self,
        table_name: str,
        sql: str,
        database: str = "mindsdb",
        replace: bool = False,
    ) -> dict:
        """Create a materialized table from query results

        Executes: CREATE TABLE {database}.{table_name} (SELECT ...)
        """
        if replace:
            try:
                await self.query(f"DROP TABLE IF EXISTS `{database}`.`{table_name}`")
            except Exception:
                pass  # Table might not exist

        create_sql = f"CREATE TABLE `{database}`.`{table_name}` ({sql})"
        await self.query(create_sql)

        # Get row count
        count_result = await self.query(
            f"SELECT COUNT(*) as cnt FROM `{database}`.`{table_name}`"
        )
        row_count = count_result["data"][0][0] if count_result["data"] else 0

        return {
            "table_name": table_name,
            "database": database,
            "row_count": row_count,
        }

    # ─── Health Check ─────────────────────────────────────

    async def health_check(self) -> dict:
        """Check MindsDB server status

        Executes: SELECT 1
        """
        import time
        start = time.monotonic()

        try:
            await self.query("SELECT 1")
            elapsed = int((time.monotonic() - start) * 1000)

            databases = await self.list_databases()
            models = await self.list_models()

            return {
                "status": "healthy",
                "response_time_ms": elapsed,
                "databases_count": len(databases),
                "models_count": len(models),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }
```

---

## 3. MindsDB HTTP API 참조

| 엔드포인트 | 메서드 | 용도 |
|-----------|--------|------|
| `/api/sql/query` | POST | SQL 쿼리 실행 (핵심) |
| `/api/status` | GET | 서버 상태 |

### /api/sql/query 요청 형식

```json
{
  "query": "SELECT * FROM erp_db.public.processes LIMIT 10",
  "context": {
    "db": "mindsdb"
  }
}
```

### /api/sql/query 응답 형식

```json
{
  "column_names": ["id", "process_code", "org_name"],
  "data": [
    [1, "PROC-2026-001", "주식회사 가나다"],
    [2, "PROC-2026-002", "주식회사 라마바"]
  ],
  "type": "table"
}
```

---

## 4. 에러 시나리오

| 시나리오 | MindsDB 응답 | Weaver 처리 |
|---------|-------------|------------|
| SQL 문법 오류 | `{"error": "syntax error..."}` | 400 `INVALID_SQL` |
| 존재하지 않는 DB | `{"error": "unknown database..."}` | 404 `DATABASE_NOT_FOUND` |
| 연결 타임아웃 | httpx.TimeoutException | 408 `QUERY_TIMEOUT` |
| MindsDB 다운 | httpx.ConnectError | 503 `MINDSDB_UNAVAILABLE` |
| HTTP 5xx | httpx.HTTPStatusError | 502 `MINDSDB_ERROR` |

---

## 5. 성능 고려사항

| 항목 | 설정 | 근거 |
|------|------|------|
| HTTP 커넥션 풀 | httpx.AsyncClient (재사용) | 매 요청마다 연결 생성 방지 |
| 커넥트 타임아웃 | 10초 | MindsDB 시작 대기 |
| 쿼리 타임아웃 | 120초 | 대규모 크로스 DB 쿼리 허용 |
| 재시도 | 없음 | 멱등성 보장 불가 (INSERT 가능) |
| 로깅 | SQL 처음 100자만 | 쿼리 전체 로깅은 성능 저하 |

---

## 6. 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/architecture-overview.md` | MindsDB 통합 아키텍처 |
| `01_architecture/data-fabric.md` | 데이터 패브릭 설계 |
| `02_api/query-api.md` | 쿼리 실행 API 스펙 |
| `08_operations/deployment.md` | MindsDB 배포 설정 |
| `99_decisions/ADR-001-mindsdb-gateway.md` | MindsDB 선택 근거 |
