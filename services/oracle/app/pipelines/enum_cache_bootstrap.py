"""Enum 캐시 부트스트랩 모듈 (#8 P1-1).

서비스 시작 시 PostgreSQL의 VARCHAR/TEXT 컬럼 중
저카디널리티(100개 이하 고유값) 컬럼의 DISTINCT 값을 조회하여
인메모리 캐시에 저장한다.

캐시된 enum 값은 #7 서브스키마 DDL에 힌트로 포함되어
LLM이 정확한 필터 값을 생성하도록 돕는다.
예: region 컬럼의 값이 '서울', '부산', '대전'임을 알려줌.

Major 리뷰 반영: asyncio.to_thread()로 블로킹 I/O 래핑.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger()


# ──────────────────────────────────────────────────────────────
# 캐시 대상 컬럼 판별 패턴
# ──────────────────────────────────────────────────────────────

# varchar/text/character 타입만 대상
_TEXT_DTYPE_RE = re.compile(r"(char|text|varchar)", re.IGNORECASE)


@dataclass(frozen=True)
class EnumCacheResult:
    """enum 캐시 부트스트랩 실행 결과 통계."""
    scanned: int                     # information_schema에서 조회한 전체 컬럼 수
    cached: int                      # 캐시에 저장된 컬럼 수
    skipped_high_cardinality: int    # 고유값 100개 초과로 건너뛴 컬럼 수
    skipped_empty: int               # 값이 없어서 건너뛴 컬럼 수
    errors: int                      # 조회 중 오류 발생 횟수
    elapsed_ms: float                # 전체 실행 시간 (밀리초)


# ──────────────────────────────────────────────────────────────
# 인메모리 캐시 저장소 (서비스 수명 동안 유지)
# ──────────────────────────────────────────────────────────────
_enum_cache_store: dict[str, dict[str, Any]] = {}


def _should_cache_column(col_name: str, dtype: str) -> bool:
    """컬럼 이름이나 타입 패턴으로 enum 캐시 대상인지 판별한다.

    varchar/text/character 타입인 모든 컬럼을 대상으로 한다.
    고카디널리티 여부는 DISTINCT 쿼리 결과로 판단한다.
    """
    return bool(_TEXT_DTYPE_RE.search(dtype))


def _run_sync(
    db_url: str,
    target_schema: str,
    max_columns: int,
    max_values: int,
) -> EnumCacheResult:
    """동기 블로킹 I/O: PostgreSQL에서 enum 후보 컬럼을 조회한다.

    asyncio.to_thread()로 래핑되어 이벤트 루프를 차단하지 않는다.
    """
    import psycopg2

    started = time.perf_counter()
    cached = 0
    skipped_hi = 0
    skipped_empty = 0
    errors = 0

    try:
        conn = psycopg2.connect(db_url)
        conn.set_session(readonly=True, autocommit=True)
        cur = conn.cursor()
    except Exception as exc:
        logger.warning("enum_cache_db_connect_failed", error=str(exc))
        return EnumCacheResult(
            scanned=0, cached=0, skipped_high_cardinality=0,
            skipped_empty=0, errors=1,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )

    try:
        # Step 1: information_schema에서 text-like 컬럼 목록 조회
        cur.execute("""
            SELECT table_schema, table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s
              AND data_type IN ('character varying', 'text', 'character')
            ORDER BY table_schema, table_name, ordinal_position
            LIMIT %s
        """, (target_schema, max_columns))

        candidates = cur.fetchall()

        for (schema, table, column, dtype) in candidates:
            # 타입 패턴으로 enum 후보 필터링
            if not _should_cache_column(column, dtype):
                continue

            try:
                # Step 2: 각 컬럼의 DISTINCT 값 조회
                # LIMIT max_values+1: 초과 시 고카디널리티로 판단
                # psycopg2.sql로 안전한 식별자 조합 (Cypher injection 방지)
                from psycopg2 import sql as psql
                query = psql.SQL(
                    "SELECT {col} AS value, COUNT(*) AS cnt "
                    "FROM {schema}.{table} "
                    "WHERE {col} IS NOT NULL "
                    "GROUP BY {col} "
                    "ORDER BY cnt DESC "
                    "LIMIT %s"
                ).format(
                    col=psql.Identifier(column),
                    schema=psql.Identifier(schema),
                    table=psql.Identifier(table),
                )
                cur.execute(query, (max_values + 1,))
                rows = cur.fetchall()

                if not rows:
                    skipped_empty += 1
                    continue

                # 고유값이 max_values보다 많으면 enum이 아님
                if len(rows) > max_values:
                    skipped_hi += 1
                    continue

                # Step 3: enum_values 리스트 생성
                enum_values = [
                    {"value": str(r[0]), "count": int(r[1])}
                    for r in rows if r[0] is not None
                ]

                if not enum_values:
                    skipped_empty += 1
                    continue

                # Step 4: 인메모리 캐시에 저장
                cache_key = f"{schema}.{table}.{column}".lower()
                _enum_cache_store[cache_key] = {
                    "values": enum_values,
                    "cardinality": len(enum_values),
                }
                cached += 1

            except Exception as exc:
                errors += 1
                if errors <= 3:
                    logger.warning(
                        "enum_cache_column_error",
                        table=f"{schema}.{table}",
                        column=column,
                        error=str(exc),
                    )

    finally:
        cur.close()
        conn.close()

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    result = EnumCacheResult(
        scanned=len(candidates),
        cached=cached,
        skipped_high_cardinality=skipped_hi,
        skipped_empty=skipped_empty,
        errors=errors,
        elapsed_ms=elapsed_ms,
    )
    logger.info(
        "enum_cache_bootstrap_done",
        cached=cached,
        scanned=len(candidates),
        elapsed_ms=round(elapsed_ms, 1),
    )
    return result


class EnumCacheBootstrap:
    """서비스 시작 시 enum 캐시를 초기화하는 부트스트래퍼.

    저카디널리티 VARCHAR 컬럼의 DISTINCT 값을 조회하여
    인메모리 캐시에 저장한다. LLM이 정확한 값을 생성하도록 돕는다.
    """

    async def run(self, datasource_id: str = "") -> EnumCacheResult | None:
        """enum 캐시 부트스트랩을 비동기로 실행한다.

        내부적으로 asyncio.to_thread()를 사용하여
        psycopg2 블로킹 I/O가 이벤트 루프를 차단하지 않도록 한다.
        (Major 리뷰 반영)

        Returns:
            EnumCacheResult 또는 비활성화 시 None
        """
        if not settings.ENUM_CACHE_ENABLED:
            logger.info("enum_cache_disabled")
            return None

        logger.info("enum_cache_bootstrap_started", datasource_id=datasource_id)

        # 블로킹 I/O를 별도 스레드에서 실행 (이벤트 루프 보호)
        result = await asyncio.to_thread(
            _run_sync,
            db_url=settings.QUERY_HISTORY_DATABASE_URL,
            target_schema=settings.ENUM_CACHE_TARGET_SCHEMA,
            max_columns=settings.ENUM_CACHE_MAX_COLUMNS,
            max_values=settings.ENUM_CACHE_MAX_VALUES,
        )

        return result


# ──────────────────────────────────────────────────────────────
# 런타임 캐시 조회 API
# ──────────────────────────────────────────────────────────────

def get_enum_values(fqn: str) -> list[dict] | None:
    """특정 컬럼의 캐시된 enum 값을 조회한다.

    Args:
        fqn: "schema.table.column" 형식 (예: "public.sales.region")

    Returns:
        [{"value": "서울", "count": 25}, ...] 또는 캐시 미스 시 None
    """
    entry = _enum_cache_store.get(fqn.lower())
    return entry["values"] if entry else None


def get_enum_hints_for_tables(table_names: list[str], schema: str = "public") -> list[dict]:
    """지정된 테이블들의 enum 힌트 목록을 반환한다.

    #7 서브스키마와 연동: SubSchemaContext.enum_hints에 포함된다.

    Args:
        table_names: 테이블 이름 목록 (예: ["sales", "operations"])
        schema: 스키마 이름 (기본: "public")

    Returns:
        [{"table": "sales", "column": "region", "values": ["서울", "부산"], "cardinality": 5}, ...]
    """
    hints: list[dict] = []

    # 캐시에서 테이블별 컬럼 역인덱스 구성
    prefix_map: dict[str, list[tuple[str, list[dict]]]] = {}
    for fqn, entry in _enum_cache_store.items():
        parts = fqn.split(".")
        if len(parts) == 3:
            tbl = parts[1]
            prefix_map.setdefault(tbl, []).append(
                (parts[2], entry["values"])
            )

    # 요청된 테이블의 enum 힌트 수집
    for tbl in table_names:
        tbl_lower = tbl.lower()
        for col, values in prefix_map.get(tbl_lower, []):
            hints.append({
                "table": tbl,
                "column": col,
                "values": [v["value"] for v in values[:10]],
                "cardinality": len(values),
            })

    return hints


def get_cache_stats() -> dict[str, int]:
    """현재 캐시 상태 통계를 반환한다 (디버깅/모니터링용)."""
    return {
        "total_columns": len(_enum_cache_store),
        "total_values": sum(
            entry["cardinality"] for entry in _enum_cache_store.values()
        ),
    }


# 싱글톤 인스턴스 (기존 import 호환성 유지)
enum_cache_bootstrap = EnumCacheBootstrap()
