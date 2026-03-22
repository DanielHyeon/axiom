"""루브릭 기반 SQL 평가기.

KAIR text2sql의 rubric_evaluate_candidate_generator를 Axiom 패턴으로 이식.
생성된 SQL 후보를 다기준으로 점수화하여 최적 후보를 선택한다.

C-Pipeline 평가 기준 (5개 축):
  1. 의미 정합성 — 질문 의도와 SQL이 일치하는가
  2. 테이블 적절성 — 필요한 테이블만 사용하는가
  3. 조건 완전성 — WHERE/GROUP BY/ORDER BY가 올바른가
  4. 결과 형태 — SELECT 절이 질문에 맞는 컬럼을 반환하는가
  5. SQL 품질 — 불필요한 서브쿼리/JOIN 없이 간결한가
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from app.core.llm_factory import llm_factory

logger = structlog.get_logger(__name__)

# 루브릭 통과 임계값 — 이 이상이면 COMPLETE
RUBRIC_THRESHOLD = 0.75


class RubricScore(BaseModel):
    """개별 루브릭 항목 점수."""
    model_config = ConfigDict(extra="forbid")

    criterion: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class RubricResult(BaseModel):
    """루브릭 평가 전체 결과."""
    model_config = ConfigDict(extra="forbid")

    total_score: float = Field(ge=0.0, le=1.0)
    passed: bool = False
    scores: list[RubricScore] = Field(default_factory=list)
    summary: str = ""


@dataclass
class SQLCandidate:
    """SQL 후보 — 탐색 단계에서 생성된 SQL과 평가 결과."""
    sql: str
    rubric: RubricResult | None = None
    execution_result: dict[str, Any] | None = None
    rank: int = 0


_RUBRIC_SYSTEM_PROMPT = """당신은 SQL 품질 심사관입니다.
사용자 질문과 생성된 SQL을 5개 기준으로 평가하세요.

평가 기준:
1. semantic_match (의미 정합성): 질문 의도와 SQL이 일치하는가 (0.0~1.0)
2. table_usage (테이블 적절성): 필요한 테이블만 사용하는가 (0.0~1.0)
3. condition_completeness (조건 완전성): WHERE/GROUP BY/ORDER BY가 올바른가 (0.0~1.0)
4. result_shape (결과 형태): SELECT 절이 적절한 컬럼을 반환하는가 (0.0~1.0)
5. sql_quality (SQL 품질): 불필요한 복잡성 없이 간결한가 (0.0~1.0)

JSON만 출력하세요:
{
  "total_score": 0.85,
  "passed": true,
  "scores": [
    {"criterion": "semantic_match", "score": 0.9, "reason": "질문 의도에 부합"},
    {"criterion": "table_usage", "score": 0.8, "reason": "적절한 테이블 사용"},
    {"criterion": "condition_completeness", "score": 0.85, "reason": "조건 완전"},
    {"criterion": "result_shape", "score": 0.9, "reason": "결과 형태 적절"},
    {"criterion": "sql_quality", "score": 0.8, "reason": "간결한 SQL"}
  ],
  "summary": "전체적으로 양호한 SQL"
}
"""


async def evaluate_candidate(
    question: str,
    sql: str,
    available_tables: list[str] | None = None,
    execution_result: dict[str, Any] | None = None,
) -> RubricResult:
    """단일 SQL 후보를 루브릭으로 평가한다.

    Args:
        question: 사용자 질문
        sql: 평가할 SQL
        available_tables: 사용 가능한 테이블 목록 (검증용)
        execution_result: SQL 실행 결과 (있으면 정확도 향상)

    Returns:
        RubricResult — 5개 축 점수 + 통과 여부
    """
    context_parts = [f"질문: {question}", f"SQL:\n{sql}"]
    if available_tables:
        context_parts.append(f"사용 가능한 테이블: {', '.join(available_tables)}")
    if execution_result:
        row_count = execution_result.get("row_count", "unknown")
        columns = execution_result.get("columns", [])
        context_parts.append(f"실행 결과: {row_count}행, 컬럼: {columns}")

    prompt = "\n\n".join(context_parts)

    try:
        raw = await llm_factory.generate(
            _RUBRIC_SYSTEM_PROMPT + "\n\n" + prompt,
            temperature=0.1,
        )
        raw = (raw or "").strip()

        # JSON 추출
        if "{" in raw:
            json_str = raw[raw.index("{"):raw.rindex("}") + 1]
            data = json.loads(json_str)
            return RubricResult(
                total_score=data.get("total_score", 0.0),
                passed=data.get("total_score", 0.0) >= RUBRIC_THRESHOLD,
                scores=[
                    RubricScore(**s)
                    for s in data.get("scores", [])
                    if isinstance(s, dict)
                ],
                summary=data.get("summary", ""),
            )
        else:
            logger.warning("rubric_no_json", raw_len=len(raw))
            return RubricResult(total_score=0.5, passed=False, summary="루브릭 평가 실패 — JSON 없음")

    except Exception as e:
        logger.warning("rubric_evaluation_failed", error=str(e))
        return RubricResult(total_score=0.0, passed=False, summary=f"평가 오류: {e}")


async def evaluate_candidates(
    question: str,
    candidates: list[str],
    available_tables: list[str] | None = None,
) -> list[SQLCandidate]:
    """여러 SQL 후보를 루브릭으로 병렬 평가하고 순위를 매긴다.

    asyncio.gather로 N개 후보를 동시에 LLM 평가하여 지연 시간을 최소화한다.

    Args:
        question: 사용자 질문
        candidates: SQL 후보 리스트 (보통 4개)
        available_tables: 사용 가능한 테이블 목록

    Returns:
        점수 내림차순으로 정렬된 SQLCandidate 리스트
    """
    import asyncio

    # 병렬 LLM 루브릭 평가
    tasks = [evaluate_candidate(question, sql, available_tables) for sql in candidates]
    rubrics = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[SQLCandidate] = []
    for sql, rubric in zip(candidates, rubrics):
        if isinstance(rubric, Exception):
            logger.warning("rubric_gather_error", sql=sql[:50], error=str(rubric))
            rubric = RubricResult(total_score=0.0, passed=False, summary=f"평가 오류: {rubric}")
        results.append(SQLCandidate(sql=sql, rubric=rubric))

    # 점수 내림차순 정렬
    results.sort(
        key=lambda c: c.rubric.total_score if c.rubric else 0.0,
        reverse=True,
    )

    # 순위 부여
    for i, c in enumerate(results):
        c.rank = i + 1

    logger.info(
        "candidates_evaluated",
        count=len(results),
        best_score=results[0].rubric.total_score if results and results[0].rubric else 0.0,
        best_passed=results[0].rubric.passed if results and results[0].rubric else False,
    )

    return results
