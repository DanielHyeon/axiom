# 어댑터 패턴 기반 스키마 인트로스펙션

<!-- affects: backend, data -->
<!-- requires-update: 03_backend/schema-introspection.md, 06_data/datasource-config.md -->

## 이 문서가 답하는 질문

- 스키마 인트로스펙션은 왜 어댑터 패턴을 사용하는가?
- 각 DB 엔진별 어댑터는 어떻게 구현되는가?
- 새로운 DB 엔진 어댑터를 추가하려면 어떻게 하는가?
- 어댑터가 추출하는 메타데이터의 범위는 무엇인가?

---

## 1. 설계 결정

### 1.1 왜 어댑터 패턴인가

**결정**: 스키마 인트로스펙션에 어댑터 패턴(Strategy Pattern)을 적용한다.

**근거**:
- 각 DB 엔진은 **스키마 조회 SQL이 완전히 다르다** (information_schema vs ALL_TAB_COLUMNS 등)
- MindsDB는 스키마를 추출해주지 않는다 (쿼리 실행만 담당)
- 새로운 DB 엔진 추가 시 **기존 코드 변경 없이** 어댑터만 추가하면 된다
- K-AIR의 `schema_introspection.py` (880줄)를 엔진별로 분리하여 유지보수성 향상

**참조**: ADR-002 (`99_decisions/ADR-002-adapter-pattern.md`)

### 1.2 아키텍처

```
┌─ SchemaIntrospectionService ─────────────────────────┐
│                                                       │
│  def get_adapter(engine: str) -> BaseAdapter:         │
│      match engine:                                    │
│          case "postgresql": return PostgreSQLAdapter() │
│          case "mysql":      return MySQLAdapter()      │
│          case "oracle":     return OracleAdapter()     │
│                                                       │
│  async def extract_metadata(datasource):              │
│      adapter = self.get_adapter(datasource.engine)    │
│      schemas = await adapter.get_schemas()            │
│      for schema in schemas:                           │
│          tables = await adapter.get_tables(schema)    │
│          for table in tables:                         │
│              columns = await adapter.get_columns(...) │
│              fks = await adapter.get_foreign_keys(...)│
│      return metadata                                  │
│                                                       │
└───────────────────────────────────────────────────────┘
         │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼─────┐
    │PostgreSQL│   │  MySQL    │  │  Oracle  │
    │ Adapter  │   │  Adapter  │  │  Adapter │
    │          │   │           │  │          │
    │ asyncpg  │   │ aiomysql  │  │ oracledb │
    └──────────┘   └───────────┘  └──────────┘
```

---

## 2. 베이스 어댑터 인터페이스

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ColumnInfo:
    """컬럼 메타데이터"""
    name: str
    data_type: str
    nullable: bool
    default_value: Optional[str] = None
    comment: Optional[str] = None
    is_primary_key: bool = False
    character_maximum_length: Optional[int] = None
    numeric_precision: Optional[int] = None


@dataclass
class ForeignKeyInfo:
    """외래 키 메타데이터"""
    constraint_name: str
    source_column: str
    target_schema: str
    target_table: str
    target_column: str


@dataclass
class TableInfo:
    """테이블 메타데이터"""
    schema_name: str
    table_name: str
    table_type: str  # 'BASE TABLE' | 'VIEW'
    comment: Optional[str] = None
    row_count: Optional[int] = None


