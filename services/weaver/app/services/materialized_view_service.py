"""Materialized View 관리 서비스.

PostgreSQL Materialized View(물질화 뷰)의 생성, 새로고침, 삭제, 목록 조회를 담당한다.
MindsDB 클라이언트를 통해 SQL을 실행하여 대상 데이터소스의 MV를 관리한다.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.services.mindsdb_client import MindsDBClient, mindsdb_client

logger = logging.getLogger("axiom.weaver.mv")

# SQL 식별자 유효성 검사 패턴 — 인젝션 방지
# 알파벳/언더스코어로 시작, 알파벳/숫자/언더스코어 0~62자 (최대 63자)
_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


class MaterializedViewError(Exception):
    """Materialized View 작업 중 발생한 오류."""
    pass


def validate_sql_identifier(name: str) -> bool:
    """SQL 식별자가 안전한 형식인지 검증한다.

    인젝션 공격을 방지하기 위해 식별자 패턴을 엄격히 제한한다.
    허용: 알파벳/언더스코어로 시작, 알파벳/숫자/언더스코어만 포함, 최대 63자.

    Args:
        name: 검증할 SQL 식별자

    Returns:
        유효하면 True, 아니면 False
    """
    return bool(_IDENTIFIER_PATTERN.match(name))


def _ensure_valid_identifier(name: str, label: str = "식별자") -> None:
    """SQL 식별자가 유효하지 않으면 예외를 발생시킨다.

    Args:
        name: 검증할 식별자
        label: 오류 메시지에 사용할 라벨 (예: '뷰 이름', '스키마 이름')
    """
    if not validate_sql_identifier(name):
        raise MaterializedViewError(
            f"유효하지 않은 {label}: '{name}' — "
            f"알파벳/언더스코어로 시작하고, 알파벳/숫자/언더스코어만 포함해야 합니다 (최대 63자)"
        )


class MaterializedViewService:
    """Materialized View CRUD 서비스.

    MindsDB 클라이언트를 통해 대상 데이터베이스에서 MV를 관리한다.
    모든 식별자는 SQL 인젝션 방지를 위해 검증 후 사용한다.
    """

    def __init__(self, client: MindsDBClient | None = None) -> None:
        self._client = client or mindsdb_client

    async def create_mv(
        self,
        name: str,
        source_table: str,
        schema_name: str = "public",
        select_query: str | None = None,
        database: str | None = None,
    ) -> dict[str, Any]:
        """Materialized View를 생성한다.

        Args:
            name: MV 이름
            source_table: 원본 테이블 이름 (select_query가 없을 때 사용)
            schema_name: 스키마 이름 (기본값: public)
            select_query: 커스텀 SELECT 쿼리 (지정 시 source_table 대신 사용)
            database: MindsDB 데이터베이스 이름 (USE 구문용)

        Returns:
            생성 결과 딕셔너리
        """
        _ensure_valid_identifier(name, "뷰 이름")
        _ensure_valid_identifier(schema_name, "스키마 이름")

        # 커스텀 쿼리가 없으면 source_table에서 전체 SELECT
        if select_query:
            query_body = select_query
        else:
            _ensure_valid_identifier(source_table, "테이블 이름")
            query_body = f"SELECT * FROM {schema_name}.{source_table}"

        sql = f"CREATE MATERIALIZED VIEW {schema_name}.{name} AS {query_body}"
        logger.info("MV 생성: %s.%s", schema_name, name)

        result = await self._client.execute_query(sql, database=database)
        return {"status": "created", "name": name, "schema": schema_name, **result}

    async def refresh_mv(
        self,
        name: str,
        schema_name: str = "public",
        concurrently: bool = False,
        database: str | None = None,
    ) -> dict[str, Any]:
        """Materialized View를 새로고침(갱신)한다.

        Args:
            name: MV 이름
            schema_name: 스키마 이름
            concurrently: CONCURRENTLY 옵션 사용 여부 (유니크 인덱스 필요)
            database: MindsDB 데이터베이스 이름

        Returns:
            새로고침 결과 딕셔너리
        """
        _ensure_valid_identifier(name, "뷰 이름")
        _ensure_valid_identifier(schema_name, "스키마 이름")

        concurrent_clause = " CONCURRENTLY" if concurrently else ""
        sql = f"REFRESH MATERIALIZED VIEW{concurrent_clause} {schema_name}.{name}"
        logger.info("MV 새로고침: %s.%s (concurrently=%s)", schema_name, name, concurrently)

        result = await self._client.execute_query(sql, database=database)
        return {"status": "refreshed", "name": name, "schema": schema_name, **result}

    async def drop_mv(
        self,
        name: str,
        schema_name: str = "public",
        if_exists: bool = True,
        database: str | None = None,
    ) -> dict[str, Any]:
        """Materialized View를 삭제한다.

        Args:
            name: MV 이름
            schema_name: 스키마 이름
            if_exists: IF EXISTS 절 사용 여부 (기본: True)
            database: MindsDB 데이터베이스 이름

        Returns:
            삭제 결과 딕셔너리
        """
        _ensure_valid_identifier(name, "뷰 이름")
        _ensure_valid_identifier(schema_name, "스키마 이름")

        exists_clause = " IF EXISTS" if if_exists else ""
        sql = f"DROP MATERIALIZED VIEW{exists_clause} {schema_name}.{name}"
        logger.info("MV 삭제: %s.%s", schema_name, name)

        result = await self._client.execute_query(sql, database=database)
        return {"status": "dropped", "name": name, "schema": schema_name, **result}

    async def list_mvs(
        self,
        schema_name: str = "public",
        database: str | None = None,
    ) -> list[dict[str, Any]]:
        """스키마 내 모든 Materialized View 목록을 조회한다.

        PostgreSQL의 pg_matviews 시스템 카탈로그를 사용한다.

        Args:
            schema_name: 스키마 이름
            database: MindsDB 데이터베이스 이름

        Returns:
            MV 정보 딕셔너리 목록
        """
        _ensure_valid_identifier(schema_name, "스키마 이름")

        sql = (
            "SELECT schemaname, matviewname, matviewowner, ispopulated, definition "
            "FROM pg_matviews "
            f"WHERE schemaname = '{schema_name}' "
            "ORDER BY matviewname"
        )
        logger.info("MV 목록 조회: schema=%s", schema_name)

        result = await self._client.execute_query(sql, database=database)
        rows = result.get("data", [])
        columns = result.get("columns", [])

        # 컬럼 이름이 있으면 딕셔너리로 변환, 없으면 원본 반환
        if columns and rows:
            return [
                dict(zip(columns, row)) if isinstance(row, (list, tuple)) else row
                for row in rows
            ]
        return rows


# 모듈 수준 싱글톤 인스턴스
mv_service = MaterializedViewService()
