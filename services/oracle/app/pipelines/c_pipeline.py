"""C-Pipeline: 탐색→수렴→탈출 3단계 SQL 생성 파이프라인.

KAIR text2sql의 ControllerConfig (C-Pipeline)을 Axiom 패턴으로 이식.
기존 ReactAgent의 단순 생성-검증 루프를 3단계 파이프라인으로 확장한다.

Phase 1 — 탐색 (Exploration):
  다양한 전략으로 N개 SQL 후보를 생성하고 루브릭으로 평가한다.
  임계값(0.75) 이상이면 COMPLETE.

Phase 2 — 수렴 (Convergence):
  Phase 1에서 통과 후보가 없으면, 가장 높은 점수의 후보를 기반으로
  LLM 자동 수정을 반복하여 품질을 높인다.

Phase 3 — 탈출 (Escape):
  수렴이 실패하면 차선 후보로 전환하여 Phase 2를 재시도한다.
  모든 후보가 실패하면 FAIL.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

import structlog

from app.core.config import settings
from app.core.llm_factory import llm_factory
from app.core.sql_guard import GuardConfig, sql_guard
from app.pipelines.hyde_generator import generate_hyde_variants
from app.pipelines.rubric_evaluator import (
    RUBRIC_THRESHOLD,
    SQLCandidate,
    evaluate_candidate,
    evaluate_candidates,
)

logger = structlog.get_logger(__name__)

# SQL 후보 생성 수 (Phase 1 탐색)
NUM_CANDIDATES = 4

# Phase 2 수렴 최대 반복
MAX_CONVERGENCE_ITERATIONS = 3

# Phase 3 탈출 시 시도할 차선 후보 수
MAX_ESCAPE_CANDIDATES = 2


@dataclass
class CPipelineResult:
    """C-Pipeline 실행 결과."""
    phase: str  # exploration, convergence, escape
    final_sql: str = ""
    final_score: float = 0.0
    passed: bool = False
    candidates: list[SQLCandidate] = field(default_factory=list)
    total_attempts: int = 0
    steps: list[dict[str, Any]] = field(default_factory=list)


def _step(phase: str, detail: str, data: dict | None = None) -> dict[str, Any]:
    """C-Pipeline 스텝 로그 항목을 생성한다."""
    return {"phase": phase, "detail": detail, **(data or {})}


class CPipeline:
    """탐색→수렴→탈출 3단계 SQL 생성 파이프라인.

    기존 ReactAgent의 단일 생성-검증 루프를 대체하며,
    다수 후보 생성 → 루브릭 평가 → 자동 수정의 고급 파이프라인을 제공한다.
    """

    async def run(
        self,
        question: str,
        table_names: list[str],
        row_limit: int = 1000,
        dialect: str = "postgres",
        conversation_context: str = "",
    ) -> CPipelineResult:
        """C-Pipeline 전체를 실행한다.

        Args:
            question: 사용자 질문
            table_names: 사용 가능한 테이블 목록
            row_limit: SQL LIMIT 값
            dialect: SQL 방언
            conversation_context: 이전 대화 이력 (프롬프트 삽입용)

        Returns:
            CPipelineResult — 최종 SQL + 점수 + 단계별 이력
        """
        result = CPipelineResult(phase="exploration")

        # ── Phase 1: 탐색 (Exploration) ──
        # N개 SQL 후보를 다양한 전략으로 생성
        candidates_sql = await self._generate_diverse_candidates(
            question, table_names, row_limit, dialect, conversation_context
        )
        result.steps.append(_step("exploration", f"{len(candidates_sql)}개 후보 생성"))

        # 루브릭 평가
        candidates = await evaluate_candidates(question, candidates_sql, table_names)
        result.candidates = candidates
        result.total_attempts = len(candidates)

        # 최고 점수 후보 확인
        if candidates and candidates[0].rubric and candidates[0].rubric.passed:
            best = candidates[0]
            result.final_sql = best.sql
            result.final_score = best.rubric.total_score
            result.passed = True
            result.steps.append(_step(
                "exploration",
                f"Phase 1 통과 — 점수 {best.rubric.total_score:.2f}",
                {"sql": best.sql},
            ))
            logger.info("c_pipeline_phase1_pass", score=best.rubric.total_score)
            return result

        # ── Phase 2: 수렴 (Convergence) ──
        result.phase = "convergence"
        if candidates:
            best = candidates[0]
            result.steps.append(_step(
                "convergence",
                f"Phase 1 미통과 — 최고 점수 {best.rubric.total_score if best.rubric else 0:.2f}, 수렴 시작",
            ))

            converged = await self._converge(
                question, best, table_names, row_limit, dialect, result
            )
            if converged:
                return result

        # ── Phase 3: 탈출 (Escape) ──
        result.phase = "escape"
        result.steps.append(_step("escape", "수렴 실패 — 차선 후보로 탈출 시도"))

        for escape_idx in range(1, min(len(candidates), MAX_ESCAPE_CANDIDATES + 1)):
            alt = candidates[escape_idx]
            result.steps.append(_step(
                "escape",
                f"차선 후보 #{escape_idx + 1} (점수 {alt.rubric.total_score if alt.rubric else 0:.2f})",
            ))
            converged = await self._converge(
                question, alt, table_names, row_limit, dialect, result
            )
            if converged:
                return result

        # 모든 시도 실패
        result.passed = False
        if candidates:
            result.final_sql = candidates[0].sql
            result.final_score = candidates[0].rubric.total_score if candidates[0].rubric else 0.0
        result.steps.append(_step("escape", "모든 후보 실패 — C-Pipeline 종료"))
        logger.warning("c_pipeline_failed", total_attempts=result.total_attempts)
        return result

    # ── Phase 1 내부: 다양한 SQL 후보 생성 ──

    async def _generate_diverse_candidates(
        self,
        question: str,
        table_names: list[str],
        row_limit: int,
        dialect: str,
        conversation_context: str,
    ) -> list[str]:
        """다양한 전략으로 N개 SQL 후보를 병렬 생성한다.

        전략 다양성 (asyncio.gather로 병렬 실행):
          - 후보 1: 기본 생성 (temperature=0.1, 정확성 우선)
          - 후보 2: 집계 관점 (GROUP BY, HAVING 강조)
          - 후보 3: 창의적 생성 (temperature=0.5, 대안적 접근)
          - 후보 4: 간결 생성 (최소 JOIN, 단순 쿼리)

        HyDE 활성화 시 가상 SQL도 후보에 포함한다.
        """
        strategies = [
            {"suffix": "", "temperature": 0.1, "hint": "정확하고 직접적인 SQL"},
            {"suffix": " 집계/그룹화 관점에서", "temperature": 0.2, "hint": "GROUP BY와 집계 함수 활용"},
            {"suffix": " 다른 관점에서", "temperature": 0.5, "hint": "대안적 접근"},
            {"suffix": " 가장 간결하게", "temperature": 0.1, "hint": "최소한의 JOIN, 단순 쿼리"},
        ]

        # 각 전략별 프롬프트 구성
        async def _gen_one(strat: dict) -> str | None:
            prompt_parts = [
                f"Generate a SELECT SQL for: {question}{strat['suffix']}",
                f"Use tables: {', '.join(table_names)}",
                f"LIMIT {row_limit}",
                f"Hint: {strat['hint']}",
                f"Dialect: {dialect}",
            ]
            if conversation_context:
                prompt_parts.append(f"\n{conversation_context}")
            prompt = ". ".join(prompt_parts)
            try:
                sql = await llm_factory.generate(prompt, temperature=strat["temperature"])
                return self._clean_sql(sql or "")
            except Exception as e:
                logger.warning("candidate_generation_failed", error=str(e))
                return None

        # 병렬 LLM 호출 — asyncio.gather로 N개 동시 생성
        tasks = [_gen_one(s) for s in strategies[:NUM_CANDIDATES]]

        # HyDE 활성화 시 가상 SQL도 병렬로 생성하여 후보에 추가
        if settings.ENABLE_HYDE:
            tasks.append(self._generate_hyde_candidate(question, dialect))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        candidates: list[str] = []
        for r in results:
            if isinstance(r, str) and r:
                candidates.append(r)
            elif isinstance(r, Exception):
                logger.warning("candidate_gather_error", error=str(r))

        # 최소 1개는 보장
        if not candidates:
            fallback = f"SELECT * FROM {table_names[0] if table_names else 'dual'} LIMIT {row_limit}"
            candidates.append(fallback)

        return candidates

    @staticmethod
    async def _generate_hyde_candidate(question: str, dialect: str) -> str | None:
        """HyDE 가상 SQL을 생성하여 후보에 추가한다."""
        try:
            variants = await generate_hyde_variants(question, dialect, count=1)
            return variants[0] if variants else None
        except Exception as e:
            logger.warning("hyde_candidate_failed", error=str(e))
            return None

    # ── Phase 2 내부: 수렴 (자동 수정 반복) ──

    async def _converge(
        self,
        question: str,
        candidate: SQLCandidate,
        table_names: list[str],
        row_limit: int,
        dialect: str,
        result: CPipelineResult,
    ) -> bool:
        """후보 SQL을 반복적으로 수정하여 루브릭 임계값을 통과시킨다.

        Returns:
            True면 수렴 성공 (result에 최종 SQL 설정됨)
        """
        current_sql = candidate.sql
        current_rubric = candidate.rubric

        for conv_iter in range(MAX_CONVERGENCE_ITERATIONS):
            result.total_attempts += 1

            # 현재 루브릭 피드백으로 SQL 수정 요청
            feedback = current_rubric.summary if current_rubric else "품질 미달"
            low_scores = [
                f"{s.criterion}({s.score:.1f}): {s.reason}"
                for s in (current_rubric.scores if current_rubric else [])
                if s.score < RUBRIC_THRESHOLD
            ]

            repair_prompt = f"""다음 SQL을 개선하세요.

