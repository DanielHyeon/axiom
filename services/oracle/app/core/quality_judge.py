"""LLM 기반 품질 심사기 (Quality Gate).

NL2SQL 파이프라인이 생성한 SQL의 품질을 LLM으로 심사하여
캐시 저장 여부를 결정한다.

핵심 원칙:
- Fail-closed: 파싱/호출 실패 시 무조건 REJECT
- N-라운드 심사: confidence가 애매한 구간이면 2차 심사 수행
- Pydantic strict 모델로 LLM 출력 스키마를 강제
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field

from app.core.llm_factory import llm_factory

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# 프롬프트 로딩
# ---------------------------------------------------------------------------

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
_QUALITY_GATE_PROMPT_PATH = _PROMPT_DIR / "quality_gate_prompt.md"


def _load_system_prompt() -> str:
    """품질 게이트 시스템 프롬프트를 파일에서 로딩한다."""
    try:
        return _QUALITY_GATE_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("quality_gate_prompt_not_found", path=str(_QUALITY_GATE_PROMPT_PATH))
        return "당신은 Text2SQL 결과 품질 심사관입니다. JSON만 출력하세요."


# ---------------------------------------------------------------------------
# Pydantic 모델 — LLM 출력 스키마 (추가 키 금지)
# ---------------------------------------------------------------------------


class QualityJudgeLLMOutput(BaseModel):
    """LLM이 반환해야 하는 JSON 스키마.

    extra="forbid" 설정으로 예상치 못한 키가 포함되면 파싱 실패 처리한다.
    """

    model_config = ConfigDict(extra="forbid")

    accept: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# 심사 결과 데이터클래스
# ---------------------------------------------------------------------------


@dataclass
class QualityJudgeResult:
    """품질 심사 최종 결과."""

    accept: bool = False
    confidence: float = 0.0
    reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    summary: str = ""
    parse_error: str = ""


# ---------------------------------------------------------------------------
# 유틸리티 함수
# ---------------------------------------------------------------------------


def _clamp01(value: float) -> float:
    """confidence 값을 0.0~1.0 범위로 강제한다."""
    return max(0.0, min(1.0, float(value)))


def _extract_first_json_object(text: str) -> str | None:
    """LLM 응답에서 첫 번째 JSON 객체를 추출한다.

    코드 펜스(```json ... ```)가 있으면 제거하고,
    가장 바깥쪽 { ... } 를 찾아 반환한다.
    """
    if not text:
        return None

    # 코드 펜스 제거: ```json ... ``` 또는 ``` ... ```
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.replace("```", "")

    # 가장 바깥쪽 { ... } 범위 추출
    start = cleaned.find("{")
    if start == -1:
        return None

    # 중괄호 깊이 카운팅으로 매칭되는 닫는 중괄호 찾기
    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start : i + 1]
    return None


def semantic_mismatch_reasons(question: str, sql: str) -> list[str]:
    """질문과 SQL 사이의 의미적 불일치를 감지한다.

    KAIR controller.py에서 이식한 패턴으로,
    질문에 포함된 집계/기간 키워드가 SQL에 반영되지 않은 경우를 감지한다.
    """
    reasons: list[str] = []
    uq = question.lower()
    s = sql.lower()

    # 집계 함수 불일치 감지
    if any(k in uq for k in ("평균", "average", "avg")) and "avg(" not in s:
        reasons.append("missing AVG()")

    if any(k in uq for k in ("합계", "총합", "sum", "합산")) and "sum(" not in s:
        reasons.append("missing SUM()")

    if any(k in uq for k in ("건수", "개수", "count", "횟수", "몇 건")) and "count(" not in s:
        reasons.append("missing COUNT()")

    if any(k in uq for k in ("최대", "최고", "max", "가장 높은", "가장 많은")) and "max(" not in s:
        reasons.append("missing MAX()")

    if any(k in uq for k in ("최소", "최저", "min", "가장 낮은", "가장 적은")) and "min(" not in s:
        reasons.append("missing MIN()")

    # GROUP BY 불일치 감지
    group_keywords = ("별", "그룹", "group by")
    if any(k in uq for k in group_keywords) and "group by" not in s:
        reasons.append("missing GROUP BY")

    # 정렬 관련 불일치
    if any(k in uq for k in ("순서", "정렬", "순위", "높은 순", "낮은 순")) and "order by" not in s:
        reasons.append("missing ORDER BY")

    return reasons


def preview_null_ratio(preview: dict | None) -> float:
    """preview 데이터에서 NULL 셀 비율을 계산한다.

    반환값: 0.0 (NULL 없음) ~ 1.0 (전부 NULL)
    """
    if not preview:
        return 0.0
    rows = preview.get("rows") or []
    if not rows:
        return 0.0

    total_cells = 0
    null_cells = 0
    for row in rows:
        for cell in row:
            total_cells += 1
            if cell is None:
                null_cells += 1

    if total_cells == 0:
        return 0.0
    return null_cells / total_cells


# ---------------------------------------------------------------------------
# 품질 심사기 클래스
# ---------------------------------------------------------------------------


class QualityJudge:
    """LLM 기반 N-라운드 품질 심사기.

    Round 1: 기본 검증 (SQL 문법, 테이블 존재, 컬럼 매칭)
    Round 2 (조건부): confidence가 0.55~0.85 구간에서
                     semantic mismatch 추가 검증

    사용 예시:
        judge = QualityJudge()
        result = await judge.multi_round_judge(
            question="서울 지역 매출 합계",
            sql="SELECT SUM(revenue) FROM sales WHERE region='서울'",
            row_count=1,
            execution_time_ms=45.0,
            preview={"columns": ["sum"], "rows": [[150000]], "row_count": 1},
            metadata=None,
        )
    """

    # Round 2 실행 조건: confidence가 이 구간이면 재심사
    _AMBIGUOUS_LOW = 0.55
    _AMBIGUOUS_HIGH = 0.85

    # 최종 판정 임계값
    THRESHOLD_APPROVE = 0.80
    THRESHOLD_PENDING = 0.60

    def __init__(self) -> None:
        self._system_prompt = _load_system_prompt()

    def _build_user_prompt(
        self,
        question: str,
        sql: str,
        row_count: int | None,
        execution_time_ms: float | None,
        preview: dict | None,
        metadata: dict | None,
        round_idx: int,
        *,
        extra_signals: dict | None = None,
    ) -> str:
        """LLM에 전달할 사용자 프롬프트를 JSON 형태로 구성한다."""
        signals: dict[str, Any] = {}
        if row_count is not None:
            signals["row_count"] = row_count
        if execution_time_ms is not None:
            signals["execution_time_ms"] = execution_time_ms
        if preview:
            signals["preview"] = preview
        if extra_signals:
            signals.update(extra_signals)

        payload = {
            "question": question,
            "sql": sql,
            "signals": signals,
            "round_idx": round_idx,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _parse_llm_output(self, raw: str) -> QualityJudgeResult:
        """LLM 응답을 파싱하여 QualityJudgeResult로 변환한다.

        파싱 실패 시 fail-closed: accept=False, confidence=0.0
        """
        json_str = _extract_first_json_object(raw)
        if not json_str:
            return QualityJudgeResult(
                accept=False,
                confidence=0.0,
                reasons=["LLM 응답에서 JSON을 찾을 수 없음"],
                parse_error="no_json_found",
            )

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            return QualityJudgeResult(
                accept=False,
                confidence=0.0,
                reasons=["JSON 파싱 실패"],
                parse_error=f"json_decode_error: {e}",
            )

        try:
            # Pydantic strict 모델로 검증 (추가 키 금지)
            output = QualityJudgeLLMOutput.model_validate(parsed)
        except Exception as e:
            return QualityJudgeResult(
                accept=False,
                confidence=0.0,
                reasons=["Pydantic 스키마 검증 실패"],
                parse_error=f"pydantic_validation_error: {e}",
            )

        return QualityJudgeResult(
            accept=output.accept,
            confidence=_clamp01(output.confidence),
            reasons=output.reasons,
            risk_flags=output.risk_flags,
            summary=output.summary,
        )

    async def judge_round(
        self,
        question: str,
        sql: str,
        row_count: int | None,
        execution_time_ms: float | None,
        preview: dict | None,
        metadata: dict | None,
        round_idx: int = 0,
        *,
        extra_signals: dict | None = None,
    ) -> QualityJudgeResult:
        """단일 라운드 LLM 심사를 수행한다.

        LLM 호출 실패 시 fail-closed: accept=False, confidence=0.0
        """
        user_prompt = self._build_user_prompt(
            question=question,
            sql=sql,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            preview=preview,
            metadata=metadata,
            round_idx=round_idx,
            extra_signals=extra_signals,
        )

        try:
            raw_response = await llm_factory.generate(
                user_prompt,
                system_prompt=self._system_prompt,
                temperature=0.0,
                max_tokens=700,
            )
        except Exception as e:
            # fail-closed: LLM 호출 실패 시 REJECT
            logger.error("quality_judge_llm_error", round_idx=round_idx, error=str(e))
            return QualityJudgeResult(
                accept=False,
                confidence=0.0,
                reasons=["LLM 호출 실패"],
                parse_error=f"llm_call_error: {e}",
            )

        result = self._parse_llm_output(raw_response or "")

        logger.info(
            "quality_judge_round",
            round_idx=round_idx,
            accept=result.accept,
            confidence=result.confidence,
            reasons=result.reasons[:3],
            risk_flags=result.risk_flags[:3],
            parse_error=result.parse_error or "",
        )

        return result

    async def _execute_round(
        self,
        question: str,
        sql: str,
        row_count: int | None,
        execution_time_ms: float | None,
        preview: dict | None,
        metadata: dict | None,
        round_num: int,
        extra_signals: dict | None = None,
    ) -> QualityJudgeResult:
        """단일 라운드 심사를 실행한다.

        judge_round를 래핑하여 라운드 번호(0-based)와
        추가 신호를 전달한다.
        """
        return await self.judge_round(
            question=question,
            sql=sql,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            preview=preview,
            metadata=metadata,
            round_idx=round_num,
            extra_signals=extra_signals,
        )

    def _merge_round_results(
        self,
        round1: QualityJudgeResult,
        round2: QualityJudgeResult | None,
    ) -> QualityJudgeResult:
        """두 라운드 결과를 병합하여 최종 판정을 내린다.

        Round 2가 None이면 Round 1 결과를 그대로 반환한다.
        Round 2에 파싱 에러가 있으면 Round 1 confidence를 하향 조정한다.
        정상 병합 시 가중 평균(Round1 0.4 + Round2 0.6)으로 계산한다.
        """
        # Round 2가 없으면 Round 1 그대로
        if round2 is None:
            return round1

        # Round 2 파싱 에러 시 보수적 판단
        if round2.parse_error:
            return QualityJudgeResult(
                accept=round1.accept and round1.confidence >= self.THRESHOLD_APPROVE,
                confidence=_clamp01(round1.confidence * 0.9),
                reasons=round1.reasons + ["Round 2 파싱 실패로 보수적 판단"],
                risk_flags=round1.risk_flags + ["round2_parse_failure"],
                summary=round1.summary,
            )

        # 두 라운드의 가중 평균 계산 (Round 2에 더 높은 가중치)
        avg_confidence = _clamp01(
            round1.confidence * 0.4 + round2.confidence * 0.6
        )

        # 모든 라운드의 근거와 위험 신호를 병합 (중복 제거, 순서 유지)
        merged_reasons = list(dict.fromkeys(round1.reasons + round2.reasons))
        merged_risk_flags = list(dict.fromkeys(round1.risk_flags + round2.risk_flags))

        # 최종 accept 판정
        all_accept = round1.accept and round2.accept
        final_accept = all_accept and avg_confidence >= self.THRESHOLD_PENDING

        logger.info(
            "quality_judge_multi_round",
            round1_confidence=round1.confidence,
            round2_confidence=round2.confidence,
            avg_confidence=avg_confidence,
            all_accept=all_accept,
            final_accept=final_accept,
        )

        return QualityJudgeResult(
            accept=final_accept,
            confidence=avg_confidence,
            reasons=merged_reasons,
            risk_flags=merged_risk_flags,
            summary=round2.summary or round1.summary,
        )

    def _build_round2_signals(
        self,
        question: str,
        sql: str,
        preview: dict | None,
        round1: QualityJudgeResult,
    ) -> dict[str, Any]:
        """Round 2에 주입할 추가 신호를 구성한다.

        semantic mismatch, null ratio, 이전 라운드 피드백을 포함한다.
        """
        extra_signals: dict[str, Any] = {}

        mismatches = semantic_mismatch_reasons(question, sql)
        if mismatches:
            extra_signals["semantic_mismatches"] = mismatches

        null_ratio = preview_null_ratio(preview)
        if null_ratio > 0.0:
            extra_signals["null_ratio"] = round(null_ratio, 3)

        # 이전 라운드 피드백 주입
        if round1.reasons:
            extra_signals["previous_round_reasons"] = round1.reasons
        if round1.risk_flags:
            extra_signals["previous_round_risk_flags"] = round1.risk_flags

        return extra_signals

    async def multi_round_judge(
        self,
        question: str,
        sql: str,
        row_count: int | None,
        execution_time_ms: float | None,
        preview: dict | None,
        metadata: dict | None,
        max_rounds: int = 2,
    ) -> QualityJudgeResult:
        """N-라운드 심사를 수행한다.

        Round 1 결과의 confidence가 애매한 구간(0.55~0.85)이면
        추가 신호를 주입하여 Round 2를 수행한다.

        최종 판정:
        - avg_confidence >= 0.80 AND 모든 라운드 accept=True -> APPROVE
        - avg_confidence >= 0.60 AND 최소 1라운드 accept=True -> PENDING
        - 그 외 -> REJECT
        """
        # Round 1: 기본 심사
        round1 = await self._execute_round(
            question=question,
            sql=sql,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            preview=preview,
            metadata=metadata,
            round_num=0,
        )

        # 파싱 에러가 있으면 바로 REJECT (fail-closed)
        if round1.parse_error:
            return round1

        # Round 2 실행 여부 판단: confidence가 애매한 구간인지 확인
        need_round2 = (
            max_rounds >= 2
            and self._AMBIGUOUS_LOW <= round1.confidence <= self._AMBIGUOUS_HIGH
        )

        if not need_round2:
            return self._merge_round_results(round1, None)

        # Round 2: 추가 신호 주입 (semantic mismatch + null ratio)
        extra_signals = self._build_round2_signals(question, sql, preview, round1)

        round2 = await self._execute_round(
            question=question,
            sql=sql,
            row_count=row_count,
            execution_time_ms=execution_time_ms,
            preview=preview,
            metadata=metadata,
            round_num=1,
            extra_signals=extra_signals,
        )

        return self._merge_round_results(round1, round2)
