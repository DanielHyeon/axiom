"""AI 큐브 생성 서비스 -- LLM으로 Mondrian XML 또는 DDL을 생성한다.

generate_cube_xml: 자연어 설명 -> Mondrian XML 스키마
generate_ddl: 큐브 설명 -> PostgreSQL DDL + 샘플 INSERT
"""
from __future__ import annotations

import re

import structlog

from app.services.llm_client import generate_text, LLM_AVAILABLE

logger = structlog.get_logger(__name__)

# ── Mondrian XML 생성용 시스템 프롬프트 ──
CUBE_GENERATION_SYSTEM = """You are an expert OLAP data architect.
Given a user's natural language description, generate a complete Mondrian XML schema.

RULES:
1. Output ONLY valid Mondrian XML (no markdown, no explanations)
2. Include <Schema>, <Cube>, <Table>, <Dimension>, <Hierarchy>, <Level>, <Measure>
3. Use realistic column names that match the described domain
4. Include appropriate aggregators (sum, count, avg, min, max)
5. Define foreign keys on dimensions
6. Use "dw" as the default schema prefix
7. Level columns should be lowercase_snake_case
"""

# ── DDL 생성용 시스템 프롬프트 ──
DDL_GENERATION_SYSTEM = """You are an expert PostgreSQL database architect.
Given a Mondrian cube schema description, generate PostgreSQL DDL statements.

RULES:
1. Output ONLY valid PostgreSQL SQL (no markdown, no explanations)
2. Create dimension tables first (no FK dependencies), then fact table last
3. All tables should be in the "dw" schema
4. Include PRIMARY KEY, FOREIGN KEY constraints
5. Include CREATE INDEX statements for FK columns
6. Add realistic sample INSERT statements (at least 10 rows per table)
7. Use appropriate data types (INTEGER, VARCHAR, NUMERIC, DATE, TIMESTAMP)
"""


def _strip_code_fences(text: str, lang: str = "") -> str:
    """Markdown 코드 블록(```lang ... ```)을 제거한다."""
    pattern = rf'^```(?:{lang})?\s*\n?' if lang else r'^```\w*\s*\n?'
    cleaned = re.sub(pattern, '', text, flags=re.MULTILINE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()


async def generate_cube_xml(prompt: str) -> dict:
    """자연어 설명에서 Mondrian XML을 생성한다.

    Args:
        prompt: 큐브를 설명하는 자연어 (예: "월별 매출 분석 큐브")

    Returns:
        {"xml": str, "success": bool, "message": str}
    """
    if not LLM_AVAILABLE:
        return {
            "xml": "",
            "success": False,
            "message": "OPENAI_API_KEY가 설정되지 않았습니다",
        }

    raw = await generate_text(CUBE_GENERATION_SYSTEM, prompt, max_tokens=4096)
    if not raw:
        return {
            "xml": "",
            "success": False,
            "message": "LLM 응답이 비어있습니다",
        }

    # Markdown 코드 블록 제거 (```xml ... ```)
    xml_content = _strip_code_fences(raw, lang="xml")

    logger.info("ai_cube_xml_generated", xml_length=len(xml_content))
    return {
        "xml": xml_content,
        "success": True,
        "message": "큐브 XML 생성 완료",
    }


async def generate_ddl(
    cube_description: str,
    include_sample: bool = True,
    sample_rows: int = 10,
) -> dict:
    """큐브 설명에서 PostgreSQL DDL + 샘플 데이터를 생성한다.

    Args:
        cube_description: 큐브/테이블 구조를 설명하는 텍스트
        include_sample: 샘플 INSERT문 포함 여부
        sample_rows: 테이블당 샘플 행 수

    Returns:
        {"sql": str, "success": bool, "message": str}
    """
    if not LLM_AVAILABLE:
        return {
            "sql": "",
            "success": False,
            "message": "OPENAI_API_KEY가 설정되지 않았습니다",
        }

    # 샘플 데이터 요청을 프롬프트에 추가
    sample_clause = (
        f"\nGenerate {sample_rows} realistic sample INSERT rows per table."
        if include_sample
        else ""
    )
    user_prompt = f"{cube_description}{sample_clause}"

    raw = await generate_text(DDL_GENERATION_SYSTEM, user_prompt, max_tokens=8192)
    if not raw:
        return {
            "sql": "",
            "success": False,
            "message": "LLM 응답이 비어있습니다",
        }

    # Markdown 코드 블록 제거 (```sql ... ```)
    sql_content = _strip_code_fences(raw, lang="sql")

    logger.info("ai_ddl_generated", sql_length=len(sql_content))
    return {
        "sql": sql_content,
        "success": True,
        "message": "DDL 생성 완료",
    }
