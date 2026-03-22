"""Instance Fetcher 서비스 — 온톨로지 노드 바인딩 데이터 프리뷰.

KAIR instance_fetcher.py를 Axiom Weaver 패턴으로 이식.
노드의 dataSourceSchema 정보를 기반으로 실제 데이터를 조회한다.

데이터 흐름:
  1. node_id로 Synapse에서 노드 메타데이터 조회 (dataSourceSchema)
  2. 메타데이터에서 schema/table 정보 추출
  3. MindsDB 또는 asyncpg로 COUNT + SELECT 실행
  4. 컬럼 타입 추론 후 반환
"""
from __future__ import annotations

import re
import logging
from typing import Any

from app.services.mindsdb_client import mindsdb_client, MindsDBUnavailableError

logger = logging.getLogger("axiom.weaver.instance_fetcher")

# SQL Identifier 검증 — injection 방지
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,62}$")


def _validate_identifier(name: str) -> str:
    """SQL 식별자를 검증한다. 유효하지 않으면 ValueError."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"유효하지 않은 SQL 식별자: '{name}'")
    return name


def _infer_column_type(value: Any) -> str:
    """Python 값에서 컬럼 타입을 추론한다."""
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    val_str = str(value)
    # 날짜 패턴 감지
    if re.match(r"^\d{4}-\d{2}-\d{2}", val_str):
        return "date"
    return "text"


class InstanceFetcherService:
    """온톨로지 노드에 바인딩된 테이블의 데이터를 프리뷰한다."""

    async def fetch_sample_data(
        self,
        node_id: str,
        limit: int = 50,
        schema_name: str = "",
        table_name: str = "",
    ) -> dict[str, Any]:
        """노드 바인딩 테이블의 샘플 데이터를 조회한다.

        schema_name/table_name이 빈 문자열이면 Synapse에서
        노드의 dataSourceSchema 정보를 조회하여 자동 추론한다.

        Returns:
            { total_count, columns, column_types, preview, table_name, schema_name }
        """
        # 테이블 정보 결정
        if not table_name:
            # 향후: Synapse API로 노드의 dataSourceSchema 조회
            # 현재: node_id를 테이블명으로 간주 (폴백)
            table_name = node_id
            logger.debug("instance_fetcher_fallback", node_id=node_id, msg="테이블명으로 node_id 사용")

        _validate_identifier(table_name)
        if schema_name:
            _validate_identifier(schema_name)

        fqn = f'"{schema_name}"."{table_name}"' if schema_name else f'"{table_name}"'

        try:
            # 건수 조회
            count_data = await mindsdb_client.execute_query(
                f"SELECT COUNT(*) AS cnt FROM {fqn}"
            )
            total_count = self._extract_count(count_data)

            # 프리뷰 데이터 조회
            preview_data = await mindsdb_client.execute_query(
                f"SELECT * FROM {fqn} LIMIT {limit}"
            )
            rows = self._extract_rows(preview_data)
            columns = self._extract_column_names(preview_data)

            # 컬럼 타입 추론 (첫 번째 행 기반)
            column_types = {}
            if rows:
                for col in columns:
                    column_types[col] = _infer_column_type(rows[0].get(col))

            return {
                "total_count": total_count,
                "columns": columns,
                "column_types": column_types,
                "preview": rows,
                "table_name": table_name,
                "schema_name": schema_name,
            }

        except MindsDBUnavailableError as e:
            logger.warning("mindsdb_unavailable", node_id=node_id, error=str(e))
            return {
                "total_count": 0,
                "columns": [],
                "column_types": {},
                "preview": [],
                "table_name": table_name,
                "schema_name": schema_name,
                "error": "MindsDB 연결 불가",
            }

    async def fetch_instances(
        self,
        node_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """페이지네이션 기반 인스턴스 조회.

        fetch_sample_data와 동일하되 OFFSET 지원.
        """
        table_name = node_id
        _validate_identifier(table_name)
        fqn = f'"{table_name}"'

        try:
            count_data = await mindsdb_client.execute_query(
                f"SELECT COUNT(*) AS cnt FROM {fqn}"
            )
            total_count = self._extract_count(count_data)

            preview_data = await mindsdb_client.execute_query(
                f"SELECT * FROM {fqn} LIMIT {limit} OFFSET {offset}"
            )
            rows = self._extract_rows(preview_data)
            columns = self._extract_column_names(preview_data)

            column_types = {}
            if rows:
                for col in columns:
                    column_types[col] = _infer_column_type(rows[0].get(col))

            return {
                "total_count": total_count,
                "columns": columns,
                "column_types": column_types,
                "data": rows,
                "offset": offset,
                "limit": limit,
                "has_more": offset + limit < total_count,
            }

        except MindsDBUnavailableError as e:
            logger.warning("mindsdb_unavailable", node_id=node_id, error=str(e))
            return {
                "total_count": 0,
                "columns": [],
                "column_types": {},
                "data": [],
                "offset": offset,
                "limit": limit,
                "has_more": False,
                "error": "MindsDB 연결 불가",
            }

    # ── 헬퍼 함수 ──

    @staticmethod
    def _extract_count(data: dict) -> int:
        """COUNT 쿼리 결과에서 건수를 추출한다."""
        rows = data.get("data", [])
        if rows:
            row = rows[0]
            if isinstance(row, dict):
                return int(next(iter(row.values()), 0))
            if isinstance(row, (list, tuple)):
                return int(row[0]) if row else 0
        return 0

    @staticmethod
    def _extract_column_names(data: dict) -> list[str]:
        """쿼리 결과에서 컬럼명 추출."""
        if "column_names" in data:
            return data["column_names"]
        rows = data.get("data", [])
        if rows and isinstance(rows[0], dict):
            return list(rows[0].keys())
        return []

    @staticmethod
    def _extract_rows(data: dict) -> list[dict[str, Any]]:
        """쿼리 결과에서 행 데이터 추출."""
        rows = data.get("data", [])
        if rows and isinstance(rows[0], dict):
            return rows
        col_names = data.get("column_names", [])
        if col_names and rows:
            return [
                dict(zip(col_names, row))
                for row in rows
                if isinstance(row, (list, tuple))
            ]
        return []
