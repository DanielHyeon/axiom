from __future__ import annotations

import asyncio
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any


def get_adapter(engine: str, connection: dict[str, Any]) -> "DataSourceAdapter":
    """엔진과 connection dict로 어댑터 인스턴스 반환. metadata-api.md 지원 엔진: postgresql, mysql, oracle."""
    engine = (engine or "").strip().lower()
    if engine == "postgresql" or engine == "postgres":
        dsn = _connection_to_pg_dsn(connection)
        return PostgresAdapter(dsn)
    if engine == "mysql":
        return MySQLAdapter(connection)
    if engine == "oracle":
        return OracleAdapter(connection)
    raise ValueError(f"Unsupported engine for metadata extraction: {engine!r}")


def _connection_to_pg_dsn(connection: dict[str, Any]) -> str:
    host = str(connection.get("host") or "localhost").strip()
    port = int(connection.get("port") or 5432)
    database = str(connection.get("database") or "").strip()
    user = str(connection.get("user") or "").strip()
    password = str(connection.get("password") or "").strip()
    if not database or not user:
        raise ValueError("connection must have database and user")
    password_enc = urllib.parse.quote_plus(password) if password else ""
    auth = f"{urllib.parse.quote_plus(user)}:{password_enc}@" if user else ""
    return f"postgresql://{auth}{host}:{port}/{database}"


import re


def _safe_identifier(name: str) -> bool:
    """SQL 식별자로 안전한 문자만 허용 (a-zA-Z0-9_)."""
    return bool(name and re.match(r"^[a-zA-Z0-9_]+$", name))


class DataSourceAdapter(ABC):
    @abstractmethod
    async def test_connection(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def extract_schema(self, *, include_row_counts: bool = False) -> dict[str, Any]:
        raise NotImplementedError


class PostgresAdapter(DataSourceAdapter):
    def __init__(self, dsn: str, *, connect_timeout_seconds: float = 3.0, max_tables: int = 200) -> None:
        if not dsn:
            raise ValueError("dsn is required")
        self.dsn = dsn
        self.connect_timeout_seconds = connect_timeout_seconds
        self.max_tables = max_tables

    def _is_mock(self) -> bool:
        return self.dsn.startswith("mock_")

    async def extract_schema(self, *, include_row_counts: bool = False) -> dict[str, Any]:
        if self._is_mock():
            return {
                "engine": "postgresql",
                "schema": "public",
                "tables": [
                    {
                        "name": "users",
                        "columns": [
                            {"name": "id", "type": "uuid", "nullable": False},
                            {"name": "email", "type": "text", "nullable": False},
                        ],
                    },
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "id", "type": "uuid", "nullable": False},
                            {"name": "user_id", "type": "uuid", "nullable": False},
                            {"name": "total_amount", "type": "numeric", "nullable": False},
                        ],
                    },
                ],
                "foreign_keys": [
                    {
                        "source_schema": "public",
                        "source_table": "orders",
                        "source_column": "user_id",
                        "target_schema": "public",
                        "target_table": "users",
                        "target_column": "id",
                        "constraint_name": "orders_user_id_fkey",
                    },
                ],
            }
        try:
            import asyncpg  # type: ignore
        except Exception as exc:
            raise RuntimeError("asyncpg package is required for postgres adapter") from exc

        conn = await asyncpg.connect(dsn=self.dsn, timeout=self.connect_timeout_seconds)
        try:
            rows = await conn.fetch(
                """
                SELECT
                    t.table_name,
                    c.column_name,
                    c.data_type,
                    (c.is_nullable = 'YES') AS is_nullable,
                    c.ordinal_position
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c
                  ON c.table_schema = t.table_schema
                 AND c.table_name = t.table_name
                WHERE t.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                ORDER BY t.table_name, c.ordinal_position
                LIMIT $1
                """,
                self.max_tables * 100,
            )
            tables = _pg_rows_to_tables(rows)
            schema_name = "public"
            if include_row_counts:
                for t in tables:
                    table_name = t.get("name") or ""
                    if _safe_identifier(table_name):
                        try:
                            n = await conn.fetchval(
                                f'SELECT count(*) FROM "{schema_name}"."{table_name}"'
                            )
                            t["row_count"] = int(n) if n is not None else 0
                        except Exception:
                            t["row_count"] = None
                    else:
                        t["row_count"] = None
            foreign_keys = await _pg_fetch_foreign_keys(conn, schema_name)
            return {"engine": "postgresql", "schema": schema_name, "tables": tables, "foreign_keys": foreign_keys}
        finally:
            await conn.close()

    async def test_connection(self) -> bool:
        if self._is_mock():
            return True
        try:
            import asyncpg  # type: ignore
        except Exception:
            return False
        try:
            conn = await asyncpg.connect(dsn=self.dsn, timeout=self.connect_timeout_seconds)
            try:
                await conn.execute("SELECT 1")
            finally:
                await conn.close()
            return True
        except Exception:
            return False


