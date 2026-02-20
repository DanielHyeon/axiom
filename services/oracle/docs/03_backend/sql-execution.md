# SQL 실행 엔진

## 이 문서가 답하는 질문

- SQL 실행 시 어떤 DB 드라이버를 사용하는가?
- 커넥션 풀은 어떻게 관리되는가?
- 타임아웃과 행 제한은 어떻게 동작하는가?
- 실행 에러는 어떻게 처리되는가?

<!-- affects: 02_api, 07_security -->
<!-- requires-update: 08_operations/deployment.md -->

---

## 1. 모듈 개요

`sql_exec.py`는 K-AIR에서 380줄로 구현된 모듈로, SQL Guard를 통과한 SELECT 쿼리를 대상 데이터베이스에서 비동기로 실행하고 결과를 반환한다.

---

## 2. 지원 데이터베이스

| DB | 드라이버 | 프로토콜 | 비고 |
|----|---------|---------|------|
| PostgreSQL | `asyncpg` | TCP :5432 | 주력 지원 (비즈니스 DB) |
| MySQL | `aiomysql` | TCP :3306 | K-AIR 호환성 유지 |

### 2.1 드라이버 선택 근거

| 기준 | asyncpg | psycopg2 |
|------|---------|----------|
| 비동기 | 네이티브 async | 래퍼 필요 |
| 성능 | 3-5배 빠름 | 기준 |
| 바이너리 프로토콜 | 지원 | 지원 |
| 선택 | **채택** | 미사용 |

---

## 3. 커넥션 풀 관리

```python
# sql_exec.py 기반
class SQLExecutor:
    """비동기 SQL 실행기."""

    def __init__(self, config: OracleSettings):
        self._pools: dict[str, asyncpg.Pool] = {}
        self._config = config

    async def _get_pool(self, datasource: DataSource) -> asyncpg.Pool:
        """
        데이터소스별 커넥션 풀 생성/재사용.
        Lazy initialization: 첫 요청 시 풀 생성.
        """
        pool_key = datasource.id
        if pool_key not in self._pools:
            if datasource.type == "postgresql":
                self._pools[pool_key] = await asyncpg.create_pool(
                    dsn=datasource.connection_string,
                    min_size=2,         # 최소 커넥션
                    max_size=10,        # 최대 커넥션
                    max_inactive_connection_lifetime=300,  # 5분 유휴 해제
                    command_timeout=self._config.sql_timeout,
                )
            elif datasource.type == "mysql":
                self._pools[pool_key] = await aiomysql.create_pool(
                    host=datasource.host,
                    port=datasource.port,
                    user=datasource.user,
                    password=datasource.password,
                    db=datasource.database,
                    minsize=2,
                    maxsize=10,
                )
        return self._pools[pool_key]

    async def close_all(self):
        """모든 커넥션 풀 종료. 서버 shutdown 시 호출."""
        for pool in self._pools.values():
            await pool.close()
        self._pools.clear()
```

### 3.1 커넥션 풀 설정

| 설정 | 값 | 근거 |
|------|-----|------|
| `min_size` | 2 | 유휴 시에도 기본 커넥션 유지 |
| `max_size` | 10 | 동시 쿼리 수 제한 (DB 부하 방지) |
| `max_inactive_lifetime` | 300초 | 5분 유휴 커넥션 자동 해제 |
| `command_timeout` | 30초 | SQL 실행 타임아웃 |

---

## 4. SQL 실행 흐름

```python
async def execute_sql(
    self,
    sql: str,
    datasource: DataSource,
    timeout: int | None = None,
    max_rows: int | None = None
) -> ExecutionResult:
    """
    SQL 실행 전체 흐름.

    1. 커넥션 풀에서 커넥션 획득
    2. statement_timeout 설정 (PostgreSQL)
    3. SQL 실행
    4. 결과 행 제한 (max_rows)
    5. 컬럼 메타데이터 추출
    6. 커넥션 반환
    """
    timeout = timeout or self._config.sql_timeout
    max_rows = max_rows or self._config.max_rows

    pool = await self._get_pool(datasource)

    async with pool.acquire() as conn:
        try:
            # PostgreSQL: statement_timeout 설정
            if datasource.type == "postgresql":
                await conn.execute(
                    f"SET statement_timeout = '{timeout * 1000}'"
                )

            # SQL 실행
            rows = await conn.fetch(sql)

            # 행 수 제한
            total_count = len(rows)
            truncated = total_count > max_rows
            if truncated:
                rows = rows[:max_rows]

            # 컬럼 메타데이터 추출
            columns = []
            if rows:
                columns = [
                    ColumnMeta(
                        name=key,
                        type=_pg_type_to_str(rows[0][key])
                    )
                    for key in rows[0].keys()
                ]

            return ExecutionResult(
                columns=columns,
                rows=[list(row.values()) for row in rows],
                row_count=total_count,
                truncated=truncated,
                execution_time_ms=_elapsed_ms()
            )

        except asyncpg.QueryCanceledError:
            raise SQLTimeoutError(
                f"SQL 실행이 {timeout}초를 초과했습니다"
            )
        except asyncpg.PostgresError as e:
            raise SQLExecutionError(
                f"SQL 실행 에러: {e.message}"
            )
        finally:
            # statement_timeout 리셋
            if datasource.type == "postgresql":
                await conn.execute("RESET statement_timeout")
```

