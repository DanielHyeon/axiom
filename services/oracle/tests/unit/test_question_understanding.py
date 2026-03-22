"""
Sprint 4: 질문 이해 엔진 단위 테스트

QuestionUnderstandingEngine의 5단계 파이프라인을 검증한다:
1. 텍스트 정규화 (조사 제거, 소문자 변환)
2. 동의어 확장 (exact / normalized 매칭)
3. 의도 분류 + 신뢰도 점수
4. Fallback 모드 결정
5. 시멘틱 힌트 생성
"""

import pytest

from app.core.question_understanding import (
    QuestionUnderstandingEngine,
    QuestionUnderstandingResult,
    SynonymMatch,
    IntentDecision,
)

# ── 공통 fixture ─────────────────────────────────────────

@pytest.fixture
def engine() -> QuestionUnderstandingEngine:
    """엔진 인스턴스 — 매 테스트마다 새로 생성"""
    return QuestionUnderstandingEngine()


@pytest.fixture
def sample_synonym_map() -> dict[str, str]:
    """테스트용 동의어 맵 (surface_form → concept_id)"""
    return {
        "매출액": "revenue_total",
        "매출": "revenue_total",
        "순이익": "net_profit",
        "불량률": "defect_rate",
        "OEE": "oee_index",
        "가동률": "oee_index",
        "리드타임": "lead_time",
    }


# ═══════════════════════════════════════════════════════════
# 1단계: 텍스트 정규화
# ═══════════════════════════════════════════════════════════

class TestNormalizeText:
    """한글 조사 제거 + 소문자 변환 + 공백 정리 테스트"""

    def test_normalize_korean_particles(self, engine: QuestionUnderstandingEngine):
        """한국어 조사(은/는/이/가/을/를/의/에/에서/으로/로)가 제거되는지"""
        result = engine._normalize_text("매출액의 추세는 어떤가요?")
        # "의", "는" 조사가 제거되어야 한다
        assert "의" not in result.split()
        assert "는" not in result.split()
        assert "매출액" in result
        assert "추세" in result

    def test_normalize_whitespace(self, engine: QuestionUnderstandingEngine):
        """연속 공백이 하나로 정리되는지"""
        result = engine._normalize_text("  매출   현황을   보여줘  ")
        assert "  " not in result
        assert result == engine._normalize_text(result)  # 멱등성

    def test_normalize_lowercase(self, engine: QuestionUnderstandingEngine):
        """영어가 소문자로 변환되는지"""
        result = engine._normalize_text("Show me the OEE Trend")
        assert "show" in result
        assert "oee" in result

    def test_normalize_preserves_content(self, engine: QuestionUnderstandingEngine):
        """조사가 없는 영어 문장은 소문자 변환만 적용"""
        result = engine._normalize_text("What is the revenue?")
        assert result == "what is the revenue?"


# ═══════════════════════════════════════════════════════════
# 2단계: 동의어 확장
# ═══════════════════════════════════════════════════════════

class TestSynonymExpansion:
    """동의어 맵 기반 용어 매칭 테스트"""

    def test_synonym_exact_match(self, engine: QuestionUnderstandingEngine, sample_synonym_map: dict):
        """surface_form이 질문에 그대로 포함될 때 exact 매칭"""
        result = engine.understand("매출액 추세를 보여줘", sample_synonym_map)
        revenue_match = next(
            (m for m in result.synonym_matches if m.canonical_name == "revenue_total"), None
        )
        assert revenue_match is not None
        assert revenue_match.match_type == "exact"
        assert revenue_match.confidence == 0.95

    def test_synonym_normalized_match(self, engine: QuestionUnderstandingEngine):
        """조사가 붙은 surface_form이 정규화 후 매칭되는 경우"""
        # "불량률의" 에서 "의" 제거 후 "불량률" 매칭
        synonym_map = {"불량률의 원인": "defect_cause"}
        # "불량률 원인" (조사 제거)이 질문에 포함
        result = engine.understand("불량률 원인 분석해줘", synonym_map)
        match = next(
            (m for m in result.synonym_matches if m.canonical_name == "defect_cause"), None
        )
        assert match is not None
        assert match.match_type == "normalized"
        assert match.confidence == 0.85

    def test_synonym_no_match(self, engine: QuestionUnderstandingEngine, sample_synonym_map: dict):
        """동의어 맵에 없는 용어는 매칭되지 않음"""
        result = engine.understand("날씨가 어떤가요?", sample_synonym_map)
        assert len(result.synonym_matches) == 0

    def test_synonym_dedup_by_concept(self, engine: QuestionUnderstandingEngine, sample_synonym_map: dict):
        """같은 concept에 여러 surface_form이 매칭되면 높은 confidence 하나만 남김"""
        # "매출액"과 "매출" 모두 revenue_total에 매칭되지만, 하나만 남아야 함
        result = engine.understand("매출액과 매출 비교", sample_synonym_map)
        revenue_matches = [m for m in result.synonym_matches if m.canonical_name == "revenue_total"]
        assert len(revenue_matches) == 1
        # 더 높은 confidence (0.95)가 남아야 함
        assert revenue_matches[0].confidence == 0.95

    def test_empty_synonym_map(self, engine: QuestionUnderstandingEngine):
        """빈 동의어 맵이면 매칭 결과 없음"""
        result = engine.understand("매출 추세", {})
        assert len(result.synonym_matches) == 0

    def test_synonym_none_map(self, engine: QuestionUnderstandingEngine):
        """None 동의어 맵이면 매칭 결과 없음"""
        result = engine.understand("매출 추세", None)
        assert len(result.synonym_matches) == 0

    def test_synonym_case_insensitive(self, engine: QuestionUnderstandingEngine):
        """대소문자 구분 없이 매칭"""
        synonym_map = {"OEE": "oee_index"}
        result = engine.understand("oee 현황을 보여줘", synonym_map)
        match = next(
            (m for m in result.synonym_matches if m.canonical_name == "oee_index"), None
        )
        assert match is not None


