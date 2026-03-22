"""BehaviorModel 실행 결과 PostgreSQL 저장 서비스.

KAIR ontology_behavior.py의 save-result-to-table 기능을 서비스 레이어로 분리.
동적으로 테이블을 생성하고 실행 결과를 INSERT 한다.
"""
from __future__ import annotations

import re
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# SQL Identifier 검증 — Cypher/SQL injection 방지
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _validate_identifier(name: str) -> str:
    """SQL 식별자를 검증한다. 유효하지 않으면 ValueError를 발생시킨다."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"유효하지 않은 SQL 식별자: '{name}'")
    return name


def _infer_pg_type(value: Any) -> str:
    """Python 값에서 PostgreSQL 컬럼 타입을 추론한다."""
    if value is None:
        return "TEXT"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE PRECISION"
    return "TEXT"


class ResultPersister:
    """BehaviorModel 실행 결과를 PostgreSQL에 동적 저장한다.

    테이블이 없으면 첫 번째 행의 키/타입으로 자동 생성하고,
    모든 행을 executemany로 배치 삽입한다.
    """

    async def save(
        self,
        table_name: str,
        data: list[dict[str, Any]],
        schema_name: str = "public",
    ) -> dict[str, Any]:
        """실행 결과를 PostgreSQL 테이블에 저장한다.

        Args:
            table_name: 대상 테이블 이름 (자동 생성)
            data: 저장할 행 목록 (dict 리스트)
            schema_name: 대상 스키마 (기본: public)

        Returns:
            { success, table_name, schema_name, rows_inserted } dict
        """
        if not data:
            return {
                "success": False,
                "error": "저장할 데이터가 없습니다.",
                "rows_inserted": 0,
            }

        # 식별자 검증
        safe_table = _validate_identifier(table_name.replace(" ", "_"))
        safe_schema = _validate_identifier(schema_name)

        try:
            import asyncpg
        except ImportError:
            return {
                "success": False,
                "error": "asyncpg 패키지가 설치되지 않았습니다.",
                "rows_inserted": 0,
            }

        # DATABASE_URL에서 연결 정보 파싱
        conn = await self._get_connection()
        if conn is None:
            return {
                "success": False,
                "error": "PostgreSQL 연결 실패",
                "rows_inserted": 0,
            }

        try:
            # 첫 번째 행으로 스키마 추론 — 컬럼명도 SQL injection 방지
            sample_row = data[0]
            columns = list(sample_row.keys())
            for col in columns:
                _validate_identifier(col)

            # CREATE TABLE IF NOT EXISTS
            column_defs = []
            for col in columns:
                col_type = _infer_pg_type(sample_row.get(col))
                safe_col = f'"{col}"'
                column_defs.append(f"{safe_col} {col_type}")

            create_sql = (
                f'CREATE TABLE IF NOT EXISTS "{safe_schema}"."{safe_table}" '
                f'(id SERIAL PRIMARY KEY, {", ".join(column_defs)}, '
                f"created_at TIMESTAMP DEFAULT NOW())"
            )
            await conn.execute(create_sql)

            # 배치 INSERT
            cols_quoted = [f'"{c}"' for c in columns]
            placeholders = [f"${i + 1}" for i in range(len(columns))]
            insert_sql = (
                f'INSERT INTO "{safe_schema}"."{safe_table}" '
                f'({", ".join(cols_quoted)}) '
                f'VALUES ({", ".join(placeholders)})'
            )

            # executemany 대신 개별 실행 (타입 불일치 행 스킵 방지)
            rows_inserted = 0
            for row in data:
                values = [row.get(c) for c in columns]
                try:
                    await conn.execute(insert_sql, *values)
                    rows_inserted += 1
                except Exception as row_err:
                    logger.warning(
                        "row_insert_skipped",
                        table=safe_table,
                        error=str(row_err),
                    )

            logger.info(
                "result_persisted",
                schema=safe_schema,
                table=safe_table,
                rows=rows_inserted,
                total=len(data),
            )

            return {
                "success": True,
                "schema_name": safe_schema,
                "table_name": safe_table,
                "rows_inserted": rows_inserted,
                "message": f"{rows_inserted}개 행이 저장되었습니다.",
            }

        except Exception as e:
            logger.error("result_persist_error", error=str(e), table=safe_table)
            return {
                "success": False,
                "error": f"테이블 저장 오류: {e}",
                "rows_inserted": 0,
            }
        finally:
            await conn.close()

    @staticmethod
    async def _get_connection():
        """settings의 DATABASE_URL로부터 asyncpg 연결을 얻는다."""
        import asyncpg

        db_url = settings.SCHEMA_EDIT_DATABASE_URL
        # postgresql+asyncpg:// → postgresql:// 변환
        dsn = db_url.replace("postgresql+asyncpg://", "postgresql://")
        try:
            return await asyncpg.connect(dsn)
        except Exception as e:
            logger.error("pg_connection_failed", error=str(e))
            return None
