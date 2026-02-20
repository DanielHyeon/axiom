# Axiom Core - 에이전트 아키텍처

## 이 문서가 답하는 질문

- ReAct 패턴은 어떻게 구현되는가?
- HITL 3단계 신뢰도 모델의 실제 작동 방식은?
- 에이전트의 도구 호출 흐름은 어떻게 진행되는가?

<!-- affects: backend, api -->
<!-- requires-update: 01_architecture/agent-orchestration.md -->

---

## 1. ReAct 에이전트 패턴

### 1.1 LangGraph create_react_agent

K-AIR의 langchain-react-main 패턴을 직접 활용한다.

```python
# app/orchestrator/react_agent.py

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from app.core.llm_factory import LLMFactory
from app.orchestrator.tool_loader import SafeToolLoader

async def create_agent_for_workitem(
    workitem: dict,
    activity: dict,
    tenant_id: str,
) -> tuple:
    """워크아이템 실행을 위한 ReAct 에이전트 생성"""

    # 1. LLM 생성
    llm = LLMFactory.create(
        provider=activity.get("llm_provider", "openai"),
        model=activity.get("llm_model", "gpt-4o"),
        temperature=0.0,
    )

    # 2. 도구 로드 (우선순위 순)
    tools = await SafeToolLoader.create_tools_for_activity(
        activity=activity,
        tenant_id=tenant_id,
    )

    # 3. 시스템 프롬프트 구성
    system_prompt = f"""당신은 Axiom 비즈니스 프로세스 인텔리전스 에이전트입니다.
현재 작업: {activity['name']}
지시사항: {activity['instruction']}

규칙:
1. 주어진 도구를 사용하여 작업을 수행하세요.
2. 불확실한 경우 도구를 사용하여 검증하세요.
3. 결과에 대한 신뢰도를 0.0~1.0으로 평가하세요.
4. 전문적 판단이 필요한 경우 신뢰도를 0.7 이하로 설정하세요.
"""

    # 4. ReAct 에이전트 생성
    agent = create_react_agent(
        llm,
        tools,
        state_modifier=system_prompt,
    )

    return agent, tools
```

### 1.2 ReAct 실행 루프

```
Thought: "데이터 수치를 검증해야 합니다. DB에서 시스템 기록을 조회합니다."
     |
Action: search_records(case_id="...", source="XYZ")
     |
Observation: {"reported_value": 5000000000, "system_value": 4800000000}
     |
Thought: "보고 수치(50억)과 시스템 수치(48억) 차이가 4%입니다. 허용 범위 내입니다."
     |
Action: classify_data(type="일반 데이터", confidence=0.92)
     |
Observation: {"classified": true, "type": "일반 데이터"}
     |
Final Answer: {
  "data_verified": true,
  "discrepancy": "4%",
  "classification": "일반 데이터",
  "confidence": 0.92
}
```

---

## 2. HITL 3단계 신뢰도

### 2.1 신뢰도 산정 방법

```python
def calculate_confidence(agent_result: dict) -> float:
    """에이전트 결과의 신뢰도 계산"""
    base_confidence = agent_result.get("confidence", 0.5)

    # 조정 요인
    adjustments = 0.0

    # 도구 사용 결과 기반 조정
    if agent_result.get("tools_verified"):
        adjustments += 0.1  # DB 검증 완료 시 +10%

    # 과거 유사 작업 성공률 기반 조정
    historical_accuracy = agent_result.get("historical_accuracy", 0.0)
    adjustments += historical_accuracy * 0.1  # 과거 정확도 반영

    # 전문적 판단 포함 여부
    if agent_result.get("requires_expert_judgment"):
        adjustments -= 0.2  # 전문적 판단 필요 시 -20%

    return min(max(base_confidence + adjustments, 0.0), 1.0)
```

### 2.2 신뢰도별 처리 경로

| 신뢰도 | 처리 | Workitem 상태 | 사용자 행동 |
|--------|------|-------------|-----------|
| >= 0.99 | 자동 완료 | TODO -> DONE | 없음 (결과 확인만 가능) |
| 0.80 ~ 0.99 | 결과 제시 + 승인 대기 | TODO -> SUBMITTED | 승인 또는 수정 |
| < 0.80 | 사람이 직접 수행 | TODO (에이전트 드래프트 참고 가능) | 직접 작업 |

---

## 3. 에이전트 실패 처리

```
[결정] LLM 실패는 시스템 장애가 아닌 "에이전트 태스크 실패"로 처리한다.
[결정] 에이전트 실패 시 Workitem은 TODO 상태로 복귀하고, MANUAL 모드로 전환한다.
[결정] 에이전트 실패 이력은 모니터링에 기록하고, 반복 실패 패턴 분석에 활용한다.

실패 유형별 처리:
  LLM 타임아웃      -> 재시도 3회 -> TODO로 복귀 + 알림
  LLM 출력 파싱 실패 -> 재시도 1회 (프롬프트 수정) -> TODO로 복귀
  도구 실행 실패     -> Saga 보상 -> TODO로 복귀 + 알림
  신뢰도 미달       -> SUBMITTED (HITL 대기) -> 사람이 확인
```

---

## 근거

- K-AIR process-gpt-langchain-react-main (create_react_agent 활용)
- K-AIR 역설계 보고서 섹션 7.4 (HITL 3단계 신뢰도)
- K-AIR 역설계 보고서 섹션 8.1 (에이전트 프레임워크)
