# Axiom Core - 3티어 지식 관리

## 이 문서가 답하는 질문

- Memory, DMN Rules, Skills 각각은 무엇이고 어떤 차이가 있는가?
- 사용자 피드백이 어떤 지식 저장소에 학습되는지 어떻게 결정하는가?
- 지식 간 충돌은 어떻게 해결하는가?

<!-- affects: backend, data -->
<!-- requires-update: 06_data/database-schema.md -->

---

## 1. 3티어 지식 구조

### 1.1 저장소별 특성

| 저장소 | 유형 | 저장 위치 | 검색 방식 | 예시 |
|--------|------|----------|----------|------|
| **Memory** | 비정형 지식 (경험, 사례) | pgvector (벡터 임베딩) | 유사도 검색 (cosine) | "지난 XYZ 프로젝트에서 보조 데이터 최적화율은 5%였다" |
| **DMN Rules** | 정형 규칙 (의사결정 테이블) | proc_def.definition (JSONB) | 규칙 매칭 (정확) | IF KPI영향="없음" THEN 데이터분류="일반 데이터" |
| **Skills** | 실행 가능 도구 (API/함수) | MCP 서버 등록 | 도구 호출 | `calculate_optimization_rate(baseline, target, period)` |

### 1.2 우선순위

```
에이전트가 작업 수행 시:
  1. Skills 먼저 확인 (도메인 전용 도구가 있으면 사용)
  2. DMN Rules 확인 (규칙이 있으면 적용)
  3. Memory 참조 (유사 경험이 있으면 참고)
  4. 위 모두 없으면 LLM의 일반 지식에 의존
```

---

## 2. 학습 라우팅 결정

### 2.1 LearningRouter

```python
# app/orchestrator/learning_router.py
# K-AIR agent-feedback의 LearningRouter에서 이식

class LearningRouter:
    """피드백을 어떤 지식 저장소에 학습할지 결정"""

    async def route(self, feedback: dict, analysis: dict) -> str:
        """
        Returns: "MEMORY" | "DMN_RULE" | "SKILL" | "MIXED"
        """
        content = feedback["content"]
        feedback_type = feedback["feedback_type"]

        # 규칙 기반 라우팅
        if self._is_decision_rule(content):
            return "DMN_RULE"
        elif self._is_executable_tool(content):
            return "SKILL"
        elif self._is_experiential(content):
            return "MEMORY"
        else:
            # LLM으로 판단
            return await self._llm_route(content)

    def _is_decision_rule(self, content: str) -> bool:
        """의사결정 규칙인지 판별"""
        rule_indicators = [
            "~인 경우", "~이면", "~일 때",
            "IF", "WHEN", "규칙", "기준",
            "이상", "이하", "초과", "미만",
        ]
        return any(indicator in content for indicator in rule_indicators)

    def _is_executable_tool(self, content: str) -> bool:
        """실행 가능한 도구인지 판별"""
        tool_indicators = [
            "계산", "산정", "변환", "검증",
            "API", "함수", "도구",
        ]
        return any(indicator in content for indicator in tool_indicators)
```

### 2.2 라우팅 예시

| 피드백 | 라우팅 | 이유 |
|--------|--------|------|
| "KPI 영향이 없으면 일반 데이터이다" | **DMN_RULE** | IF-THEN 규칙 |
| "최적화율은 (개선항목수/총항목수)*100으로 계산한다" | **SKILL** | 계산 도구 |
| "XYZ 프로젝트에서 이 방식이 효과적이었다" | **MEMORY** | 경험적 지식 |
| "핵심 데이터는 KPI에 영향이 있을 때만 인정하되, 가중치의 80%를 적용한다" | **MIXED** (DMN + Memory) | 규칙 + 맥락 |

---

## 3. 충돌 해결

### 3.1 충돌 수준별 처리

| 충돌 수준 | 처리 | 예시 |
|----------|------|------|
| **NO** | 새 지식 추가 (CREATE) | 기존에 없던 새로운 규칙 |
| **LOW** | 자동 머지 (UPDATE) | 기존 규칙의 수치만 변경 (최적화율 5% -> 7%) |
| **MEDIUM** | LLM 판단 후 머지 | 기존 규칙과 부분 모순 |
| **HIGH** | 사람 개입 필요 (SKIP + 알림) | 기존 규칙과 완전 모순 |

---

## 근거

- K-AIR process-gpt-agent-feedback-main (FeedbackProcessor, LearningRouter, ConflictAnalyzer)
- K-AIR 역설계 보고서 섹션 8.2 (에이전트 지식 학습 루프)