# ═══════════════════════════════════════════════════════════
# 3단계: 의도 분류 + 신뢰도
# ═══════════════════════════════════════════════════════════

class TestIntentClassification:
    """키워드 기반 의도 분류 + 신뢰도/모호성 테스트"""

    def test_intent_kpi_query(self, engine: QuestionUnderstandingEngine):
        """KPI 키워드가 있으면 kpi_query 의도"""
        result = engine.understand("이번 달 KPI 실적 보여줘")
        assert result.intent.top_intent == "kpi_query"

    def test_intent_trend(self, engine: QuestionUnderstandingEngine):
        """추세 키워드가 있으면 trend 의도"""
        result = engine.understand("매출 추세 변화를 보여줘")
        assert result.intent.top_intent == "trend"

    def test_intent_comparison(self, engine: QuestionUnderstandingEngine):
        """비교 키워드가 있으면 comparison 의도"""
        result = engine.understand("A팀 vs B팀 실적 비교")
        assert result.intent.top_intent == "comparison"

    def test_intent_root_cause(self, engine: QuestionUnderstandingEngine):
        """원인 키워드가 있으면 root_cause 의도"""
        result = engine.understand("불량률 증가의 원인이 뭐야?")
        assert result.intent.top_intent == "root_cause"

    def test_intent_general_fallback(self, engine: QuestionUnderstandingEngine):
        """어떤 키워드도 매칭 안 되면 general"""
        result = engine.understand("안녕하세요 반갑습니다")
        assert result.intent.top_intent == "general"

    def test_intent_confidence_high(self, engine: QuestionUnderstandingEngine):
        """명확한 키워드가 여럿이면 신뢰도가 높음"""
        result = engine.understand("매출 추세 변화 변동 시계열 추이")
        assert result.intent.confidence > 0.5

    def test_intent_confidence_low_ambiguous(self, engine: QuestionUnderstandingEngine):
        """여러 의도 키워드가 섞이면 신뢰도가 낮아짐"""
        # "추세"(trend) + "비교"(comparison) 동시 존재
        result = engine.understand("추세 비교")
        # 두 의도가 경합하므로 어느 하나가 압도적이지 않음
        assert result.intent.ambiguity_score > 0.0

    def test_intent_ambiguity_score(self, engine: QuestionUnderstandingEngine):
        """모호성 점수가 0.0~1.0 범위인지"""
        result = engine.understand("매출 추세")
        assert 0.0 <= result.intent.ambiguity_score <= 1.0

    def test_intent_top_k_format(self, engine: QuestionUnderstandingEngine):
        """top_k가 올바른 형식인지 (intent, score 키)"""
        result = engine.understand("KPI 지표 현황")
        for item in result.intent.top_k:
            assert "intent" in item
            assert "score" in item
            assert isinstance(item["score"], float)

    def test_intent_model_version(self, engine: QuestionUnderstandingEngine):
        """모델 버전 문자열이 설정되어 있는지"""
        result = engine.understand("매출 추세")
        assert result.intent.model_version == "keyword_v1"


# ═══════════════════════════════════════════════════════════
# 4단계: Fallback 모드
# ═══════════════════════════════════════════════════════════

