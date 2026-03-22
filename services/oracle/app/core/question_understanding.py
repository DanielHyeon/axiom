"""
Sprint 4: 질문 이해 엔진 — 온톨로지 동의어 확장 + 의도 신뢰도 평가

사용자 질문을 시멘틱 레이어의 언어로 번역하는 전처리 파이프라인.
- 1단계: 텍스트 정규화 (소문자 + 공백 정리 + 한글 조사 제거)
- 2단계: 동의어 확장 (synonym_map 기반 용어 → 정규 개념 매칭)
- 3단계: 의도 분류 + 신뢰도 점수 산출
- 4단계: Fallback 모드 결정 (신뢰도 낮으면 안전 모드)
- 5단계: LLM에 주입할 시멘틱 힌트 생성
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SynonymMatch:
    """동의어 매칭 결과 — 사용자 표현과 정규 개념의 연결"""

    original_term: str       # 사용자가 쓴 표현 (예: "매출액")
    canonical_name: str      # 정규 개념 이름 (예: "revenue_total")
    match_type: str          # "exact" | "normalized" | "partial"
    confidence: float        # 매칭 신뢰도 (0.0~1.0)


@dataclass
class IntentDecision:
    """의도 분류 결과 + 신뢰도 — 질문이 무엇을 원하는지 판단"""

    top_intent: str           # 가장 유력한 의도 (예: "kpi_query")
    confidence: float         # 의도 신뢰도 (0.0~1.0)
    top_k: list[dict]         # 상위 k개 의도 점수 목록
    ambiguity_score: float    # 모호성 점수 — 1차-2차 격차 기반 (높을수록 모호)
    model_version: str = "keyword_v1"


@dataclass
class QuestionUnderstandingResult:
    """질문 이해 종합 결과 — 파이프라인 전체 출력"""

    raw_question: str                    # 원본 질문
    normalized_question: str             # 정규화된 질문
    synonym_matches: list[SynonymMatch]  # 동의어 매칭 목록
    intent: IntentDecision               # 의도 분류 결과
    fallback_mode: str                   # "NONE" | "SAFE_NARROW" | "REFERENCE_ONLY"
    semantic_hints: list[str]            # LLM에 주입할 힌트 목록


# 한국어 조사 패턴 — 단어 뒤에 오는 조사를 제거하기 위한 정규식
# 순서 중요: 긴 조사(에서, 으로)를 먼저 매칭해야 짧은 것(에, 로)에 먹히지 않는다
_KOREAN_PARTICLE_PATTERN = re.compile(
    r"(에서|으로|는|은|이|가|을|를|의|에|로|와|과|도)(?=\s|$)"
)

# 의도 분류용 키워드 사전 — 각 의도에 해당하는 한국어+영어 키워드
_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "root_cause": ("원인", "왜", "root cause", "why", "이유", "근본"),
    "trend": ("추세", "변화", "trend", "변동", "시계열", "추이", "증가", "감소"),
    "comparison": ("비교", "대비", "compare", "vs", "차이", "대조"),
    "forecast_support": ("예측", "전망", "forecast", "predict", "예상"),
    "anomaly": ("이상", "비정상", "anomaly", "outlier", "특이"),
    "segment": ("세그먼트", "그룹", "segment", "분류", "분포"),
    "kpi_query": ("kpi", "지표", "metric", "성과", "실적", "현황", "수치"),
}


class QuestionUnderstandingEngine:
    """온톨로지 기반 질문 이해 엔진

    NL2SQL 파이프라인에서 LLM 호출 전에 사용하여,
    사용자의 자연어 질문을 시멘틱 레이어 용어로 번역한다.
    """

    def understand(
        self,
        question: str,
        synonym_map: dict[str, str] | None = None,
    ) -> QuestionUnderstandingResult:
        """질문을 분석하여 시멘틱 레이어 언어로 번역한다.

        Args:
            question: 사용자의 원본 질문 (예: "매출액의 추세는?")
            synonym_map: 동의어 맵 (surface_form → concept_id)

        Returns:
            QuestionUnderstandingResult: 정규화 + 동의어 + 의도 + 힌트 종합
        """
        # 1단계: 텍스트 정규화 (소문자, 공백, 조사 제거)
        normalized = self._normalize_text(question)

        # 2단계: 동의어 확장 (synonym_map 기반)
        matches = self._expand_synonyms(normalized, synonym_map or {})

        # 3단계: 의도 분류 + 신뢰도 점수
        intent = self._classify_intent_with_confidence(normalized, matches)

        # 4단계: Fallback 모드 결정 (신뢰도 기반)
        fallback = self._decide_fallback(intent, matches)

        # 5단계: LLM 힌트 생성
        hints = self._build_semantic_hints(matches)

        return QuestionUnderstandingResult(
            raw_question=question,
            normalized_question=normalized,
            synonym_matches=matches,
            intent=intent,
            fallback_mode=fallback,
            semantic_hints=hints,
        )

    # ── 내부 메서드 ─────────────────────────────────────────

    @staticmethod
    def _normalize_text(text: str) -> str:
        """텍스트 정규화 — 소문자 변환, 공백 정리, 한글 조사 제거

        예시: "매출액의 추세는 어떤가요?" → "매출액 추세 어떤가요?"
        """
        cleaned = text.lower().strip()
        # 한국어 조사 제거 (은/는/이/가/을/를/의/에/에서/으로/로/와/과/도)
        cleaned = _KOREAN_PARTICLE_PATTERN.sub("", cleaned)
        # 연속 공백을 하나로 정리
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _expand_synonyms(
        text: str,
        synonym_map: dict[str, str],
    ) -> list[SynonymMatch]:
        """동의어 맵을 사용하여 질문의 용어를 정규 개념으로 매칭

        매칭 방식:
        - exact: surface_form이 정규화된 질문에 그대로 포함
        - normalized: surface_form을 조사 제거 후 매칭

        중복 concept은 높은 confidence 우선으로 하나만 남긴다.
        """
        matches: list[SynonymMatch] = []
        text_lower = text.lower()

        for surface_form, concept_id in synonym_map.items():
            sf_lower = surface_form.lower()

            # 정확 매칭: surface_form이 질문 텍스트에 그대로 포함
            if sf_lower in text_lower:
                matches.append(SynonymMatch(
                    original_term=surface_form,
                    canonical_name=concept_id,
                    match_type="exact",
                    confidence=0.95,
                ))
                continue

            # 정규화 매칭: 조사 제거 후 매칭 시도
            sf_normalized = _KOREAN_PARTICLE_PATTERN.sub("", sf_lower)
            sf_normalized = re.sub(r"\s+", " ", sf_normalized).strip()
            if sf_normalized and sf_normalized in text_lower:
                matches.append(SynonymMatch(
                    original_term=surface_form,
                    canonical_name=concept_id,
                    match_type="normalized",
                    confidence=0.85,
                ))

        # 같은 concept에 여러 surface_form이 매칭되면 confidence 높은 것만
        seen: dict[str, SynonymMatch] = {}
        for m in sorted(matches, key=lambda x: -x.confidence):
            if m.canonical_name not in seen:
                seen[m.canonical_name] = m
        return list(seen.values())

    @staticmethod
    def _classify_intent_with_confidence(
        text: str,
        matches: list[SynonymMatch],
    ) -> IntentDecision:
        """키워드 기반 의도 분류 + 신뢰도 점수 산출

        각 의도별 키워드 히트 수를 세고, 동의어 매칭 보너스를 더한다.
        1차와 2차 의도의 점수 격차로 모호성을 판단한다.
        """
        text_lower = text.lower()

        # 각 의도별 점수 계산
        scores: dict[str, float] = {}
        for intent, keywords in _INTENT_KEYWORDS.items():
            hit_count = sum(1 for kw in keywords if kw in text_lower)
            # 동의어 매칭이 있으면 보너스 0.1 (개념이 인식되었으므로 의도 판단 보강)
            concept_bonus = 0.1 * len(matches) if matches else 0
            scores[intent] = min(1.0, hit_count * 0.3 + concept_bonus)

        # 점수 내림차순 정렬
        sorted_intents = sorted(scores.items(), key=lambda x: -x[1])

        # 1위 의도: 점수 > 0이면 채택, 아니면 "general"
        top_intent = sorted_intents[0][0] if sorted_intents[0][1] > 0 else "general"
        top_score = sorted_intents[0][1] if sorted_intents[0][1] > 0 else 0.1
        second_score = sorted_intents[1][1] if len(sorted_intents) > 1 else 0.0

        # 신뢰도 = 1위 점수 * (1위-2위 격차 보정)
        # 격차가 클수록 확신이 높다
        gap = top_score - second_score
        confidence = min(1.0, top_score * (0.5 + 0.5 * gap))

        # 모호성 = 격차가 작을수록 높음 (0.0 = 명확, 1.0 = 매우 모호)
        ambiguity = 1.0 - min(1.0, gap * 2)

        # 상위 3개 의도 (점수 > 0인 것만)
        top_k = [
            {"intent": intent, "score": round(score, 3)}
            for intent, score in sorted_intents[:3]
            if score > 0
        ]

        return IntentDecision(
            top_intent=top_intent,
            confidence=round(confidence, 3),
            top_k=top_k,
            ambiguity_score=round(ambiguity, 3),
        )

    @staticmethod
    def _decide_fallback(
        intent: IntentDecision,
        matches: list[SynonymMatch],
    ) -> str:
        """신뢰도/모호성 기반 fallback 모드 결정

        - NONE: 정상 실행 (높은 신뢰도)
        - SAFE_NARROW: 범위를 좁혀서 안전하게 실행 (중간 신뢰도)
        - REFERENCE_ONLY: 참고용으로만 사용 (매우 낮은 신뢰도)
        """
        if intent.confidence < 0.3:
            return "REFERENCE_ONLY"
        if intent.confidence < 0.5 or intent.ambiguity_score > 0.7:
            return "SAFE_NARROW"
        return "NONE"

    @staticmethod
    def _build_semantic_hints(matches: list[SynonymMatch]) -> list[str]:
        """LLM 프롬프트에 주입할 동의어 해석 힌트 생성

        예: "질문의 '매출액'은(는) 승인된 개념 'revenue_total'을(를) 의미합니다."
        """
        hints: list[str] = []
        for m in matches:
            hints.append(
                f"질문의 '{m.original_term}'은(는) "
                f"승인된 개념 '{m.canonical_name}'을(를) 의미합니다."
            )
        return hints