질문: {question}
현재 SQL:
{current_sql}

문제점:
- 전체 피드백: {feedback}
- 낮은 점수 항목: {'; '.join(low_scores) if low_scores else '없음'}

사용 가능한 테이블: {', '.join(table_names)}
LIMIT {row_limit}. {dialect} 방언.

개선된 SQL만 출력하세요."""

            try:
                fixed = await llm_factory.generate(repair_prompt, temperature=0.2)
                fixed = self._clean_sql(fixed or "")
                if not fixed or fixed == current_sql:
                    result.steps.append(_step(
                        "convergence", f"수렴 반복 {conv_iter + 1} — 동일 SQL, 중단"
                    ))
                    break

                # 수정된 SQL 재평가
                new_rubric = await evaluate_candidate(
                    question, fixed, table_names
                )
                result.steps.append(_step(
                    "convergence",
                    f"수렴 반복 {conv_iter + 1} — 점수 {new_rubric.total_score:.2f}",
                    {"sql": fixed[:100]},
                ))

                if new_rubric.passed:
                    result.final_sql = fixed
                    result.final_score = new_rubric.total_score
                    result.passed = True
                    logger.info("c_pipeline_converged", iteration=conv_iter + 1, score=new_rubric.total_score)
                    return True

                # 수렴 진행 — 다음 반복
                current_sql = fixed
                current_rubric = new_rubric

            except Exception as e:
                logger.warning("convergence_repair_failed", error=str(e))
                break

        return False

    @staticmethod
    def _clean_sql(raw: str) -> str:
        """LLM 응답에서 SQL을 추출한다 — 마크다운 블록 제거."""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        # SELECT가 없으면 빈 문자열
        if "SELECT" not in raw.upper():
            return ""
        return raw


# 싱글톤 인스턴스
c_pipeline = CPipeline()