class TestFallbackMode:
    """신뢰도/모호성 기반 fallback 모드 결정 테스트"""

    def test_fallback_reference_only(self, engine: QuestionUnderstandingEngine):
        """매우 낮은 신뢰도 → REFERENCE_ONLY"""
        result = engine.understand("안녕하세요")
        # "general" 의도, 매우 낮은 신뢰도
        assert result.fallback_mode == "REFERENCE_ONLY"

    def test_fallback_safe_narrow(self, engine: QuestionUnderstandingEngine):
        """중간 신뢰도 또는 높은 모호성 → SAFE_NARROW"""
        # "추세 변화 비교" — trend 키워드 2개 + comparison 1개로 중간 신뢰도
        result = engine.understand("추세 변화 비교")
        assert result.fallback_mode == "SAFE_NARROW"

    def test_fallback_none(self, engine: QuestionUnderstandingEngine):
        """높은 신뢰도 + 낮은 모호성 → NONE (정상 실행)"""
        result = engine.understand("매출 추세 변화 추이 시계열 분석")
        assert result.fallback_mode == "NONE"

    def test_fallback_mode_values(self, engine: QuestionUnderstandingEngine):
        """fallback_mode가 허용된 값 중 하나인지"""
        for q in ["안녕", "매출 추세", "KPI 지표 실적 성과"]:
            result = engine.understand(q)
            assert result.fallback_mode in ("NONE", "SAFE_NARROW", "REFERENCE_ONLY")


# ═══════════════════════════════════════════════════════════
# 5단계: 시멘틱 힌트 생성
# ═══════════════════════════════════════════════════════════

class TestSemanticHints:
    """LLM 프롬프트 주입용 힌트 생성 테스트"""

    def test_semantic_hints_generation(self, engine: QuestionUnderstandingEngine, sample_synonym_map: dict):
        """동의어 매칭이 있으면 힌트가 생성되는지"""
        result = engine.understand("매출액 현황", sample_synonym_map)
        assert len(result.semantic_hints) > 0
        # 힌트 형식 검증
        hint = result.semantic_hints[0]
        assert "매출액" in hint or "매출" in hint
        assert "revenue_total" in hint

    def test_no_hints_without_matches(self, engine: QuestionUnderstandingEngine):
        """동의어 매칭이 없으면 힌트도 없음"""
        result = engine.understand("날씨 정보", {})
        assert len(result.semantic_hints) == 0

    def test_hints_count_matches_synonyms(self, engine: QuestionUnderstandingEngine, sample_synonym_map: dict):
        """힌트 수 == 동의어 매칭 수"""
        result = engine.understand("매출액과 불량률", sample_synonym_map)
        assert len(result.semantic_hints) == len(result.synonym_matches)


# ═══════════════════════════════════════════════════════════
# 통합 테스트: 전체 파이프라인
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """understand() 메서드의 전체 파이프라인 통합 테스트"""

    def test_full_pipeline_integration(self, engine: QuestionUnderstandingEngine, sample_synonym_map: dict):
        """5단계 전체가 올바르게 동작하는지 종합 검증"""
        result = engine.understand("매출액의 추세는 어떤가요?", sample_synonym_map)

        # 결과 타입 검증
        assert isinstance(result, QuestionUnderstandingResult)

        # 원본 질문 보존
        assert result.raw_question == "매출액의 추세는 어떤가요?"

        # 정규화된 질문 (조사 제거)
        assert result.normalized_question != result.raw_question

        # 동의어 매칭
        assert len(result.synonym_matches) > 0
        revenue_match = next(
            (m for m in result.synonym_matches if m.canonical_name == "revenue_total"), None
        )
        assert revenue_match is not None

        # 의도 분류 (추세 키워드가 있으므로 trend)
        assert result.intent.top_intent == "trend"
        assert 0.0 < result.intent.confidence <= 1.0
        assert 0.0 <= result.intent.ambiguity_score <= 1.0
        assert len(result.intent.top_k) > 0

        # Fallback 모드
        assert result.fallback_mode in ("NONE", "SAFE_NARROW", "REFERENCE_ONLY")

        # 시멘틱 힌트
        assert len(result.semantic_hints) == len(result.synonym_matches)

    def test_pipeline_with_no_synonym_map(self, engine: QuestionUnderstandingEngine):
        """동의어 맵 없이도 의도 분류는 동작"""
        result = engine.understand("KPI 지표를 보여줘")
        assert result.intent.top_intent == "kpi_query"
        assert len(result.synonym_matches) == 0
        assert len(result.semantic_hints) == 0

    def test_pipeline_english_question(self, engine: QuestionUnderstandingEngine):
        """영어 질문도 처리 가능"""
        synonym_map = {"revenue": "revenue_total"}
        result = engine.understand("Show me the revenue trend", synonym_map)
        assert result.intent.top_intent == "trend"
        assert len(result.synonym_matches) > 0

    def test_pipeline_empty_question(self, engine: QuestionUnderstandingEngine):
        """빈 질문도 에러 없이 처리"""
        result = engine.understand("", {})
        assert result.intent.top_intent == "general"
        assert result.fallback_mode == "REFERENCE_ONLY"
