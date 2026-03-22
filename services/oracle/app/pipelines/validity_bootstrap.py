"""Text2SQL 유효성 플래그 부트스트래핑 서비스 (#P4-16).

서비스 시작 시 또는 수동 트리거로 빈 테이블/null-only 컬럼을 감지하여
Synapse의 Neo4j 메타데이터에 text_to_sql_is_valid = false 플래그를 설정한다.

이 플래그가 false인 테이블/컬럼은 NL2SQL RAG 검색에서 제외되어
불필요한 후보 테이블을 줄이고 SQL 생성 품질을 높인다.

흐름:
1. PostgreSQL pg_stat_user_tables에서 테이블별 행수 추정 (전체 스캔 없이 빠르게)
2. 행수 0인 테이블 → text_to_sql_is_valid = false
3. pg_stats에서 null_frac = 1.0인 컬럼 → text_to_sql_is_valid = false
4. Synapse API로 플래그 업데이트 (HTTP 호출)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────
# 유효성 검사 결과 데이터 모델
# ──────────────────────────────────────────────────────────────


@dataclass
class ValidityReport:
    """유효성 부트스트랩 실행 결과 보고서.

    어떤 테이블/컬럼이 invalid로 마킹되었는지,
    전체 스캔 범위와 소요 시간을 기록한다.
    """

    # 빈 테이블로 판정된 테이블 목록 (예: ["public.empty_table"])
    invalid_tables: list[str] = field(default_factory=list)
    # null-only 컬럼으로 판정된 컬럼 목록 (예: ["public.sales.unused_col"])
    invalid_columns: list[str] = field(default_factory=list)
    # 스캔한 전체 테이블 수
    scanned_tables: int = 0
    # 스캔한 전체 컬럼 수
    scanned_columns: int = 0
    # Synapse API 업데이트 성공/실패 카운트
    synapse_updated: int = 0
    synapse_errors: int = 0
    # 전체 실행 시간 (밀리초)
    elapsed_ms: float = 0.0


# ──────────────────────────────────────────────────────────────
# 최근 보고서 저장소 (인메모리, 서비스 수명 동안 유지)
# ──────────────────────────────────────────────────────────────
_last_report: ValidityReport | None = None


def get_last_report() -> ValidityReport | None:
    """마지막 유효성 검사 보고서를 반환한다. 한번도 실행 안 했으면 None."""
    return _last_report


# ──────────────────────────────────────────────────────────────
# PostgreSQL 통계 조회 (동기 — asyncio.to_thread 래핑)
# ──────────────────────────────────────────────────────────────


def _scan_empty_tables_sync(
    db_url: str,
    target_schema: str,
) -> tuple[list[str], list[str], int]:
    """pg_stat_user_tables에서 행수 추정이 0인 빈 테이블을 찾는다.

    Returns:
        (빈_테이블_목록, 유효_테이블_목록, 전체_테이블_수)
    """
    import psycopg2

    empty_tables: list[str] = []
    valid_tables: list[str] = []

    try:
        conn = psycopg2.connect(db_url)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
    except Exception as exc:
        logger.warning("validity_db_connect_failed", error=str(exc))
        return [], [], 0

    try:
        # pg_stat_user_tables의 n_live_tup은 VACUUM/ANALYZE 이후 추정 행수
        # 정확하진 않지만 빈 테이블 판별에는 충분하다
        cur.execute("""
            SELECT schemaname, relname, n_live_tup
            FROM pg_stat_user_tables
            WHERE schemaname = %s
            ORDER BY relname
        """, (target_schema,))

        rows = cur.fetchall()
        for schema, table, n_live_tup in rows:
            fqn = f"{schema}.{table}"
            if n_live_tup == 0:
                empty_tables.append(fqn)
            else:
                valid_tables.append(table)

        return empty_tables, valid_tables, len(rows)

    finally:
        cur.close()
        conn.close()


def _scan_null_only_columns_sync(
    db_url: str,
    target_schema: str,
    valid_tables: list[str],
) -> tuple[list[str], int]:
    """pg_stats에서 null_frac = 1.0인 (모든 값이 NULL) 컬럼을 찾는다.

    빈 테이블은 이미 invalid로 마킹했으므로 유효한 테이블만 검사한다.

    Returns:
        (null_only_컬럼_목록, 스캔한_컬럼_수)
    """
    import psycopg2

    null_only_columns: list[str] = []
    scanned = 0

    if not valid_tables:
        return [], 0

    try:
        conn = psycopg2.connect(db_url)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
    except Exception as exc:
        logger.warning("validity_db_connect_failed_columns", error=str(exc))
        return [], 0

    try:
        # pg_stats는 ANALYZE 이후 컬럼별 통계를 보관한다
        # null_frac = 1.0 → 해당 컬럼의 모든 행이 NULL
        # 참고: pg_stats에 행이 없는 컬럼은 ANALYZE 미실행 상태이므로 건너뜀
        cur.execute("""
            SELECT schemaname, tablename, attname, null_frac
            FROM pg_stats
            WHERE schemaname = %s
              AND tablename = ANY(%s)
            ORDER BY tablename, attname
        """, (target_schema, valid_tables))

        rows = cur.fetchall()
        scanned = len(rows)

        for schema, table, column, null_frac in rows:
            # null_frac은 0.0 ~ 1.0 범위의 float
            if null_frac is not None and null_frac >= 1.0:
                fqn = f"{schema}.{table}.{column}"
                null_only_columns.append(fqn)

        return null_only_columns, scanned

    finally:
        cur.close()
        conn.close()


# ──────────────────────────────────────────────────────────────
# Synapse API 플래그 업데이트
# ──────────────────────────────────────────────────────────────


async def _update_synapse_validity_flags(
    invalid_tables: list[str],
    invalid_columns: list[str],
    datasource_id: str,
    concurrency: int,
) -> tuple[int, int]:
    """Synapse API를 호출하여 text_to_sql_is_valid 플래그를 설정한다.

    동시에 concurrency개씩 병렬 호출하여 대량 업데이트를 빠르게 처리한다.

    Returns:
        (성공_횟수, 실패_횟수)
    """
    base_url = settings.SYNAPSE_API_URL.rstrip("/")
    schema_edit_base = settings.SYNAPSE_SCHEMA_EDIT_BASE
    headers = {
        "Authorization": f"Bearer {settings.SERVICE_TOKEN_ORACLE}",
        "Content-Type": "application/json",
    }

    updated = 0
    errors = 0
    semaphore = asyncio.Semaphore(concurrency)

    async def _update_one(
        client: httpx.AsyncClient,
        entity_type: str,
        fqn: str,
    ) -> bool:
        """개별 테이블/컬럼의 유효성 플래그를 업데이트한다."""
        nonlocal updated, errors
        async with semaphore:
            try:
                # Synapse schema-edit API로 메타데이터 속성 업데이트
                # 테이블: PUT /schema-edit/tables/{name}/properties
                # 컬럼: PUT /schema-edit/columns/{table}/{col}/properties
                parts = fqn.split(".")
                if entity_type == "table" and len(parts) >= 2:
                    table_name = parts[-1]
                    url = f"{base_url}{schema_edit_base}/tables/{table_name}/properties"
                elif entity_type == "column" and len(parts) >= 3:
                    table_name = parts[-2]
                    col_name = parts[-1]
                    url = f"{base_url}{schema_edit_base}/columns/{table_name}/{col_name}/properties"
                else:
                    logger.warning("validity_invalid_fqn", fqn=fqn, entity_type=entity_type)
                    return False

                payload = {
                    "properties": {
                        "text_to_sql_is_valid": False,
                    },
                    "datasource_id": datasource_id,
                }

                resp = await client.put(url, headers=headers, json=payload, timeout=10.0)
                resp.raise_for_status()
                return True

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                # Synapse API 오류는 경고만 남기고 계속 진행
                logger.warning(
                    "validity_synapse_update_failed",
                    entity_type=entity_type,
                    fqn=fqn,
                    error=str(exc),
                )
                return False

    async with httpx.AsyncClient() as client:
        # 테이블 플래그 업데이트
        table_tasks = [
            _update_one(client, "table", fqn)
            for fqn in invalid_tables
        ]
        # 컬럼 플래그 업데이트
        column_tasks = [
            _update_one(client, "column", fqn)
            for fqn in invalid_columns
        ]

        all_results = await asyncio.gather(
            *table_tasks, *column_tasks,
            return_exceptions=True,
        )

        for result in all_results:
            if isinstance(result, Exception):
                errors += 1
            elif result is True:
                updated += 1
            else:
                errors += 1

    return updated, errors


# ──────────────────────────────────────────────────────────────
# 유효성 판별 순수 함수 (테스트 용이)
# ──────────────────────────────────────────────────────────────


def classify_empty_tables(
    table_stats: list[tuple[str, str, int]],
) -> tuple[list[str], list[str]]:
    """테이블 통계에서 빈 테이블과 유효 테이블을 분류한다.

    Args:
        table_stats: [(schema, table_name, n_live_tup), ...]

    Returns:
        (빈_테이블_FQN_목록, 유효_테이블_이름_목록)
    """
    empty: list[str] = []
    valid: list[str] = []
    for schema, table, n_live_tup in table_stats:
        if n_live_tup == 0:
            empty.append(f"{schema}.{table}")
        else:
            valid.append(table)
    return empty, valid


def classify_null_only_columns(
    column_stats: list[tuple[str, str, str, float | None]],
) -> list[str]:
    """컬럼 통계에서 모든 값이 NULL인 컬럼을 분류한다.

    Args:
        column_stats: [(schema, table, column, null_frac), ...]

    Returns:
        null_only 컬럼의 FQN 목록
    """
    null_only: list[str] = []
    for schema, table, column, null_frac in column_stats:
        if null_frac is not None and null_frac >= 1.0:
            null_only.append(f"{schema}.{table}.{column}")
    return null_only


# ──────────────────────────────────────────────────────────────
# 메인 부트스트래퍼 클래스
# ──────────────────────────────────────────────────────────────


class ValidityBootstrap:
    """Text2SQL 유효성 플래그 부트스트래퍼.

    빈 테이블과 null-only 컬럼을 감지하여 Synapse 메타데이터에
    text_to_sql_is_valid = false 플래그를 설정한다.

    NL2SQL RAG 검색에서 의미 없는 후보를 제거하여
    SQL 생성 정확도를 높이는 것이 목적이다.
    """

    async def run(
        self,
        target_schema: str | None = None,
        datasource_id: str = "",
    ) -> ValidityReport:
        """유효성 부트스트랩을 실행한다.

        1단계: pg_stat_user_tables에서 빈 테이블 감지
        2단계: pg_stats에서 null-only 컬럼 감지
        3단계: Synapse API로 플래그 업데이트

        Args:
            target_schema: 스캔 대상 PostgreSQL 스키마 (기본: settings 값 사용)
            datasource_id: 데이터소스 식별자 (Synapse 업데이트 시 전달)

        Returns:
            ValidityReport — 실행 결과 보고서
        """
        global _last_report

        if not settings.VALIDITY_BOOTSTRAP_ENABLED:
            logger.info("validity_bootstrap_disabled")
            report = ValidityReport()
            _last_report = report
            return report

        schema = target_schema or settings.VALIDITY_BOOTSTRAP_TARGET_SCHEMA
        concurrency = settings.VALIDITY_BOOTSTRAP_CONCURRENCY
        started = time.perf_counter()

        logger.info(
            "validity_bootstrap_started",
            target_schema=schema,
            datasource_id=datasource_id,
        )

        # ── 1단계: 빈 테이블 감지 ──
        empty_tables, valid_tables, total_tables = await asyncio.to_thread(
            _scan_empty_tables_sync,
            db_url=settings.QUERY_HISTORY_DATABASE_URL,
            target_schema=schema,
        )

        if empty_tables:
            logger.info(
                "validity_empty_tables_found",
                count=len(empty_tables),
                tables=empty_tables[:10],  # 로그에 최대 10개만 표시
            )

        # ── 2단계: null-only 컬럼 감지 ──
        null_only_columns, total_columns = await asyncio.to_thread(
            _scan_null_only_columns_sync,
            db_url=settings.QUERY_HISTORY_DATABASE_URL,
            target_schema=schema,
            valid_tables=valid_tables,
        )

        if null_only_columns:
            logger.info(
                "validity_null_only_columns_found",
                count=len(null_only_columns),
                columns=null_only_columns[:10],
            )

        # ── 3단계: Synapse API로 플래그 업데이트 ──
        synapse_updated = 0
        synapse_errors = 0

        if empty_tables or null_only_columns:
            synapse_updated, synapse_errors = await _update_synapse_validity_flags(
                invalid_tables=empty_tables,
                invalid_columns=null_only_columns,
                datasource_id=datasource_id,
                concurrency=concurrency,
            )

        elapsed_ms = (time.perf_counter() - started) * 1000.0

        report = ValidityReport(
            invalid_tables=empty_tables,
            invalid_columns=null_only_columns,
            scanned_tables=total_tables,
            scanned_columns=total_columns,
            synapse_updated=synapse_updated,
            synapse_errors=synapse_errors,
            elapsed_ms=round(elapsed_ms, 1),
        )

        # 인메모리 저장 (GET /report 응답용)
        _last_report = report

        logger.info(
            "validity_bootstrap_done",
            invalid_tables=len(empty_tables),
            invalid_columns=len(null_only_columns),
            scanned_tables=total_tables,
            scanned_columns=total_columns,
            synapse_updated=synapse_updated,
            synapse_errors=synapse_errors,
            elapsed_ms=round(elapsed_ms, 1),
        )

        return report


# 싱글톤 인스턴스
validity_bootstrap = ValidityBootstrap()
