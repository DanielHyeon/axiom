"""LLM 기반 테이블 리랭킹 서비스.

KAIR text2sql의 table_rerank_generator를 Axiom 패턴으로 이식.
그래프 검색으로 후보 테이블을 찾은 후, LLM으로 관련성을 재평가하여
최적의 테이블 순서를 결정한다.

핵심 가치:
  - 그래프 검색(벡터+키워드)의 recall은 높지만 precision이 낮음
  - LLM 리랭킹으로 precision을 높여 SQL 생성 품질 향상
  - 불필요한 테이블을 제거하여 SQL 복잡도 감소
"""
from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.core.llm_factory import llm_factory

logger = structlog.get_logger(__name__)

_RERANK_SYSTEM_PROMPT = """당신은 데이터베이스 전문가입니다.
사용자 질문에 가장 관련 있는 테이블을 순서대로 평가하세요.
각 테이블에 대해 관련성 점수(0.0~1.0)와 이유를 JSON 배열로 반환하세요.
0.5 미만인 테이블은 제외하세요.

출력 형식:
[{"table": "테이블명", "score": 0.9, "reason": "이유"}]
"""


class RankedTable(BaseModel):
    """리랭킹된 테이블 정보."""
    table: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""


async def rerank_tables(
    question: str,
    candidate_tables: list[dict[str, Any]],
    top_k: int = 5,
    min_score: float = 0.5,
) -> list[RankedTable]:
    """후보 테이블을 LLM으로 리랭킹한다.

    Args:
        question: 사용자 질문
        candidate_tables: 그래프 검색 결과 (name, columns, description 등)
        top_k: 반환할 최대 테이블 수
        min_score: 최소 관련성 점수 (미만은 제외)

    Returns:
        관련성 점수 내림차순으로 정렬된 테이블 리스트
    """
    if not candidate_tables:
        return []

    # 테이블 정보를 간결하게 요약
    table_summaries = []
    for t in candidate_tables[:20]:  # LLM 컨텍스트 제한
        name = t.get("name", "unknown")
        cols = t.get("columns", [])
        desc = t.get("description", "")
        col_names = [c.get("name", "") for c in cols[:10]] if isinstance(cols, list) else []
        table_summaries.append(
            f"- {name}: {desc or '(설명 없음)'} | 컬럼: {', '.join(col_names)}"
        )

    prompt = f"""질문: {question}

후보 테이블:
{chr(10).join(table_summaries)}

각 테이블의 관련성을 평가하세요."""

    try:
        raw = await llm_factory.generate(
            _RERANK_SYSTEM_PROMPT + "\n\n" + prompt,
            temperature=0.1,
        )
        raw = (raw or "").strip()

        # JSON 배열 추출
        if "[" in raw:
            json_str = raw[raw.index("["):raw.rindex("]") + 1]
            items = json.loads(json_str)
        else:
            logger.warning("rerank_no_json", raw_len=len(raw))
            # LLM이 JSON을 반환하지 않으면 원래 순서 유지
            return [
                RankedTable(table=t.get("name", ""), score=0.7, reason="리랭킹 실패 — 원래 순서 유지")
                for t in candidate_tables[:top_k]
            ]

        ranked = []
        for item in items:
            if isinstance(item, dict) and item.get("score", 0) >= min_score:
                ranked.append(RankedTable(
                    table=item.get("table", ""),
                    score=item.get("score", 0.0),
                    reason=item.get("reason", ""),
                ))

        # 점수 내림차순 정렬
        ranked.sort(key=lambda x: x.score, reverse=True)
        logger.info(
            "tables_reranked",
            input_count=len(candidate_tables),
            output_count=len(ranked[:top_k]),
        )
        return ranked[:top_k]

    except Exception as e:
        logger.warning("rerank_failed", error=str(e))
        # 실패 시 원래 순서 유지
        return [
            RankedTable(table=t.get("name", ""), score=0.7, reason="리랭킹 실패")
            for t in candidate_tables[:top_k]
        ]