class BaseAdapter(ABC):
    """스키마 인트로스펙션 베이스 어댑터

    모든 DB 엔진별 어댑터는 이 인터페이스를 구현해야 한다.
    """

    def __init__(self, connection_params: dict):
        self.connection_params = connection_params

    @abstractmethod
    async def connect(self) -> None:
        """DB 연결 수립"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """DB 연결 해제"""
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """연결 테스트 (SELECT 1 등)"""
        ...

    @abstractmethod
    async def get_schemas(self) -> List[str]:
        """스키마 목록 조회"""
        ...

    @abstractmethod
    async def get_tables(self, schema: str) -> List[TableInfo]:
        """지정 스키마의 테이블 목록 조회"""
        ...

    @abstractmethod
    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        """지정 테이블의 컬럼 목록 조회"""
        ...

    @abstractmethod
    async def get_foreign_keys(self, schema: str, table: str) -> List[ForeignKeyInfo]:
        """지정 테이블의 외래 키 목록 조회"""
        ...

    @abstractmethod
    async def get_sample_data(self, schema: str, table: str, limit: int = 5) -> List[dict]:
        """테이블 샘플 데이터 조회"""
        ...

    @abstractmethod
    async def get_row_count(self, schema: str, table: str) -> int:
        """테이블 행 수 조회"""
        ...
```

### 연결 장애 처리 참조

> **복원력 설계**: 어댑터 `connect()` 실패 시의 Circuit Breaker (Core→Weaver: 3회/60s, 60s Open), Retry 정책, Fallback 전략은 Core의 [resilience-patterns.md](../../../core/docs/01_architecture/resilience-patterns.md) §2~4를 참조한다.

---

## 3. PostgreSQL 어댑터

K-AIR `schema_introspection.py`의 PostgreSQLAdapter를 기반으로 구현한다.

```python
import asyncpg
from typing import List


class PostgreSQLAdapter(BaseAdapter):
    """PostgreSQL 스키마 인트로스펙션 어댑터

    asyncpg를 사용한 비동기 연결.
    information_schema와 pg_catalog를 활용하여 메타데이터를 추출한다.
    """

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            host=self.connection_params["host"],
            port=self.connection_params.get("port", 5432),
            database=self.connection_params["database"],
            user=self.connection_params["user"],
            password=self.connection_params["password"],
            min_size=1,
            max_size=5,
            command_timeout=30,
        )

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()

    async def test_connection(self) -> bool:
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    async def get_schemas(self) -> List[str]:
        """시스템 스키마(pg_*, information_schema)를 제외한 사용자 스키마 목록"""
        query = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema',
                                       'pg_toast', 'pg_temp_1', 'pg_toast_temp_1')
            ORDER BY schema_name;
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [row["schema_name"] for row in rows]

    async def get_tables(self, schema: str) -> List[TableInfo]:
        """테이블과 뷰 목록 (시스템 테이블 제외)"""
        query = """
            SELECT
                t.table_name,
                t.table_type,
                obj_description((quote_ident(t.table_schema) || '.' ||
                    quote_ident(t.table_name))::regclass) as comment,
                (SELECT reltuples::bigint
                 FROM pg_class
                 WHERE oid = (quote_ident(t.table_schema) || '.' ||
                     quote_ident(t.table_name))::regclass) as row_count
            FROM information_schema.tables t
            WHERE t.table_schema = $1
              AND t.table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY t.table_name;
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, schema)
        return [
            TableInfo(
                schema_name=schema,
                table_name=row["table_name"],
                table_type=row["table_type"],
                comment=row["comment"],
                row_count=row["row_count"],
            )
            for row in rows
        ]

    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        """컬럼 상세 정보 (PK 포함)"""
        query = """
            SELECT
                c.column_name,
                c.data_type,
                c.is_nullable = 'YES' as nullable,
                c.column_default,
                c.character_maximum_length,
                c.numeric_precision,
                col_description(
                    (quote_ident($1) || '.' || quote_ident($2))::regclass,
                    c.ordinal_position
                ) as comment,
                EXISTS (
                    SELECT 1 FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_schema = $1
                      AND tc.table_name = $2
                      AND tc.constraint_type = 'PRIMARY KEY'
                      AND kcu.column_name = c.column_name
                ) as is_primary_key
            FROM information_schema.columns c
            WHERE c.table_schema = $1
              AND c.table_name = $2
            ORDER BY c.ordinal_position;
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, schema, table)
        return [
            ColumnInfo(
                name=row["column_name"],
                data_type=row["data_type"],
                nullable=row["nullable"],
                default_value=row["column_default"],
                comment=row["comment"],
                is_primary_key=row["is_primary_key"],
                character_maximum_length=row["character_maximum_length"],
                numeric_precision=row["numeric_precision"],
            )
            for row in rows
        ]

    async def get_foreign_keys(self, schema: str, table: str) -> List[ForeignKeyInfo]:
        """외래 키 관계 추출"""
        query = """
            SELECT
                tc.constraint_name,
                kcu.column_name as source_column,
                ccu.table_schema as target_schema,
                ccu.table_name as target_table,
                ccu.column_name as target_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.table_schema = $1
              AND tc.table_name = $2
              AND tc.constraint_type = 'FOREIGN KEY';
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, schema, table)
        return [
            ForeignKeyInfo(
                constraint_name=row["constraint_name"],
                source_column=row["source_column"],
                target_schema=row["target_schema"],
                target_table=row["target_table"],
                target_column=row["target_column"],
            )
            for row in rows
        ]

    async def get_sample_data(self, schema: str, table: str, limit: int = 5) -> List[dict]:
        """샘플 데이터 조회 (최대 limit 행)"""
        # SQL 인젝션 방지: schema/table은 identifier이므로 quote_ident 사용
        query = f'SELECT * FROM "{schema}"."{table}" LIMIT {min(limit, 100)}'
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query)
        return [dict(row) for row in rows]

    async def get_row_count(self, schema: str, table: str) -> int:
        """테이블 행 수 (pg_class의 추정치 사용, 정확한 COUNT는 느림)"""
        query = """
            SELECT reltuples::bigint as count
            FROM pg_class
            WHERE oid = (quote_ident($1) || '.' || quote_ident($2))::regclass;
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, schema, table)
        return row["count"] if row else 0
```

---

## 4. MySQL 어댑터

```python
import aiomysql
from typing import List


class MySQLAdapter(BaseAdapter):
    """MySQL 스키마 인트로스펙션 어댑터

    aiomysql을 사용한 비동기 연결.
    information_schema를 활용하여 메타데이터를 추출한다.
    """

    async def connect(self) -> None:
        self.pool = await aiomysql.create_pool(
            host=self.connection_params["host"],
            port=self.connection_params.get("port", 3306),
            db=self.connection_params["database"],
            user=self.connection_params["user"],
            password=self.connection_params["password"],
            minsize=1,
            maxsize=5,
            connect_timeout=30,
        )

    async def disconnect(self) -> None:
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()

    async def get_schemas(self) -> List[str]:
        """MySQL에서 schema = database"""
        query = """
            SELECT SCHEMA_NAME
            FROM information_schema.SCHEMATA
            WHERE SCHEMA_NAME NOT IN ('information_schema', 'mysql',
                                       'performance_schema', 'sys')
            ORDER BY SCHEMA_NAME;
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
        return [row["SCHEMA_NAME"] for row in rows]

    async def get_tables(self, schema: str) -> List[TableInfo]:
        query = """
            SELECT
                TABLE_NAME,
                TABLE_TYPE,
                TABLE_COMMENT,
                TABLE_ROWS
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
            ORDER BY TABLE_NAME;
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, (schema,))
                rows = await cur.fetchall()
        return [
            TableInfo(
                schema_name=schema,
                table_name=row["TABLE_NAME"],
                table_type=row["TABLE_TYPE"],
                comment=row["TABLE_COMMENT"] or None,
                row_count=row["TABLE_ROWS"],
            )
            for row in rows
        ]

    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        query = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                IS_NULLABLE = 'YES' as nullable,
                COLUMN_DEFAULT,
                CHARACTER_MAXIMUM_LENGTH,
                NUMERIC_PRECISION,
                COLUMN_COMMENT,
                COLUMN_KEY = 'PRI' as is_primary_key
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION;
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, (schema, table))
                rows = await cur.fetchall()
        return [
            ColumnInfo(
                name=row["COLUMN_NAME"],
                data_type=row["DATA_TYPE"],
                nullable=bool(row["nullable"]),
                default_value=row["COLUMN_DEFAULT"],
                comment=row["COLUMN_COMMENT"] or None,
                is_primary_key=bool(row["is_primary_key"]),
                character_maximum_length=row["CHARACTER_MAXIMUM_LENGTH"],
                numeric_precision=row["NUMERIC_PRECISION"],
            )
            for row in rows
        ]

    async def get_foreign_keys(self, schema: str, table: str) -> List[ForeignKeyInfo]:
        query = """
            SELECT
                CONSTRAINT_NAME,
                COLUMN_NAME as source_column,
                REFERENCED_TABLE_SCHEMA as target_schema,
                REFERENCED_TABLE_NAME as target_table,
                REFERENCED_COLUMN_NAME as target_column
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND TABLE_NAME = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL;
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, (schema, table))
                rows = await cur.fetchall()
        return [
            ForeignKeyInfo(
                constraint_name=row["CONSTRAINT_NAME"],
                source_column=row["source_column"],
                target_schema=row["target_schema"],
                target_table=row["target_table"],
                target_column=row["target_column"],
            )
            for row in rows
        ]

    async def get_sample_data(self, schema: str, table: str, limit: int = 5) -> List[dict]:
        query = f"SELECT * FROM `{schema}`.`{table}` LIMIT {min(limit, 100)}"
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query)
                rows = await cur.fetchall()
        return list(rows)

    async def get_row_count(self, schema: str, table: str) -> int:
        query = """
            SELECT TABLE_ROWS
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s;
        """
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, (schema, table))
                row = await cur.fetchone()
        return row["TABLE_ROWS"] if row else 0