---

## 5. 타임아웃 전략

### 5.1 계층별 타임아웃

```
┌───────────────────────────────────────────────────────┐
│  API 레벨 타임아웃 (60초)                              │
│  ┌─────────────────────────────────────────────────┐  │
│  │  SQL 실행 타임아웃 (30초)                        │  │
│  │  ┌───────────────────────────────────────────┐  │  │
│  │  │  DB statement_timeout (30초)               │  │  │
│  │  │  PostgreSQL이 직접 취소                     │  │  │
│  │  └───────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────┘
```

| 계층 | 타임아웃 | 동작 |
|------|---------|------|
| API | 60초 | uvicorn/nginx 레벨에서 요청 종료 |
| SQL 실행 | 30초 | asyncpg command_timeout |
| DB statement | 30초 | PostgreSQL이 쿼리 취소 |

### 5.2 MySQL 타임아웃

```python
# MySQL은 statement_timeout이 없으므로 다른 전략 사용
if datasource.type == "mysql":
    # aiomysql에서 읽기 타임아웃 설정
    await conn.execute(
        f"SET SESSION MAX_EXECUTION_TIME={timeout * 1000}"
    )
```

---

## 6. 행 제한 전략

```
SQL 실행 결과
    │
    ├─ 행 수 <= row_limit (1000) → 전체 반환
    │
    ├─ row_limit < 행 수 <= max_rows (10000) → 잘라서 반환 (truncated=true)
    │
    └─ 행 수 > max_rows (10000) → DB 레벨에서 잘림 (LIMIT 자동 추가)
```

| 제한 | 값 | 적용 위치 |
|------|-----|----------|
| `row_limit` | 1,000 | API 응답 행 수 제한 |
| `max_rows` | 10,000 | 메모리 보호 (DB에서 가져오는 최대 행) |
| SQL LIMIT | Guard가 추가 | SQL 자체에 LIMIT 포함 |

---

## 7. 에러 처리

### 7.1 에러 분류

| asyncpg 예외 | Oracle 예외 | 사용자 메시지 |
|-------------|------------|-------------|
| `QueryCanceledError` | `SQLTimeoutError` | "쿼리 실행 시간 초과" |
| `UndefinedTableError` | `SQLExecutionError` | "테이블을 찾을 수 없습니다" |
| `UndefinedColumnError` | `SQLExecutionError` | "컬럼을 찾을 수 없습니다" |
| `SyntaxOrAccessRuleViolation` | `SQLExecutionError` | "SQL 문법 오류" |
| `InsufficientPrivilegeError` | `SQLExecutionError` | "데이터 접근 권한 없음" |
| `ConnectionDoesNotExistError` | `SQLExecutionError` | "DB 연결 실패" |

### 7.2 재시도 전략

```python
# 커넥션 에러만 재시도 (쿼리 에러는 재시도 무의미)
RETRYABLE_ERRORS = (
    asyncpg.ConnectionDoesNotExistError,
    asyncpg.InterfaceError,
    ConnectionRefusedError,
)

MAX_RETRIES = 2
RETRY_DELAY = 1.0  # 초
```

---

## 8. 보안 고려사항

| 항목 | 전략 |
|------|------|
| SQL 인젝션 | SQL Guard에서 사전 차단 (이 모듈은 2차 방어) |
| 커넥션 문자열 | 환경 변수로만 전달, 로그에 노출 금지 |
| 결과 데이터 | `sql-safety.md` §7.2 정책에 따라 역할 기반 동적 마스킹 적용 |
| READ-ONLY | Target DB 계정은 SELECT 권한만 부여 |

---

## 관련 문서

- [01_architecture/sql-guard.md](../01_architecture/sql-guard.md): SQL Guard (실행 전 검증)
- [07_security/sql-safety.md](../07_security/sql-safety.md): SQL 안전성 정책
- [08_operations/deployment.md](../08_operations/deployment.md): DB 계정 설정
