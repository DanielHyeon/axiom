"""품질 심사기(QualityJudge) 단위 테스트.

테스트 대상:
- QualityJudgeLLMOutput Pydantic 모델 (extra="forbid")
- _extract_first_json_object (JSON 추출)
- _clamp01 (confidence 범위 제한)
- semantic_mismatch_reasons (의미적 불일치 감지)
- preview_null_ratio (NULL 비율 계산)
- QualityJudge.judge_round (단일 라운드 심사)
- QualityJudge.multi_round_judge (N-라운드 심사)
- GateDecision 모델 (APPROVE/PENDING/REJECT)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.core.quality_judge import (
    QualityJudge,
    QualityJudgeLLMOutput,
    QualityJudgeResult,
    _clamp01,
    _extract_first_json_object,
    preview_null_ratio,
    semantic_mismatch_reasons,
)
from app.pipelines.cache_postprocess import CachePostProcessor, GateDecision


# ---------------------------------------------------------------------------
# _clamp01 테스트
# ---------------------------------------------------------------------------


class TestClamp01:
    """confidence 범위 제한 함수 테스트."""

    def test_normal_range(self):
        assert _clamp01(0.5) == 0.5

    def test_below_zero(self):
        """0 미만은 0.0으로 고정"""
        assert _clamp01(-0.5) == 0.0

    def test_above_one(self):
        """1 초과는 1.0으로 고정"""
        assert _clamp01(1.5) == 1.0

    def test_boundary_zero(self):
        assert _clamp01(0.0) == 0.0

    def test_boundary_one(self):
        assert _clamp01(1.0) == 1.0


# ---------------------------------------------------------------------------
# _extract_first_json_object 테스트
# ---------------------------------------------------------------------------


class TestExtractFirstJsonObject:
    """LLM 응답에서 JSON 객체 추출 테스트."""

    def test_plain_json(self):
        """순수 JSON 응답"""
        text = '{"accept": true, "confidence": 0.9}'
        result = _extract_first_json_object(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["accept"] is True

    def test_json_in_code_fence(self):
        """코드 펜스로 감싸진 JSON"""
        text = '```json\n{"accept": false, "confidence": 0.3}\n```'
        result = _extract_first_json_object(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["accept"] is False

    def test_json_with_preamble(self):
        """설명문 뒤에 JSON이 있는 경우"""
        text = '분석 결과입니다:\n{"accept": true, "confidence": 0.85}'
        result = _extract_first_json_object(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["confidence"] == 0.85

    def test_no_json(self):
        """JSON이 없는 응답"""
        result = _extract_first_json_object("그냥 텍스트입니다")
        assert result is None

    def test_empty_string(self):
        result = _extract_first_json_object("")
        assert result is None

    def test_none_input(self):
        result = _extract_first_json_object(None)
        assert result is None

    def test_nested_json(self):
        """중첩된 JSON 객체"""
        text = '{"accept": true, "reasons": ["reason1"], "confidence": 0.9}'
        result = _extract_first_json_object(text)
        assert result is not None
        parsed = json.loads(result)
        assert parsed["reasons"] == ["reason1"]


# ---------------------------------------------------------------------------
# QualityJudgeLLMOutput Pydantic 모델 테스트
# ---------------------------------------------------------------------------


class TestQualityJudgeLLMOutput:
    """Pydantic strict 모델 테스트 (extra="forbid")."""

    def test_valid_output(self):
        """정상 JSON 파싱"""
        data = {
            "accept": True,
            "confidence": 0.9,
            "reasons": ["질문 의도 부합"],
            "risk_flags": [],
            "summary": "APPROVE",
        }
        output = QualityJudgeLLMOutput.model_validate(data)
        assert output.accept is True
        assert output.confidence == 0.9

    def test_extra_key_forbidden(self):
        """추가 키 포함 시 파싱 실패"""
        data = {
            "accept": True,
            "confidence": 0.9,
            "reasons": [],
            "risk_flags": [],
            "summary": "",
            "unexpected_key": "bad",  # 추가 키
        }
        with pytest.raises(Exception):
            QualityJudgeLLMOutput.model_validate(data)

    def test_default_values(self):
        """빈 딕셔너리 -> 기본값 적용"""
        output = QualityJudgeLLMOutput.model_validate({})
        assert output.accept is False
        assert output.confidence == 0.0
        assert output.reasons == []

    def test_confidence_out_of_range(self):
        """confidence가 0~1 범위 밖이면 검증 실패"""
        with pytest.raises(Exception):
            QualityJudgeLLMOutput.model_validate({"confidence": 1.5})
        with pytest.raises(Exception):
            QualityJudgeLLMOutput.model_validate({"confidence": -0.1})


# ---------------------------------------------------------------------------
# semantic_mismatch_reasons 테스트
# ---------------------------------------------------------------------------


class TestSemanticMismatchReasons:
    """질문-SQL 의미적 불일치 감지 테스트."""

    def test_missing_avg(self):
        """질문에 '평균'이 있는데 SQL에 AVG()가 없는 경우"""
        reasons = semantic_mismatch_reasons("서울 지역 평균 매출", "SELECT revenue FROM sales")
        assert "missing AVG()" in reasons

    def test_avg_present(self):
        """AVG()가 SQL에 있으면 감지하지 않음"""
        reasons = semantic_mismatch_reasons("평균 매출", "SELECT AVG(revenue) FROM sales")
        assert "missing AVG()" not in reasons

    def test_missing_sum(self):
        reasons = semantic_mismatch_reasons("매출 합계", "SELECT revenue FROM sales")
        assert "missing SUM()" in reasons

    def test_missing_count(self):
        reasons = semantic_mismatch_reasons("건수를 알려줘", "SELECT * FROM sales")
        assert "missing COUNT()" in reasons

    def test_missing_group_by(self):
        """'별'이 질문에 있는데 GROUP BY가 없는 경우"""
        reasons = semantic_mismatch_reasons("지역별 매출", "SELECT region, revenue FROM sales")
        assert "missing GROUP BY" in reasons

    def test_no_mismatch(self):
        """불일치 없는 경우"""
        reasons = semantic_mismatch_reasons(
            "지역별 평균 매출",
            "SELECT region, AVG(revenue) FROM sales GROUP BY region ORDER BY region",
        )
        assert len(reasons) == 0


# ---------------------------------------------------------------------------
# preview_null_ratio 테스트
# ---------------------------------------------------------------------------


class TestPreviewNullRatio:
    """NULL 비율 계산 테스트."""

    def test_no_nulls(self):
        preview = {"rows": [[1, "a"], [2, "b"]]}
        assert preview_null_ratio(preview) == 0.0

    def test_all_nulls(self):
        preview = {"rows": [[None, None], [None, None]]}
        assert preview_null_ratio(preview) == 1.0

    def test_half_nulls(self):
        preview = {"rows": [[1, None], [None, "b"]]}
        assert preview_null_ratio(preview) == 0.5

    def test_empty_preview(self):
        assert preview_null_ratio(None) == 0.0
        assert preview_null_ratio({}) == 0.0
        assert preview_null_ratio({"rows": []}) == 0.0


# ---------------------------------------------------------------------------
# QualityJudge.judge_round 테스트
# ---------------------------------------------------------------------------


class TestQualityJudgeRound:
    """단일 라운드 LLM 심사 테스트."""

    @pytest.fixture
    def judge(self):
        return QualityJudge()

    @pytest.mark.asyncio
    async def test_successful_judge(self, judge):
        """LLM이 정상 JSON을 반환하면 파싱 성공"""
        llm_response = json.dumps({
            "accept": True,
            "confidence": 0.92,
            "reasons": ["질문 의도 부합"],
            "risk_flags": [],
            "summary": "승인",
        })
        with patch.object(
            judge, "_build_user_prompt", return_value="test"
        ), patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(return_value=llm_response)
            result = await judge.judge_round(
                question="매출 합계",
                sql="SELECT SUM(revenue) FROM sales",
                row_count=1,
                execution_time_ms=50.0,
                preview={"columns": ["sum"], "rows": [[150000]], "row_count": 1},
                metadata=None,
            )
        assert result.accept is True
        assert result.confidence == 0.92
        assert result.parse_error == ""

    @pytest.mark.asyncio
    async def test_llm_failure_fail_closed(self, judge):
        """LLM 호출 실패 시 fail-closed (REJECT)"""
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
            result = await judge.judge_round(
                question="test",
                sql="SELECT 1",
                row_count=None,
                execution_time_ms=None,
                preview=None,
                metadata=None,
            )
        assert result.accept is False
        assert result.confidence == 0.0
        assert "LLM 호출 실패" in result.reasons[0]

    @pytest.mark.asyncio
    async def test_invalid_json_fail_closed(self, judge):
        """LLM이 유효하지 않은 JSON을 반환하면 fail-closed"""
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(return_value="이것은 JSON이 아닙니다")
            result = await judge.judge_round(
                question="test",
                sql="SELECT 1",
                row_count=None,
                execution_time_ms=None,
                preview=None,
                metadata=None,
            )
        assert result.accept is False
        assert result.confidence == 0.0
        assert result.parse_error != ""

    @pytest.mark.asyncio
    async def test_extra_key_fail_closed(self, judge):
        """LLM 응답에 추가 키가 있으면 fail-closed"""
        llm_response = json.dumps({
            "accept": True,
            "confidence": 0.9,
            "reasons": [],
            "risk_flags": [],
            "summary": "",
            "hacked_field": "exploit",
        })
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(return_value=llm_response)
            result = await judge.judge_round(
                question="test",
                sql="SELECT 1",
                row_count=None,
                execution_time_ms=None,
                preview=None,
                metadata=None,
            )
        assert result.accept is False
        assert result.confidence == 0.0
        assert "pydantic" in result.parse_error.lower()


# ---------------------------------------------------------------------------
# QualityJudge.multi_round_judge 테스트
# ---------------------------------------------------------------------------


class TestMultiRoundJudge:
    """N-라운드 심사 테스트."""

    @pytest.fixture
    def judge(self):
        return QualityJudge()

    @pytest.mark.asyncio
    async def test_high_confidence_skips_round2(self, judge):
        """Round 1 confidence > 0.85 -> Round 2 건너뜀"""
        round1_response = json.dumps({
            "accept": True,
            "confidence": 0.95,
            "reasons": ["완벽"],
            "risk_flags": [],
            "summary": "승인",
        })
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(return_value=round1_response)
            result = await judge.multi_round_judge(
                question="test",
                sql="SELECT 1",
                row_count=1,
                execution_time_ms=50.0,
                preview=None,
                metadata=None,
            )
        # LLM이 1번만 호출되어야 함 (Round 2 건너뜀)
        assert mock_factory.generate.call_count == 1
        assert result.accept is True
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_low_confidence_skips_round2(self, judge):
        """Round 1 confidence < 0.55 -> Round 2 건너뜀"""
        round1_response = json.dumps({
            "accept": False,
            "confidence": 0.3,
            "reasons": ["불일치"],
            "risk_flags": ["mismatch"],
            "summary": "거절",
        })
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(return_value=round1_response)
            result = await judge.multi_round_judge(
                question="test",
                sql="SELECT 1",
                row_count=0,
                execution_time_ms=50.0,
                preview=None,
                metadata=None,
            )
        assert mock_factory.generate.call_count == 1
        assert result.accept is False

    @pytest.mark.asyncio
    async def test_ambiguous_triggers_round2(self, judge):
        """Round 1 confidence 0.55~0.85 -> Round 2 실행"""
        round1_response = json.dumps({
            "accept": True,
            "confidence": 0.70,
            "reasons": ["부분 일치"],
            "risk_flags": [],
            "summary": "보류",
        })
        round2_response = json.dumps({
            "accept": True,
            "confidence": 0.85,
            "reasons": ["추가 검증 통과"],
            "risk_flags": [],
            "summary": "승인",
        })
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(
                side_effect=[round1_response, round2_response]
            )
            result = await judge.multi_round_judge(
                question="test",
                sql="SELECT 1",
                row_count=5,
                execution_time_ms=50.0,
                preview={"columns": ["a"], "rows": [[1]], "row_count": 1},
                metadata=None,
            )
        # LLM이 2번 호출되어야 함
        assert mock_factory.generate.call_count == 2
        assert result.accept is True
        # 가중 평균: 0.70*0.4 + 0.85*0.6 = 0.79
        assert 0.78 <= result.confidence <= 0.80


# ---------------------------------------------------------------------------
# GateDecision / CachePostProcessor 테스트
# ---------------------------------------------------------------------------


class TestGateDecision:
    """품질 게이트 판정 모델 테스트."""

    def test_approve_model(self):
        d = GateDecision(
            status="APPROVE",
            confidence=0.92,
            reasons=["good"],
            risk_flags=[],
        )
        assert d.status == "APPROVE"
        assert d.confidence == 0.92

    def test_reject_model(self):
        d = GateDecision(
            status="REJECT",
            confidence=0.3,
            reasons=["bad"],
            risk_flags=["mismatch"],
        )
        assert d.status == "REJECT"

    def test_pending_model(self):
        d = GateDecision(
            status="PENDING",
            confidence=0.65,
            summary="수동 검토 필요",
        )
        assert d.status == "PENDING"


class TestCachePostProcessor:
    """CachePostProcessor 통합 테스트."""

    @pytest.fixture
    def processor(self):
        return CachePostProcessor()

    @pytest.mark.asyncio
    async def test_approve_threshold(self, processor):
        """confidence >= 0.80 + accept=True -> APPROVE"""
        llm_response = json.dumps({
            "accept": True,
            "confidence": 0.92,
            "reasons": ["good"],
            "risk_flags": [],
            "summary": "ok",
        })
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(return_value=llm_response)
            decision = await processor.quality_gate(
                question="매출 합계",
                sql="SELECT SUM(revenue) FROM sales",
                result_preview=[[150000]],
                datasource_id="ds1",
            )
        assert decision.status == "APPROVE"

    @pytest.mark.asyncio
    async def test_reject_on_llm_failure(self, processor):
        """LLM 호출 실패 -> REJECT"""
        with patch(
            "app.core.quality_judge.llm_factory"
        ) as mock_factory:
            mock_factory.generate = AsyncMock(side_effect=RuntimeError("timeout"))
            decision = await processor.quality_gate(
                question="test",
                sql="SELECT 1",
                result_preview=[],
                datasource_id="ds1",
            )
        assert decision.status == "REJECT"
        assert decision.confidence == 0.0

    @pytest.mark.asyncio
    async def test_feature_flag_bypass(self, processor):
        """ENABLE_QUALITY_GATE=False -> 항상 APPROVE"""
        with patch("app.pipelines.cache_postprocess.settings") as mock_settings:
            mock_settings.ENABLE_QUALITY_GATE = False
            decision = await processor.quality_gate(
                question="test",
                sql="SELECT 1",
                result_preview=[],
                datasource_id="ds1",
            )
        assert decision.status == "APPROVE"
        assert decision.confidence == 0.95