def _pg_rows_to_tables(rows: list) -> list[dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    for row in rows:
        table_name = str(row["table_name"])
        bucket = tables.setdefault(table_name, {"name": table_name, "columns": []})
        col_name = row.get("column_name")
        if not col_name:
            continue
        bucket["columns"].append(
            {
                "name": str(col_name),
                "type": str(row.get("data_type") or "text"),
                "nullable": bool(row.get("is_nullable", True)),
            }
        )
    return list(tables.values())


async def _pg_fetch_foreign_keys(conn: Any, schema_name: str) -> list[dict[str, Any]]:
    """PostgreSQL information_schema에서 FK 목록 조회. 반환: [{source_schema, source_table, source_column, target_schema, target_table, target_column, constraint_name}]"""
    try:
        rows = await conn.fetch(
            """
            SELECT
                tc.table_schema AS source_schema,
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_schema AS target_schema,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column,
                tc.constraint_name AS constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_catalog = kcu.table_catalog
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
                 AND tc.table_schema = ccu.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = $1
            ORDER BY tc.table_name, kcu.ordinal_position
            """,
            schema_name,
        )
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows or []:
        out.append({
            "source_schema": str(row.get("source_schema") or schema_name),
            "source_table": str(row.get("source_table") or ""),
            "source_column": str(row.get("source_column") or ""),
            "target_schema": str(row.get("target_schema") or ""),
            "target_table": str(row.get("target_table") or ""),
            "target_column": str(row.get("target_column") or ""),
            "constraint_name": str(row.get("constraint_name") or ""),
        })
    return out


async def _mysql_fetch_foreign_keys(conn: Any, schema_name: str) -> list[dict[str, Any]]:
    """MySQL information_schema.KEY_COLUMN_USAGE에서 FK 목록 조회. 반환: [{source_schema, source_table, source_column, target_schema, target_table, target_column, constraint_name}]"""
    try:
        import aiomysql  # type: ignore
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """
                SELECT
                    TABLE_SCHEMA AS source_schema,
                    TABLE_NAME AS source_table,
                    COLUMN_NAME AS source_column,
                    REFERENCED_TABLE_SCHEMA AS target_schema,
                    REFERENCED_TABLE_NAME AS target_table,
                    REFERENCED_COLUMN_NAME AS target_column,
                    CONSTRAINT_NAME AS constraint_name
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE REFERENCED_TABLE_NAME IS NOT NULL AND TABLE_SCHEMA = %s
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """,
                (schema_name,),
            )
            rows = await cur.fetchall()
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for row in rows or []:
        out.append({
            "source_schema": str(row.get("source_schema") or schema_name),
            "source_table": str(row.get("source_table") or ""),
            "source_column": str(row.get("source_column") or ""),
            "target_schema": str(row.get("target_schema") or ""),
            "target_table": str(row.get("target_table") or ""),
            "target_column": str(row.get("target_column") or ""),
            "constraint_name": str(row.get("constraint_name") or ""),
        })
    return out


