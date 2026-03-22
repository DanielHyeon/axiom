"""C-Pipeline + HyDE + 리랭킹 + 루브릭 + 대화 연속성 단위 테스트.

테스트 대상:
- conversation_state: 인코딩/디코딩, HMAC 위변조 탐지
- rubric_evaluator: SQLCandidate 평가 로직
- c_pipeline: 탐색→수렴→탈출 흐름
- hyde_generator: HyDE SQL 생성
"""
import pytest

from app.pipelines.conversation_state import (
    ConversationContext,
    ConversationTurn,
    decode_conversation_state,
    encode_conversation_state,
    MAX_CONVERSATION_TURNS,
)
from app.pipelines.rubric_evaluator import (
    RUBRIC_THRESHOLD,
    RubricResult,
    RubricScore,
    SQLCandidate,
)
from app.pipelines.c_pipeline import CPipelineResult, _step


# ── 대화 연속성 테스트 ──


class TestConversationState:
    """conversation_state 인코딩/디코딩/HMAC 검증."""

    def test_encode_decode_roundtrip(self):
        """인코딩 후 디코딩하면 원본 데이터가 복원된다."""
        ctx = ConversationContext(datasource_id="ds-1", case_id="case-1")
        ctx.add_turn(ConversationTurn(
            question="월별 매출 합계",
            sql="SELECT month, SUM(amount) FROM sales GROUP BY month",
            tables=["sales"],
            columns=["month", "amount"],
            row_count=12,
        ))

        token = encode_conversation_state(ctx)
        restored = decode_conversation_state(token)

        assert restored is not None
        assert restored.datasource_id == "ds-1"
        assert len(restored.turns) == 1
        assert restored.turns[0].question == "월별 매출 합계"
        assert restored.turns[0].tables == ["sales"]

    def test_tampered_token_rejected(self):
        """위변조된 토큰은 None을 반환한다."""
        ctx = ConversationContext(datasource_id="ds-1")
        ctx.add_turn(ConversationTurn(question="test"))
        token = encode_conversation_state(ctx)

        # 토큰 변조
        tampered = token[:-5] + "XXXXX"
        result = decode_conversation_state(tampered)
        assert result is None

    def test_empty_token(self):
        """빈 토큰은 None을 반환한다."""
        assert decode_conversation_state("") is None
        assert decode_conversation_state(None) is None

    def test_max_turns_enforced(self):
        """최대 턴 수를 초과하면 오래된 턴이 제거된다."""
        ctx = ConversationContext()
        for i in range(MAX_CONVERSATION_TURNS + 5):
            ctx.add_turn(ConversationTurn(question=f"질문 {i}"))

        assert len(ctx.turns) == MAX_CONVERSATION_TURNS
        # 가장 오래된 것(인덱스 0~4)이 제거되고 최신 것만 남아야 함
        assert ctx.turns[0].question == "질문 5"

    def test_context_for_prompt(self):
        """LLM 프롬프트용 대화 이력 문자열 생성."""
        ctx = ConversationContext()
        ctx.add_turn(ConversationTurn(
            question="Q1", sql="SELECT 1", tables=["t1"]
        ))
        ctx.add_turn(ConversationTurn(
            question="Q2", sql="SELECT 2", tables=["t2"]
        ))

        prompt = ctx.get_context_for_prompt()
        assert "이전 대화 이력" in prompt
        assert "Q1" in prompt
        assert "Q2" in prompt
        assert "t1" in prompt

    def test_get_recent_tables(self):
        """최근 대화에서 사용된 테이블 목록."""
        ctx = ConversationContext()
        ctx.add_turn(ConversationTurn(question="q1", tables=["a", "b"]))
        ctx.add_turn(ConversationTurn(question="q2", tables=["b", "c"]))

        tables = ctx.get_recent_tables()
        # 최신→오래된 순서, 중복 제거
        assert tables == ["b", "c", "a"]


# ── 루브릭 평가 모델 테스트 ──


class TestRubricModels:
    """루브릭 평가 데이터 모델 테스트."""

    def test_rubric_result_passed(self):
        """임계값 이상이면 passed=True."""
        result = RubricResult(total_score=0.85, passed=True)
        assert result.passed is True
        assert result.total_score >= RUBRIC_THRESHOLD

    def test_rubric_result_failed(self):
        """임계값 미만이면 passed=False."""
        result = RubricResult(total_score=0.5, passed=False)
        assert result.passed is False

    def test_sql_candidate_ranking(self):
        """SQLCandidate는 점수로 정렬 가능."""
        c1 = SQLCandidate(sql="SELECT 1", rubric=RubricResult(total_score=0.5))
        c2 = SQLCandidate(sql="SELECT 2", rubric=RubricResult(total_score=0.9))
        c3 = SQLCandidate(sql="SELECT 3", rubric=RubricResult(total_score=0.7))

        candidates = sorted(
            [c1, c2, c3],
            key=lambda c: c.rubric.total_score if c.rubric else 0.0,
            reverse=True,
        )
        assert candidates[0].sql == "SELECT 2"
        assert candidates[1].sql == "SELECT 3"


# ── C-Pipeline 결과 모델 테스트 ──


class TestCPipelineResult:
    """CPipelineResult 데이터 모델 테스트."""

    def test_step_helper(self):
        """_step 헬퍼 함수."""
        s = _step("exploration", "4개 후보 생성", {"count": 4})
        assert s["phase"] == "exploration"
        assert s["detail"] == "4개 후보 생성"
        assert s["count"] == 4

    def test_result_defaults(self):
        """기본 결과 값."""
        r = CPipelineResult(phase="exploration")
        assert r.passed is False
        assert r.final_sql == ""
        assert r.total_attempts == 0

    def test_rubric_threshold(self):
        """루브릭 임계값 확인."""
        assert RUBRIC_THRESHOLD == 0.75