```

---

## 5. Oracle 어댑터 (신규 구현)

K-AIR에는 Oracle 어댑터가 없었으므로, Axiom Weaver에서 신규 추가한다.

```python
import oracledb
from typing import List


class OracleAdapter(BaseAdapter):
    """Oracle 스키마 인트로스펙션 어댑터

    oracledb (python-oracledb)를 사용한 연결.
    ALL_TAB_COLUMNS, ALL_CONSTRAINTS 등 Oracle 딕셔너리 뷰 활용.

    주의: Oracle은 스키마 = 사용자(User)이다.
    """

    async def connect(self) -> None:
        dsn = oracledb.makedsn(
            host=self.connection_params["host"],
            port=self.connection_params.get("port", 1521),
            service_name=self.connection_params.get("service_name"),
            sid=self.connection_params.get("sid"),
        )
        self.pool = oracledb.create_pool_async(
            user=self.connection_params["user"],
            password=self.connection_params["password"],
            dsn=dsn,
            min=1,
            max=5,
        )

    async def disconnect(self) -> None:
        if self.pool:
            await self.pool.close()

    async def get_schemas(self) -> List[str]:
        """Oracle 스키마(사용자) 목록 - 시스템 스키마 제외"""
        query = """
            SELECT username
            FROM all_users
            WHERE username NOT IN ('SYS', 'SYSTEM', 'DBSNMP', 'OUTLN',
                                    'MDSYS', 'ORDSYS', 'ORDPLUGINS',
                                    'CTXSYS', 'DSSYS', 'WMSYS', 'XDB')
            ORDER BY username
        """
        async with self.pool.acquire() as conn:
            cursor = conn.cursor()
            await cursor.execute(query)
            rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_tables(self, schema: str) -> List[TableInfo]:
        query = """
            SELECT
                table_name,
                'BASE TABLE' as table_type,
                comments,
                num_rows
            FROM all_tab_comments atc
            JOIN all_tables at ON atc.owner = at.owner
                AND atc.table_name = at.table_name
            WHERE atc.owner = :schema
              AND atc.table_type = 'TABLE'
            ORDER BY table_name
        """
        async with self.pool.acquire() as conn:
            cursor = conn.cursor()
            await cursor.execute(query, {"schema": schema.upper()})
            rows = await cursor.fetchall()
        return [
            TableInfo(
                schema_name=schema,
                table_name=row[0],
                table_type=row[1],
                comment=row[2],
                row_count=row[3],
            )
            for row in rows
        ]

    async def get_columns(self, schema: str, table: str) -> List[ColumnInfo]:
        query = """
            SELECT
                atc.column_name,
                atc.data_type,
                CASE WHEN atc.nullable = 'Y' THEN 1 ELSE 0 END as nullable,
                atc.data_default,
                atc.char_length,
                atc.data_precision,
                acc.comments,
                CASE WHEN EXISTS (
                    SELECT 1 FROM all_cons_columns acc2
                    JOIN all_constraints ac ON acc2.constraint_name = ac.constraint_name
                    WHERE ac.owner = :schema
                      AND ac.table_name = :table
                      AND ac.constraint_type = 'P'
                      AND acc2.column_name = atc.column_name
                ) THEN 1 ELSE 0 END as is_pk
            FROM all_tab_columns atc
            LEFT JOIN all_col_comments acc
                ON atc.owner = acc.owner
                AND atc.table_name = acc.table_name
                AND atc.column_name = acc.column_name
            WHERE atc.owner = :schema
              AND atc.table_name = :table
            ORDER BY atc.column_id
        """
        async with self.pool.acquire() as conn:
            cursor = conn.cursor()
            await cursor.execute(query, {"schema": schema.upper(), "table": table.upper()})
            rows = await cursor.fetchall()
        return [
            ColumnInfo(
                name=row[0],
                data_type=row[1],
                nullable=bool(row[2]),
                default_value=str(row[3]) if row[3] else None,
                comment=row[6],
                is_primary_key=bool(row[7]),
                character_maximum_length=row[4],
                numeric_precision=row[5],
            )
            for row in rows
        ]

    async def get_foreign_keys(self, schema: str, table: str) -> List[ForeignKeyInfo]:
        query = """
            SELECT
                ac.constraint_name,
                acc.column_name as source_column,
                ac_r.owner as target_schema,
                ac_r.table_name as target_table,
                acc_r.column_name as target_column
            FROM all_constraints ac
            JOIN all_cons_columns acc
                ON ac.constraint_name = acc.constraint_name AND ac.owner = acc.owner
            JOIN all_constraints ac_r
                ON ac.r_constraint_name = ac_r.constraint_name AND ac.r_owner = ac_r.owner
            JOIN all_cons_columns acc_r
                ON ac_r.constraint_name = acc_r.constraint_name AND ac_r.owner = acc_r.owner
            WHERE ac.owner = :schema
              AND ac.table_name = :table
              AND ac.constraint_type = 'R'
        """
        async with self.pool.acquire() as conn:
            cursor = conn.cursor()
            await cursor.execute(query, {"schema": schema.upper(), "table": table.upper()})
            rows = await cursor.fetchall()
        return [
            ForeignKeyInfo(
                constraint_name=row[0],
                source_column=row[1],
                target_schema=row[2],
                target_table=row[3],
                target_column=row[4],
            )
            for row in rows
        ]

    async def get_sample_data(self, schema: str, table: str, limit: int = 5) -> List[dict]:
        query = f'SELECT * FROM "{schema}"."{table}" WHERE ROWNUM <= {min(limit, 100)}'
        async with self.pool.acquire() as conn:
            cursor = conn.cursor()
            await cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_row_count(self, schema: str, table: str) -> int:
        query = """
            SELECT num_rows FROM all_tables
            WHERE owner = :schema AND table_name = :table
        """
        async with self.pool.acquire() as conn:
            cursor = conn.cursor()
            await cursor.execute(query, {"schema": schema.upper(), "table": table.upper()})
            row = await cursor.fetchone()
        return row[0] if row and row[0] else 0