class MySQLAdapter(DataSourceAdapter):
    """MySQL 메타데이터 추출. connection: host, port, database, user, password."""

    def __init__(self, connection: dict[str, Any], *, connect_timeout_seconds: float = 3.0, max_tables: int = 200) -> None:
        self.connection = dict(connection)
        self.connect_timeout_seconds = connect_timeout_seconds
        self.max_tables = max_tables

    async def extract_schema(self, *, include_row_counts: bool = False) -> dict[str, Any]:
        try:
            import aiomysql  # type: ignore
        except ImportError as exc:
            raise RuntimeError("aiomysql package is required for MySQL adapter") from exc
        host = str(self.connection.get("host") or "localhost").strip()
        port = int(self.connection.get("port") or 3306)
        database = str(self.connection.get("database") or "").strip()
        user = str(self.connection.get("user") or "").strip()
        password = str(self.connection.get("password") or "").strip()
        if not database or not user:
            raise ValueError("connection must have database and user")
        conn = await aiomysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            db=database,
            connect_timeout=int(self.connect_timeout_seconds),
        )
        try:
            tables: dict[str, dict[str, Any]] = {}
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT t.table_schema, t.table_name, c.column_name, c.data_type, c.is_nullable, c.ordinal_position
                    FROM information_schema.tables t
                    LEFT JOIN information_schema.columns c
                      ON c.table_schema = t.table_schema AND c.table_name = t.table_name
                    WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE'
                    ORDER BY t.table_name, c.ordinal_position
                    LIMIT %s
                    """,
                    (database, self.max_tables * 100),
                )
                rows = await cur.fetchall()
            for row in rows or []:
                schema_name = str(row.get("table_schema") or "public").strip()
                table_name = str(row.get("table_name") or "").strip()
                if not table_name:
                    continue
                key = (schema_name, table_name)
                bucket = tables.setdefault(key, {"name": table_name, "columns": []})
                col_name = row.get("column_name")
                if col_name:
                    bucket["columns"].append(
                        {
                            "name": str(col_name),
                            "type": str(row.get("data_type") or "varchar"),
                            "nullable": (str(row.get("is_nullable") or "").upper() == "YES"),
                        }
                    )
            schema_name = database
            table_list = [{"name": t["name"], "columns": t["columns"]} for (_, _), t in sorted(tables.items())]
            if include_row_counts:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    for t in table_list:
                        tn = t.get("name") or ""
                        if _safe_identifier(database) and _safe_identifier(tn):
                            try:
                                await cur.execute(
                                    "SELECT COUNT(*) AS c FROM `{0}`.`{1}`".format(database, tn)
                                )
                                row = await cur.fetchone()
                                t["row_count"] = int(row["c"]) if row and row.get("c") is not None else 0
                            except Exception:
                                t["row_count"] = None
                        else:
                            t["row_count"] = None
            foreign_keys = await _mysql_fetch_foreign_keys(conn, schema_name)
            return {"engine": "mysql", "schema": schema_name, "tables": table_list, "foreign_keys": foreign_keys}
        finally:
            conn.close()

    async def test_connection(self) -> bool:
        try:
            import aiomysql  # type: ignore
        except ImportError:
            return False
        try:
            conn = await aiomysql.connect(
                host=str(self.connection.get("host") or "localhost"),
                port=int(self.connection.get("port") or 3306),
                user=str(self.connection.get("user") or ""),
                password=str(self.connection.get("password") or ""),
                db=str(self.connection.get("database") or ""),
                connect_timeout=int(self.connect_timeout_seconds),
            )
            conn.close()
            return True
        except Exception:
            return False


def _oracle_connection_params(connection: dict[str, Any]) -> dict[str, Any]:
    """Oracle connection dict에서 oracledb.connect() 인자 구성. host, port, service_name 또는 sid, user, password."""
    host = str(connection.get("host") or "localhost").strip()
    port = int(connection.get("port") or 1521)
    user = str(connection.get("user") or "").strip()
    password = str(connection.get("password") or "").strip()
    service_name = (connection.get("service_name") or connection.get("service") or "").strip()
    sid = (connection.get("sid") or "").strip()
    if not user:
        raise ValueError("connection must have user")
    kwargs: dict[str, Any] = {"user": user, "password": password, "host": host, "port": port}
    if service_name:
        kwargs["service_name"] = service_name
    elif sid:
        kwargs["sid"] = sid
    else:
        kwargs["service_name"] = "ORCL"
    return kwargs


def _oracle_extract_schema_sync(connection: dict[str, Any], include_row_counts: bool) -> dict[str, Any]:
    """Oracle 메타데이터 동기 추출. oracledb 블로킹 호출을 asyncio.to_thread에서 실행용."""
    import oracledb  # type: ignore
    params = _oracle_connection_params(connection)
    schema_owner = str(connection.get("schema") or params.get("user") or "").strip().upper()
    conn = oracledb.connect(**params)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM ALL_TABLES
            WHERE OWNER = :owner
            ORDER BY TABLE_NAME
            """,
            {"owner": schema_owner},
        )
        table_names = [row[0] for row in cursor.fetchall()]
        tables: list[dict[str, Any]] = []
        for table_name in table_names:
            cursor.execute(
                """
                SELECT COLUMN_NAME, DATA_TYPE, NULLABLE, COLUMN_ID
                FROM ALL_TAB_COLUMNS
                WHERE OWNER = :owner AND TABLE_NAME = :tname
                ORDER BY COLUMN_ID
                """,
                {"owner": schema_owner, "tname": table_name},
            )
            columns = []
            for col_name, data_type, nullable, _ in cursor.fetchall():
                columns.append({
                    "name": str(col_name),
                    "type": str(data_type or "VARCHAR2"),
                    "nullable": (str(nullable or "Y").upper() == "Y"),
                })
            table_entry = {"name": table_name, "columns": columns}
            if include_row_counts and _safe_identifier(schema_owner) and _safe_identifier(table_name):
                try:
                    cursor.execute(f'SELECT COUNT(*) FROM "{schema_owner}"."{table_name}"')
                    row = cursor.fetchone()
                    table_entry["row_count"] = int(row[0]) if row else 0
                except Exception:
                    table_entry["row_count"] = None
            elif include_row_counts:
                table_entry["row_count"] = None
            tables.append(table_entry)
        foreign_keys = _oracle_fetch_fk_sync(cursor, schema_owner)
        return {"engine": "oracle", "schema": schema_owner, "tables": tables, "foreign_keys": foreign_keys}
    finally:
        conn.close()


