"""탐색형 NL2SQL 워크플로 -- 큐브 컨텍스트 기반 자연어 -> SQL 변환.

KAIR의 LangGraph 5노드 워크플로를 참조하되,
langgraph 미설치 시에도 동작하는 순차 파이프라인으로 구현한다.

파이프라인 단계:
  1. load_metadata  -- 큐브 스키마 설명 로드
  2. generate_sql   -- LLM으로 SQL 생성
  3. validate_sql   -- 금지 키워드 검사 + LIMIT 강제
  4. execute_query  -- asyncpg로 실행
"""
from __future__ import annotations

import re
import time

import structlog

from app.core.config import settings
from app.core.database import execute_query
from app.services.llm_client import generate_text, LLM_AVAILABLE

logger = structlog.get_logger(__name__)

# 금지 키워드 -- SELECT 전용으로 제한 (데이터 변경 차단)
FORBIDDEN_KEYWORDS = re.compile(
    r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|GRANT|REVOKE)\b',
    re.IGNORECASE,
)

# SQL 생성용 시스템 프롬프트 (schema_description, max_rows 자리표시자 포함)
NL2SQL_SYSTEM_TEMPLATE = """You are an expert SQL analyst.
Generate a PostgreSQL SELECT query based on the user's question and the given schema.

RULES:
1. Only SELECT queries - NO modifications (INSERT, UPDATE, DELETE, DROP, etc.)
2. Use only tables and columns from the provided schema
3. Always add LIMIT {max_rows}
4. Use appropriate JOINs based on foreign key relationships
5. Include GROUP BY for aggregation queries
6. Return ONLY the SQL query, no explanations

SCHEMA:
{schema_description}
"""


