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

`sql_exec.py`는 SQL Guard를 통과한 SELECT 쿼리를 대상 데이터베이스에서 실행하고 결과를 반환한다.

> **현재 구현**: `app/core/sql_exec.py` -- 4가지 실행 모드를 지원하며, `ORACLE_SQL_EXECUTION_MODE` 환경변수로 모드를 설정한다.

---

## 2. 실행 모드

| 모드 | 드라이버 | 설명 |
|------|---------|------|
| `direct` | psycopg2 (동기, `asyncio.to_thread` 래핑) | PostgreSQL 직접 실행 (readonly). 실패 시 mock 폴백 |
| `hybrid` (기본값) | psycopg2 → Weaver ACL → mock | Weaver 우선, 실패 시 mock 폴백 |
| `weaver` | httpx (Weaver ACL) | Weaver API 경유. 실패 시 에러 발생 (폴백 없음) |
| `mock` | 없음 | SQL 파싱 기반 모의 데이터 생성 |

### 2.1 드라이버 선택 근거

| 기준 | psycopg2 (현재) | asyncpg (미구현) |
|------|-----------------|------------------|
| 비동기 | `asyncio.to_thread` 래핑 | 네이티브 async |
| 읽기 전용 | `conn.set_session(readonly=True)` | 지원 |
| 선택 근거 | 범용성, 간단한 구현 | 향후 성능 최적화 시 전환 가능 |

---

## 3. 커넥션 관리

> **현재 구현**: 커넥션 풀을 사용하지 않는다. psycopg2로 매 요청마다 연결/해제한다.

```python
# sql_exec.py 기반 (실제 구현)
class SQLExecutor:
    """비동기 SQL 실행기."""

    def __init__(self, sql_timeout: int = 30, max_rows: int = 10000):
        self.sql_timeout = sql_timeout
        self.max_rows = max_rows
        self.execution_mode = settings.ORACLE_SQL_EXECUTION_MODE.lower()

    def _execute_direct_pg_sync(self, sql: str) -> ExecutionResult:
        """PostgreSQL에 직접 SQL을 동기로 실행한다 (스레드 풀에서 호출)."""
        import psycopg2

        db_url = settings.QUERY_HISTORY_DATABASE_URL
        conn = psycopg2.connect(db_url)
        try:
            conn.set_session(readonly=True, autocommit=True)
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows_raw = cur.fetchmany(self.max_rows + 1)
                truncated = len(rows_raw) > self.max_rows
                rows = [[self._serialize_value(v) for v in r] for r in rows_raw[:self.max_rows]]
        finally:
            conn.close()
        return ExecutionResult(columns=columns, rows=rows, ...)

    async def _execute_direct_pg(self, sql: str, user: CurrentUser) -> ExecutionResult:
        """PostgreSQL 직접 실행 (비동기 래퍼). asyncio.to_thread로 위임."""
        return await asyncio.to_thread(self._execute_direct_pg_sync, sql)
```

### 3.1 커넥션 전략

| 항목 | 현재 구현 | 향후 개선안 |
|------|----------|-----------|
| 드라이버 | psycopg2 (동기) | asyncpg (네이티브 async) |
| 풀링 | 없음 (매 요청 connect/close) | asyncpg.Pool (min=2, max=10) |
| 비동기 | `asyncio.to_thread` 래핑 | 네이티브 async |
| 읽기 전용 | `conn.set_session(readonly=True)` | 지원 |

---

## 4. SQL 실행 흐름

> **현재 구현**: `execute_sql()` 메서드는 `execution_mode` 설정에 따라 4가지 경로 중 하나를 선택한다.

```python
async def execute_sql(self, sql: str, datasource_id: str, user: CurrentUser,
                      timeout: int | None = None) -> ExecutionResult:
    """
    SQL 실행 전체 흐름 (4모드 분기).

    - direct: psycopg2로 직접 실행 (asyncio.to_thread). 실패 시 mock 폴백
    - hybrid: Weaver ACL 우선, 실패 시 mock 폴백
    - weaver: Weaver ACL 경유. 실패 시 에러 (폴백 없음)
    - mock: SQL 파싱 기반 모의 데이터 생성
    """
    effective_timeout = timeout or settings.ORACLE_SQL_EXECUTION_TIMEOUT_SEC

    if self.execution_mode == "mock":
        return await self._execute_mock(sql, user)
    elif self.execution_mode == "direct":
        try:
            return await self._execute_direct_pg(sql, user)
        except Exception:
            return await self._execute_mock(sql, user)
    elif self.execution_mode == "weaver":
        return await self._execute_via_weaver(sql, datasource_id, user, effective_timeout)
    else:  # hybrid
        try:
            return await self._execute_via_weaver(sql, datasource_id, user, effective_timeout)
        except Exception:
            return await self._execute_mock(sql, user)
```

### 4.1 direct_pg 모드 상세

```python
def _execute_direct_pg_sync(self, sql: str) -> ExecutionResult:
    """동기 psycopg2 호출 (asyncio.to_thread에서 실행)."""
    import psycopg2

    conn = psycopg2.connect(settings.QUERY_HISTORY_DATABASE_URL)
    try:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows_raw = cur.fetchmany(self.max_rows + 1)
            truncated = len(rows_raw) > self.max_rows
            rows = [[self._serialize_value(v) for v in r] for r in rows_raw[:self.max_rows]]
    finally:
        conn.close()
    return ExecutionResult(columns=columns, rows=rows, row_count=len(rows),
                           truncated=truncated, backend="direct_pg", ...)
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
| SQL 실행 | 15초 | `ORACLE_SQL_EXECUTION_TIMEOUT_SEC` (psycopg2 래핑) |
| DB statement | 30초 | PostgreSQL이 쿼리 취소 |

### 5.2 MySQL 타임아웃

> **참고**: 현재 Oracle 서비스의 SQL 실행은 PostgreSQL만 지원한다 (psycopg2 direct_pg 모드 또는 Weaver ACL 경유). MySQL 직접 실행은 미구현이다.

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

> **현재 구현**: direct_pg 모드에서는 psycopg2 예외가 발생한다. 실패 시 mock 폴백으로 전환된다.

| 에러 상황 | 동작 | 사용자 메시지 |
|----------|------|-------------|
| psycopg2 연결 실패 | mock 폴백 (hybrid/direct) 또는 에러 (weaver) | "쿼리 실행 중 오류가 발생했습니다" |
| SQL 문법 오류 | mock 폴백 (hybrid/direct) 또는 에러 (weaver) | "SQL 실행 에러" |
| Weaver ACL 타임아웃 | mock 폴백 (hybrid) 또는 에러 (weaver) | "쿼리 실행 시간 초과" |
| mock 모드 | 항상 성공 (모의 데이터 생성) | - |

### 7.2 폴백 전략

```
direct 모드:  direct_pg 실패 → mock 폴백
hybrid 모드:  weaver ACL 실패 → mock 폴백
weaver 모드:  weaver ACL 실패 → 에러 발생 (폴백 없음)
mock 모드:    항상 모의 데이터 반환
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
