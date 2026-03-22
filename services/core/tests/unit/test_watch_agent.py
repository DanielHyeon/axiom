"""Watch Agent 단위 테스트.

WatchAgent 클래스의 규칙 생성 및 데이터 가용성 분석을 테스트한다.
LLM 의존성 없이 폴백 로직을 검증.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.modules.watch.watch_agent import (
    WatchAgent,
    WatchRuleProposal,
    AvailabilityReport,
)


# ── WatchRuleProposal 데이터 모델 테스트 ───────────────────────────


class TestWatchRuleProposal:
    """규칙 제안 데이터 모델 테스트"""

    def test_to_dict(self):
        """딕셔너리 변환 정상 동작"""
        proposal = WatchRuleProposal(
            name="매출 감소 감지",
            sql_query="SELECT SUM(amount) FROM sales",
            condition_type="change_rate",
            threshold=-0.2,
            severity="high",
            schedule_interval="1h",
            explanation="매출 변화율 모니터링",
        )
        d = proposal.to_dict()
        assert d["name"] == "매출 감소 감지"
        assert d["condition_type"] == "change_rate"
        assert d["threshold"] == -0.2
        assert d["severity"] == "high"

    def test_default_values(self):
        """기본값 정상 설정"""
        proposal = WatchRuleProposal(
            name="test",
            sql_query="SELECT 1",
            condition_type="threshold",
            threshold=100.0,
        )
        assert proposal.severity == "medium"
        assert proposal.schedule_interval == "1h"
        assert proposal.columns_used == []


class TestAvailabilityReport:
    """가용성 보고서 데이터 모델 테스트"""

    def test_to_dict(self):
        report = AvailabilityReport(
            available=True,
            tables_found=["sales", "products"],
            tables_missing=[],
        )
        d = report.to_dict()
        assert d["available"] is True
        assert len(d["tables_found"]) == 2


# ── WatchAgent 폴백 로직 테스트 ────────────────────────────────────


class TestWatchAgentFallback:
    """LLM 없이 키워드 기반 폴백 규칙 생성 테스트"""

    @pytest.fixture
    def agent(self):
        """LLM 없는 WatchAgent"""
        return WatchAgent()

    @pytest.mark.asyncio
    async def test_generate_rule_change_rate(self, agent):
        """변화율 키워드 감지"""
        proposal = await agent.generate_rule_from_text(
            description="매출이 전월 대비 20% 이상 감소하면 알림",
            datasource_id="ds-1",
        )
        assert isinstance(proposal, WatchRuleProposal)
        assert proposal.condition_type == "change_rate"
        # 20% → 0.2
        assert proposal.threshold == pytest.approx(0.2)

    @pytest.mark.asyncio
    async def test_generate_rule_threshold(self, agent):
        """임계값 키워드 감지"""
        proposal = await agent.generate_rule_from_text(
            description="재고가 100개 미만이면 알림",
            datasource_id="ds-1",
        )
        assert proposal.condition_type == "threshold"
        assert proposal.threshold == pytest.approx(100.0)

    @pytest.mark.asyncio
    async def test_generate_rule_anomaly(self, agent):
        """이상치 키워드 감지"""
        proposal = await agent.generate_rule_from_text(
            description="비정상적인 접속 패턴 탐지",
            datasource_id="ds-1",
        )
        assert proposal.condition_type == "anomaly"

    @pytest.mark.asyncio
    async def test_generate_rule_count(self, agent):
        """건수 키워드 감지"""
        proposal = await agent.generate_rule_from_text(
            description="에러 횟수가 50회 초과하면 긴급 알림",
            datasource_id="ds-1",
        )
        assert proposal.condition_type == "count"
        assert proposal.severity == "critical"  # "긴급" 키워드
        assert proposal.threshold == pytest.approx(50.0)

    @pytest.mark.asyncio
    async def test_generate_rule_high_severity(self, agent):
        """높은 심각도 키워드 감지"""
        proposal = await agent.generate_rule_from_text(
            description="중요 KPI가 목표치 아래로 떨어지면",
            datasource_id="ds-1",
        )
        assert proposal.severity == "high"

    @pytest.mark.asyncio
    async def test_generate_rule_low_severity(self, agent):
        """낮은 심각도 키워드 감지"""
        proposal = await agent.generate_rule_from_text(
            description="경미한 변동 감지",
            datasource_id="ds-1",
        )
        assert proposal.severity == "low"

    @pytest.mark.asyncio
    async def test_generate_rule_empty_description_raises(self, agent):
        """빈 설명은 ValueError 발생"""
        with pytest.raises(ValueError, match="비어있습니다"):
            await agent.generate_rule_from_text(
                description="",
                datasource_id="ds-1",
            )

    @pytest.mark.asyncio
    async def test_generate_rule_has_explanation(self, agent):
        """폴백 규칙에는 설명이 포함된다"""
        proposal = await agent.generate_rule_from_text(
            description="테스트 규칙",
            datasource_id="ds-1",
        )
        assert "LLM" in proposal.explanation
        assert "폴백" not in proposal.explanation or "키워드" in proposal.explanation

    @pytest.mark.asyncio
    async def test_generate_rule_datasource_id(self, agent):
        """데이터소스 ID가 올바르게 설정된다"""
        proposal = await agent.generate_rule_from_text(
            description="모니터링 규칙",
            datasource_id="my-ds-42",
        )
        assert proposal.datasource_id == "my-ds-42"


# ── 데이터 가용성 분석 폴백 테스트 ─────────────────────────────────


class TestWatchAgentAvailability:
    """데이터 가용성 분석 폴백 테스트"""

    @pytest.fixture
    def agent(self):
        return WatchAgent()

    @pytest.mark.asyncio
    async def test_analyze_fallback(self, agent):
        """LLM 없이 기본 가용성 보고서 생성"""
        report = await agent.analyze_data_availability(
            datasource_id="ds-1",
            question="매출 데이터 모니터링",
        )
        assert isinstance(report, AvailabilityReport)
        assert report.available is True
        assert "LLM" in report.suggestion

    @pytest.mark.asyncio
    async def test_analyze_empty_question(self, agent):
        """빈 질문은 available=False 반환"""
        report = await agent.analyze_data_availability(
            datasource_id="ds-1",
            question="",
        )
        assert report.available is False


# ── JSON 파싱 테스트 ───────────────────────────────────────────────


class TestParseJsonResponse:
    """LLM 응답 JSON 파싱 테스트"""

    @pytest.fixture
    def agent(self):
        return WatchAgent()

    def test_parse_clean_json(self, agent):
        """깔끔한 JSON 파싱"""
        text = '{"name": "test", "threshold": 0.5}'
        result = agent._parse_llm_json(text)
        assert result["name"] == "test"

    def test_parse_markdown_wrapped(self, agent):
        """마크다운 코드블록으로 감싸진 JSON"""
        text = '```json\n{"name": "test"}\n```'
        result = agent._parse_llm_json(text)
        assert result["name"] == "test"

    def test_parse_with_extra_text(self, agent):
        """앞뒤에 텍스트가 있는 JSON"""
        text = 'Here is the result:\n{"name": "test"}\nDone.'
        result = agent._parse_llm_json(text)
        assert result["name"] == "test"

    def test_parse_invalid_returns_none(self, agent):
        """파싱 불가 시 None 반환"""
        result = agent._parse_llm_json("not json at all")
        assert result is None
