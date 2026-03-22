"""MySQL 스키마 인트로스펙션 어댑터.

KAIR data-fabric의 MySQLAdapter를 Axiom Weaver 패턴으로 이식.
PostgreSQL 전용이던 스키마 인트로스펙션을 MySQL로 확장한다.

기존 PostgreSQL 인트로스펙션: app/core/schema_introspection.py
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("mysql_adapter")

# aiomysql 의존성 — 선택적
try:
    import aiomysql  # type: ignore
    HAS_AIOMYSQL = True
except ImportError:
    HAS_AIOMYSQL = False
    aiomysql = None  # type: ignore


# ── MySQL 스키마 인트로스펙터 ───────────────────────────────────────


class MySQLSchemaIntrospector:
    """MySQL 스키마 인트로스펙션 어댑터.

    information_schema를 사용하여 MySQL 데이터베이스의
    스키마, 테이블, 컬럼, FK 정보를 비동기로 조회한다.
    """

    def _validate_dependency(self) -> None:
        """aiomysql 패키지 설치 여부 확인"""
        if not HAS_AIOMYSQL:
            raise ImportError(
                "aiomysql 패키지가 설치되지 않았습니다. "
                "pip install aiomysql 로 설치하세요."
            )

    async def _get_connection(self, conn_params: dict[str, Any]):
        """MySQL 연결 생성 헬퍼.

        conn_params 형식:
          {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "password",
            "db": "mydb"          # 선택
          }
        """
        self._validate_dependency()
        return await aiomysql.connect(
            host=conn_params.get("host", "localhost"),
            port=int(conn_params.get("port", 3306)),
            user=conn_params.get("user", "root"),
            password=conn_params.get("password", ""),
            db=conn_params.get("db", conn_params.get("database", "")),
            charset=conn_params.get("charset", "utf8mb4"),
            autocommit=True,
        )

    async def get_schemas(self, conn_params: dict[str, Any]) -> list[str]:
        """MySQL 데이터베이스(스키마) 목록을 조회한다.

        시스템 스키마(information_schema, mysql, performance_schema, sys)는 제외.

        Returns:
            스키마(데이터베이스) 이름 리스트
        """
        conn = await self._get_connection(conn_params)
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT SCHEMA_NAME
                    FROM information_schema.SCHEMATA
                    WHERE SCHEMA_NAME NOT IN (
                        'information_schema', 'mysql', 'performance_schema', 'sys'
                    )
                    ORDER BY SCHEMA_NAME
                    """
                )
                rows = await cur.fetchall()
                return [row[0] for row in rows]
        finally:
            conn.close()

    async def get_tables(
        self, conn_params: dict[str, Any], schema: str
    ) -> list[dict[str, Any]]:
        """지정된 스키마의 테이블 목록을 조회한다.

        Args:
            conn_params: MySQL 연결 파라미터
            schema: 스키마(데이터베이스) 이름

        Returns:
            테이블 정보 딕셔너리 리스트:
              [{"name": "...", "type": "BASE TABLE|VIEW", "engine": "...",
                "row_count": ..., "comment": "..."}]
        """
        if not schema or not schema.strip():
            raise ValueError("스키마 이름이 비어있습니다")

        conn = await self._get_connection(conn_params)
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        TABLE_NAME,
                        TABLE_TYPE,
                        ENGINE,
                        TABLE_ROWS,
                        TABLE_COMMENT
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = %s
                    ORDER BY TABLE_NAME
                    """,
                    (schema,),
                )
                rows = await cur.fetchall()
                return [
                    {
                        "name": row[0],
                        "type": row[1],
                        "engine": row[2],
                        "row_count": row[3],
                        "comment": row[4] or "",
                    }
                    for row in rows
                ]
        finally:
            conn.close()

    async def get_columns(
        self,
        conn_params: dict[str, Any],
        schema: str,
        table: str,
    ) -> list[dict[str, Any]]:
        """테이블의 컬럼 목록을 조회한다.

        Args:
            conn_params: MySQL 연결 파라미터
            schema: 스키마 이름
            table: 테이블 이름

        Returns:
            컬럼 정보 딕셔너리 리스트:
              [{"name": "...", "type": "...", "nullable": bool,
                "default": ..., "is_primary": bool, "comment": "...",
                "ordinal_position": int}]
        """
        if not schema or not table:
            raise ValueError("스키마와 테이블 이름이 필요합니다")

        conn = await self._get_connection(conn_params)
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        COLUMN_DEFAULT,
                        COLUMN_KEY,
                        COLUMN_COMMENT,
                        ORDINAL_POSITION,
                        CHARACTER_MAXIMUM_LENGTH,
                        NUMERIC_PRECISION,
                        NUMERIC_SCALE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                    """,
                    (schema, table),
                )
                rows = await cur.fetchall()
                return [
                    {
                        "name": row[0],
                        "type": self._format_column_type(
                            data_type=row[1],
                            char_max_length=row[7],
                            num_precision=row[8],
                            num_scale=row[9],
                        ),
                        "nullable": row[2] == "YES",
                        "default": row[3],
                        "is_primary": row[4] == "PRI",
                        "comment": row[5] or "",
                        "ordinal_position": row[6],
                    }
                    for row in rows
                ]
        finally:
            conn.close()

    async def get_foreign_keys(
        self, conn_params: dict[str, Any], schema: str
    ) -> list[dict[str, Any]]:
        """스키마의 모든 FK 관계를 조회한다.

        Args:
            conn_params: MySQL 연결 파라미터
            schema: 스키마 이름

        Returns:
            FK 정보 딕셔너리 리스트:
              [{"constraint_name": "...",
                "table": "...", "column": "...",
                "referenced_table": "...", "referenced_column": "..."}]
        """
        if not schema:
            raise ValueError("스키마 이름이 필요합니다")

        conn = await self._get_connection(conn_params)
        try:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        kcu.CONSTRAINT_NAME,
                        kcu.TABLE_NAME,
                        kcu.COLUMN_NAME,
                        kcu.REFERENCED_TABLE_NAME,
                        kcu.REFERENCED_COLUMN_NAME
                    FROM information_schema.KEY_COLUMN_USAGE kcu
                    WHERE kcu.TABLE_SCHEMA = %s
                      AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
                    ORDER BY kcu.TABLE_NAME, kcu.ORDINAL_POSITION
                    """,
                    (schema,),
                )
                rows = await cur.fetchall()
                return [
                    {
                        "constraint_name": row[0],
                        "table": row[1],
                        "column": row[2],
                        "referenced_table": row[3],
                        "referenced_column": row[4],
                    }
                    for row in rows
                ]
        finally:
            conn.close()

    @staticmethod
    def _format_column_type(
        data_type: str,
        char_max_length: int | None,
        num_precision: int | None,
        num_scale: int | None,
    ) -> str:
        """MySQL 데이터 타입을 읽기 좋은 문자열로 변환.

        예: varchar(255), decimal(10,2), int
        """
        dt = data_type.lower() if data_type else "unknown"

        if dt in ("varchar", "char", "binary", "varbinary") and char_max_length:
            return f"{dt}({char_max_length})"
        if dt in ("decimal", "numeric") and num_precision is not None:
            scale = num_scale if num_scale else 0
            return f"{dt}({num_precision},{scale})"
        return dt


# 싱글턴 인스턴스 (다른 모듈에서 임포트 용)
mysql_introspector = MySQLSchemaIntrospector()
