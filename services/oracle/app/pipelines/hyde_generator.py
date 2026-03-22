"""HyDE (Hypothetical Document Embedding) 생성기.

KAIR text2sql의 hyde_schema_generator를 Axiom 패턴으로 이식.
사용자 질문에서 가상 SQL을 생성하여 검색 다양성을 확보한다.

원리:
  1. 질문에서 가상의 SELECT SQL을 LLM으로 생성 (테이블 추측)
  2. 가상 SQL을 임베딩하여 벡터 검색 축으로 활용
  3. 질문 벡터 + HyDE 벡터 = 다축 검색으로 recall 향상
"""
from __future__ import annotations

from typing import Any

import structlog

from app.core.llm_factory import llm_factory

logger = structlog.get_logger(__name__)

# HyDE 생성 프롬프트 — 테이블명을 추측하여 가상 SQL 생성
_HYDE_SYSTEM_PROMPT = """당신은 SQL 전문가입니다.
사용자 질문에서 가장 적합한 SELECT 쿼리를 추측하여 생성하세요.
실제 테이블명을 모르더라도 도메인 지식으로 추측하세요.
SQL만 출력하세요. 설명 없이."""


async def generate_hyde_sql(question: str, dialect: str = "postgres") -> str | None:
    """질문에서 가상 SQL을 생성한다 (HyDE).

    가상 SQL은 실행되지 않으며, 임베딩 검색용으로만 사용된다.
    실패 시 None을 반환한다.
    """
    prompt = f"[DBMS: {dialect}] 다음 질문에 대한 SELECT 쿼리를 추측하세요:\n{question}"
    try:
        result = await llm_factory.generate(prompt, temperature=0.3)
        sql = (result or "").strip()
        # 마크다운 코드 블록 제거
        if sql.startswith("```"):
            lines = sql.split("\n")
            sql = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            )
        if not sql or "SELECT" not in sql.upper():
            return None
        logger.debug("hyde_sql_generated", question_len=len(question), sql_len=len(sql))
        return sql.strip()
    except Exception as e:
        logger.warning("hyde_generation_failed", error=str(e))
        return None


async def generate_hyde_variants(
    question: str, dialect: str = "postgres", count: int = 2
) -> list[str]:
    """다양한 관점의 가상 SQL을 여러 개 생성한다.

    서로 다른 테이블/조인 전략을 사용하는 가상 SQL을 생성하여
    벡터 검색의 다양성을 극대화한다.

    Args:
        question: 사용자 질문
        dialect: SQL 방언
        count: 생성할 가상 SQL 수 (기본 2개)

    Returns:
        가상 SQL 문자열 리스트 (빈 리스트 가능)
    """
    results: list[str] = []
    for i in range(count):
        suffix = f" (관점 {i + 1}: {'집계 쿼리' if i == 0 else '상세 조회'})"
        sql = await generate_hyde_sql(question + suffix, dialect)
        if sql:
            results.append(sql)
    return results