def _oracle_fetch_fk_sync(cursor: Any, schema_owner: str) -> list[dict[str, Any]]:
    """ALL_CONSTRAINTS + ALL_CONS_COLUMNS로 FK 목록 조회."""
    try:
        cursor.execute(
            """
            SELECT
                c.OWNER AS source_schema,
                c.TABLE_NAME AS source_table,
                cc.COLUMN_NAME AS source_column,
                rc.OWNER AS target_schema,
                rc.TABLE_NAME AS target_table,
                rcc.COLUMN_NAME AS target_column,
                c.CONSTRAINT_NAME AS constraint_name
            FROM ALL_CONSTRAINTS c
            JOIN ALL_CONS_COLUMNS cc
              ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME AND c.TABLE_NAME = cc.TABLE_NAME
            JOIN ALL_CONSTRAINTS rc ON c.R_CONSTRAINT_NAME = rc.CONSTRAINT_NAME AND c.R_OWNER = rc.OWNER
            JOIN ALL_CONS_COLUMNS rcc
              ON rc.OWNER = rcc.OWNER AND rc.CONSTRAINT_NAME = rcc.CONSTRAINT_NAME
                 AND rc.TABLE_NAME = rcc.TABLE_NAME AND cc.POSITION = rcc.POSITION
            WHERE c.CONSTRAINT_TYPE = 'R' AND c.OWNER = :owner
            ORDER BY c.TABLE_NAME, cc.POSITION
            """,
            {"owner": schema_owner},
        )
        rows = cursor.fetchall()
    except Exception:
        return []
    return [
        {
            "source_schema": str(r[0] or schema_owner),
            "source_table": str(r[1] or ""),
            "source_column": str(r[2] or ""),
            "target_schema": str(r[3] or ""),
            "target_table": str(r[4] or ""),
            "target_column": str(r[5] or ""),
            "constraint_name": str(r[6] or ""),
        }
        for r in (rows or [])
    ]


class OracleAdapter(DataSourceAdapter):
    """Oracle 메타데이터 추출. oracledb 패키지 기반 (Thin 모드)."""

    def __init__(self, connection: dict[str, Any], *, connect_timeout_seconds: float = 10.0) -> None:
        self.connection = dict(connection)
        self.connect_timeout_seconds = connect_timeout_seconds

    async def extract_schema(self, *, include_row_counts: bool = False) -> dict[str, Any]:
        try:
            import oracledb  # type: ignore
        except ImportError as exc:
            raise RuntimeError("oracledb package is required for Oracle adapter. pip install oracledb") from exc
        return await asyncio.to_thread(_oracle_extract_schema_sync, self.connection, include_row_counts)

    async def test_connection(self) -> bool:
        try:
            import oracledb  # type: ignore
        except ImportError:
            return False

        def _ping() -> bool:
            params = _oracle_connection_params(self.connection)
            conn = oracledb.connect(**params)
            try:
                cur = conn.cursor()
                cur.execute("SELECT 1 FROM DUAL")
                cur.fetchone()
                return True
            finally:
                conn.close()

        try:
            return await asyncio.to_thread(_ping)
        except Exception:
            return False