def _strip_sql_fences(text: str) -> str:
    """Markdown ```sql ... ``` 코드 블록을 제거한다."""
    cleaned = re.sub(r'^```(?:sql)?\s*\n?', '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _strip_sql_comments(sql: str) -> str:
    """SQL 주석을 제거한다 (-- 라인 주석, /* */ 블록 주석).

    주석 안에 금지 키워드를 숨기는 우회 공격을 방지한다.
    """
    # /* ... */ 블록 주석 제거 (중첩 미지원 — 표준 SQL과 동일)
    cleaned = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # -- 라인 주석 제거
    cleaned = re.sub(r'--[^\n]*', '', cleaned)
    return cleaned


def _validate_sql(sql: str) -> str | None:
    """SQL을 검증한다. 문제 있으면 에러 메시지, 없으면 None."""
    # 주석 제거 후 검증 — 주석 안에 숨긴 키워드 우회 방지
    stripped = _strip_sql_comments(sql)

    # 세미콜론 차단 — 다중 문(multi-statement) 실행 방지
    if ';' in stripped:
        return "세미콜론(;)은 허용되지 않습니다 — 단일 SELECT 문만 실행 가능합니다"

    # 금지 키워드 검사
    if FORBIDDEN_KEYWORDS.search(stripped):
        return "수정(INSERT/UPDATE/DELETE 등) 쿼리는 허용되지 않습니다"

    # SELECT로 시작하는지 확인
    if not stripped.strip().upper().startswith("SELECT"):
        return "SELECT 문만 실행할 수 있습니다"

    return None


async def generate_sql_only(
    question: str,
    cube_name: str,
    schema_description: str = "",
    max_rows: int = 1000,
) -> dict:
    """SQL만 생성하고 실행하지 않는다 (미리보기용).

    Returns:
        {"sql": str, "error": str | None}
    """
    if not LLM_AVAILABLE:
        return {
            "sql": "",
            "error": "OPENAI_API_KEY가 설정되지 않아 NL2SQL을 사용할 수 없습니다",
        }

    # 스키마 설명이 없으면 기본값 사용
    if not schema_description:
        schema_description = (
            f"Cube: {cube_name}\n"
            f"Schema prefix: {settings.DW_SCHEMA}\n"
            "(상세 스키마는 큐브 메타데이터에서 로드)"
        )

    system = NL2SQL_SYSTEM_TEMPLATE.replace(
        "{schema_description}", schema_description
    ).replace("{max_rows}", str(max_rows))

    raw_sql = await generate_text(system, question, temperature=0.1)
    if not raw_sql:
        return {"sql": "", "error": "SQL 생성에 실패했습니다"}

    sql = _strip_sql_fences(raw_sql)

    # 검증
    validation_error = _validate_sql(sql)
    if validation_error:
        return {"sql": sql, "error": validation_error}

    # LIMIT 강제 추가
    if "LIMIT" not in sql.upper():
        sql = f"{sql}\nLIMIT {max_rows}"

    return {"sql": sql, "error": None}


async def run_nl2sql(
    question: str,
    cube_name: str,
    schema_description: str = "",
    max_rows: int = 1000,
) -> dict:
    """NL2SQL 파이프라인을 실행한다.

    4단계 순차 파이프라인:
      1. load_metadata  -- 스키마 설명 준비
      2. generate_sql   -- LLM으로 SQL 생성
      3. validate_sql   -- 안전성 검증
      4. execute_query  -- DB 실행

    Returns:
        {
            "sql": str,
            "columns": list[str],
            "rows": list[list],
            "row_count": int,
            "execution_time_ms": int,
            "error": str | None,
            "stage_failed": str | None,
        }
    """
    result = {
        "sql": "",
        "columns": [],
        "rows": [],
        "row_count": 0,
        "execution_time_ms": 0,
        "error": None,
        "stage_failed": None,
    }

    # ── 1단계: 메타데이터 로드 ──
    if not schema_description:
        schema_description = (
            f"Cube: {cube_name}\n"
            f"Schema prefix: {settings.DW_SCHEMA}\n"
            "(상세 스키마는 큐브 메타데이터에서 로드)"
        )

    # ── 2단계: SQL 생성 (LLM) ──
    if not LLM_AVAILABLE:
        result["error"] = "OPENAI_API_KEY가 설정되지 않아 NL2SQL을 사용할 수 없습니다"
        result["stage_failed"] = "generate_sql"
        return result

    system = NL2SQL_SYSTEM_TEMPLATE.replace(
        "{schema_description}", schema_description
    ).replace("{max_rows}", str(max_rows))

    raw_sql = await generate_text(system, question, temperature=0.1)
    if not raw_sql:
        result["error"] = "SQL 생성에 실패했습니다"
        result["stage_failed"] = "generate_sql"
        return result

    sql = _strip_sql_fences(raw_sql)
    result["sql"] = sql

    # ── 3단계: SQL 검증 ──
    validation_error = _validate_sql(sql)
    if validation_error:
        result["error"] = validation_error
        result["stage_failed"] = "validate_sql"
        return result

    # LIMIT 강제 추가
    if "LIMIT" not in sql.upper():
        sql = f"{sql}\nLIMIT {max_rows}"
        result["sql"] = sql

    # ── 4단계: 실행 ──
    start = time.monotonic()
    try:
        rows = await execute_query(sql, timeout=settings.QUERY_TIMEOUT_SEC)
        elapsed = int((time.monotonic() - start) * 1000)

        columns = list(rows[0].keys()) if rows else []
        result["columns"] = columns
        result["rows"] = [list(r.values()) for r in rows]
        result["row_count"] = len(rows)
        result["execution_time_ms"] = elapsed

        logger.info(
            "nl2sql_executed",
            cube=cube_name,
            rows=len(rows),
            ms=elapsed,
        )
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        result["execution_time_ms"] = elapsed
        result["error"] = "쿼리 실행 중 오류가 발생했습니다"
        result["stage_failed"] = "execute_query"
        logger.error("nl2sql_execution_failed", error=str(e), sql=sql)

    return result