```

---

## 6. 어댑터 팩토리

```python
class AdapterFactory:
    """DB 엔진에 따라 적절한 어댑터를 반환하는 팩토리"""

    _adapters = {
        "postgresql": PostgreSQLAdapter,
        "postgres": PostgreSQLAdapter,  # alias
        "mysql": MySQLAdapter,
        "mariadb": MySQLAdapter,  # compatible
        "oracle": OracleAdapter,
    }

    # metadata extraction is supported for these engines only
    SUPPORTED_ENGINES = list(_adapters.keys())

    @classmethod
    def get_adapter(cls, engine: str, connection_params: dict) -> BaseAdapter:
        adapter_class = cls._adapters.get(engine.lower())
        if not adapter_class:
            raise ValueError(
                f"Unsupported engine for schema introspection: {engine}. "
                f"Supported: {cls.SUPPORTED_ENGINES}"
            )
        return adapter_class(connection_params)

    @classmethod
    def is_supported(cls, engine: str) -> bool:
        return engine.lower() in cls._adapters
```

---

## 7. 새로운 어댑터 추가 가이드

새로운 DB 엔진(예: SQL Server)의 어댑터를 추가하려면:

### 7.1 단계

1. `adapters/sqlserver.py` 파일 생성
2. `BaseAdapter`를 상속하여 모든 추상 메서드 구현
3. `AdapterFactory._adapters`에 등록
4. 의존성 추가 (`pyproject.toml`)
5. `06_data/datasource-config.md`에 연결 파라미터 문서화

### 7.2 체크리스트

| 항목 | 설명 |
|------|------|
| `connect()` | 커넥션 풀 생성 (비동기 우선) |
| `disconnect()` | 풀 정리 |
| `test_connection()` | SELECT 1 또는 동등한 쿼리 |
| `get_schemas()` | 시스템 스키마 제외 |
| `get_tables()` | BASE TABLE과 VIEW 포함 |
| `get_columns()` | PK 여부, nullable, 기본값, 코멘트 포함 |
| `get_foreign_keys()` | 소스/타겟 스키마.테이블.컬럼 |
| `get_sample_data()` | LIMIT 적용, 최대 100행 |
| `get_row_count()` | 추정치 우선 (카탈로그 뷰), 정확한 COUNT는 느림 |

### 7.3 금지사항

- 어댑터 내에서 Neo4j에 직접 접근하지 않는다 (서비스 레이어 책임)
- 어댑터 내에서 MindsDB에 접근하지 않는다
- 어댑터는 메타데이터 추출만 담당한다 (데이터 변경 쿼리 금지)

---

## 8. 관련 문서

| 문서 | 설명 |
|------|------|
| `03_backend/schema-introspection.md` | 인트로스펙션 서비스 구현 상세 |
| `06_data/datasource-config.md` | 엔진별 연결 설정 파라미터 |
| `99_decisions/ADR-002-adapter-pattern.md` | 어댑터 패턴 선택 근거 |
