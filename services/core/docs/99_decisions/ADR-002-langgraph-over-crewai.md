# ADR-002: CrewAI + A2A SDK 대신 LangGraph 단일 프레임워크 선택

## 상태

Accepted

## 배경

K-AIR/Process-GPT 시스템은 에이전트 오케스트레이션에 **3개의 서로 다른 프레임워크**를 사용하고 있다:

1. **CrewAI**: 역할 기반 에이전트 실행 (`crewai-action-main`, `crewai-deep-research-main`)
2. **A2A SDK**: Agent-to-Agent 프로토콜 오케스트레이션 (`a2a-orch-main`)
3. **LangChain/LangGraph**: ReAct 추론 + MCP 도구 호출 (`langchain-react-main`, `agent-feedback-main`)

**K-AIR 에이전트 프레임워크 현황**:

| 저장소 | 프레임워크 | 패턴 | 통신 |
|--------|-----------|------|------|
| crewai-action | CrewAI | Role-based Crew | A2A SDK (폴링 5초) |
| crewai-deep-research | CrewAI Flow | 상태 머신 | 내부 (Flow) |
| agent-feedback | LangChain | ReAct 5단계 | Supabase 폴링 |
| langchain-react | LangGraph | ReAct | CLI/FastAPI |
| voice-agent | LangGraph | Voice ReAct | WebSocket |
| a2a-orch | A2A SDK | Sync/Async | HTTP + Webhook |

**문제**:
1. 3개 프레임워크의 개념 모델이 서로 달라 통합/유지보수가 어렵다.
2. CrewAI의 "역할 기반 Crew" 모델은 BPM 워크아이템 기반의 Axiom 설계와 맞지 않는다.
3. A2A SDK는 별도 Webhook Receiver Pod가 필요하고, 비동기 결과 대기가 복잡하다.
4. CrewAI는 내부적으로 LangChain을 래핑하므로, 직접 LangGraph를 사용하면 중간 추상화를 제거할 수 있다.
5. HITL(Human-in-the-Loop) 구현 시 CrewAI의 `human_input=True`는 동기식이라 웹 환경에 부적합하다.

## 검토한 옵션

### 옵션 1: CrewAI + A2A SDK 유지 (K-AIR 현행)

**장점**:
- K-AIR 코드를 최소 변경으로 이식 가능
- CrewAI의 역할 기반 모델이 직관적
- A2A SDK의 에이전트 간 표준 프로토콜

**단점**:
- 3개 프레임워크 동시 유지 (CrewAI + A2A SDK + LangChain)
- CrewAI 내부의 LangChain 의존으로 버전 충돌 위험
- HITL을 웹에서 구현하려면 CrewAI 코어를 우회해야 함
- A2A SDK의 별도 Webhook Receiver Pod 운영 필요
- CrewAI의 agent.execute()가 동기식이라 비동기 FastAPI와 충돌

### 옵션 2: LangGraph 단일 프레임워크 (선택)

**장점**:
- StateGraph 하나로 모든 에이전트 패턴 구현 가능:
  - ReAct 추론 (기존 LangChain ReAct 패턴)
  - 역할 기반 실행 (StateGraph 노드로 역할 분리)
  - 멀티에이전트 오케스트레이션 (서브그래프 합성)
  - 상태 머신 (CrewAI Flow 대체)
- `interrupt_before` 네이티브 지원으로 HITL 구현이 자연스러움
- 비동기 실행 (`ainvoke`) 네이티브 지원
- LangSmith 추적 통합 (디버깅, 비용 모니터링)
- 그래프 시각화로 오케스트레이션 흐름 확인 가능

**단점**:
- K-AIR의 CrewAI 코드(crewai-action, deep-research)를 LangGraph로 재작성 필요
- A2A SDK의 에이전트 간 통신을 자체 구현해야 함
- LangGraph의 학습 곡선이 CrewAI보다 가파름

### 옵션 3: AutoGen + LangGraph 조합

**장점**:
- AutoGen의 멀티에이전트 대화 모델
- 그룹 채팅 패턴 네이티브 지원

**단점**:
- Microsoft 생태계 의존
- BPM 워크아이템 기반 실행과 패러다임 불일치
- LangGraph와 중복되는 추상화 레이어

## 선택한 결정

**옵션 2: LangGraph 단일 프레임워크**

## 근거

### 1. HITL 구현의 결정적 차이

```python
# CrewAI의 HITL (동기식 - 웹에서 사용 불가)
agent = Agent(
    role="데이터 분석가",
    human_input=True,  # input() 호출 - CLI에서만 작동
)

# LangGraph의 HITL (비동기 - 웹 환경 완전 지원)
graph = StateGraph(AgentState)
graph.add_node("analyze", analyze_data)
graph.add_node("human_review", human_review_node)

# interrupt_before로 실행 중단 → 웹 UI에서 확인 → 재개
app = graph.compile(
    checkpointer=PostgresSaver(pool),
    interrupt_before=["human_review"],
)

# 실행 → 중단점에서 자동 멈춤
result = await app.ainvoke(state, config={"thread_id": "case-123"})
# ... 사용자 웹 UI에서 확인 ...
# 재개
result = await app.ainvoke(None, config={"thread_id": "case-123"})
```

Axiom의 BPM 엔진은 HITL 3단계 신뢰도(99%+ 자동, 80%+ 감독, <80% 수동)를 핵심 기능으로 요구한다. LangGraph의 `interrupt_before`는 이를 가장 자연스럽게 구현한다.

### 2. K-AIR 패턴의 LangGraph 매핑

| K-AIR 패턴 | K-AIR 구현 | LangGraph 구현 |
|-----------|-----------|---------------|
| 역할 기반 Crew | CrewAI Agent/Crew | StateGraph 노드 (역할별) |
| 보고서 생성 Flow | CrewAI Flow (상태 머신) | StateGraph + 조건부 엣지 |
| A2A 동기 호출 | A2A SDK AgentExecutor | 서브그래프 합성 (직접 호출) |
| A2A 비동기 | Webhook Receiver Pod | Redis Streams + Worker |
| ReAct 추론 | LangChain ReAct | LangGraph create_react_agent |
| MCP 도구 호출 | SafeToolLoader | LangGraph ToolNode + SafeToolLoader |

### 3. 9노드 오케스트레이터 아키텍처

LangGraph StateGraph로 Axiom의 전체 에이전트 흐름을 단일 그래프로 표현:

```python
# 9노드 오케스트레이터 (LangGraph StateGraph)
graph = StateGraph(OrchestratorState)

# 노드 정의
graph.add_node("classify_intent", classify_user_intent)
graph.add_node("load_context", load_case_context)
graph.add_node("select_tools", safe_tool_selection)
graph.add_node("execute_agent", run_react_agent)
graph.add_node("confidence_check", evaluate_confidence)
graph.add_node("hitl_review", human_review_gate)
graph.add_node("apply_result", apply_to_workitem)
graph.add_node("learn_feedback", update_knowledge)
graph.add_node("respond", format_response)

# 조건부 엣지 (신뢰도 기반 HITL 분기)
graph.add_conditional_edges(
    "confidence_check",
    route_by_confidence,
    {
        "auto": "apply_result",        # >= 99%
        "supervised": "hitl_review",    # 80-99%
        "manual": "hitl_review",        # < 80%
    }
)
```

### 4. 팀 규모와 기술 스택 통일

소규모 팀(2-3명)에서 CrewAI, A2A SDK, LangGraph 3개 프레임워크의 개념 모델, API, 디버깅 방법을 모두 숙지하는 것은 비현실적이다. LangGraph 하나에 집중하면:

- 학습 시간 1/3로 절감
- 디버깅 도구 통일 (LangSmith)
- 버전 의존성 충돌 제거 (CrewAI의 내부 LangChain 버전과 Axiom의 LangChain 버전 충돌 방지)

### 5. BPM 엔진과의 자연스러운 통합

Axiom의 BPM 엔진은 워크아이템 기반이다. LangGraph의 StateGraph는 상태 기반 실행 모델이므로 워크아이템 상태(TODO -> IN_PROGRESS -> SUBMITTED -> DONE)와 그래프 노드 전이를 1:1로 매핑할 수 있다.

CrewAI의 "역할 기반 Crew" 모델은 작업 할당/실행의 추상화가 BPM 워크아이템과 맞지 않아 중간 어댑터가 필요했다.

## 결과

### 긍정적 영향
- 단일 프레임워크로 에이전트 코드 통일 (학습/유지보수 비용 감소)
- HITL 구현이 프레임워크 레벨에서 자연스럽게 지원됨
- 별도 Webhook Receiver Pod 불필요 (인프라 단순화)
- LangSmith 통합으로 에이전트 실행 추적/디버깅 통일
- BPM 워크아이템과 그래프 노드의 자연스러운 매핑

### 부정적 영향
- K-AIR의 CrewAI 코드 재작성 필요 (~5일):
  - `crewai-action-main` → LangGraph ToolNode + StateGraph
  - `crewai-deep-research-main` → LangGraph 멀티스텝 워크플로우
- A2A SDK 오케스트레이션 자체 구현 필요 (~3일):
  - 동기 호출 → 서브그래프 합성
  - 비동기 호출 → Redis Streams + Worker

### 마이그레이션 작업

| K-AIR 소스 | Axiom 대상 | 작업 | 예상 공수 |
|-----------|-----------|------|:---------:|
| `crewai-action-main` | `app/orchestrator/tool_executor.py` | CrewAI Tool → LangGraph ToolNode | 2일 |
| `crewai-deep-research-main` | `app/orchestrator/research_flow.py` | CrewAI Flow → LangGraph StateGraph | 3일 |
| `a2a-orch-main` 동기 모드 | `app/orchestrator/langgraph_flow.py` | A2A → 서브그래프 직접 호출 | 1일 |
| `a2a-orch-main` 비동기 모드 | `app/workers/agent_async.py` | Webhook → Redis Streams | 2일 |
| `agent-feedback-main` | `app/orchestrator/agent_loop.py` | ReAct 5단계 유지 (변경 최소) | 1일 |
| `langchain-react-main` | `app/orchestrator/react_agent.py` | 패턴 직접 활용 (변경 최소) | 0.5일 |

총 예상 공수: **~9.5일**

## 재평가 조건

- CrewAI가 네이티브 비동기 + interrupt 패턴을 지원하는 경우 → 재검토
- LangGraph의 라이선스가 상업적 제한을 추가하는 경우 → 대안 프레임워크 검토
- 에이전트가 10종 이상으로 확장되어 표준 통신 프로토콜이 필요한 경우 → A2A 프로토콜 재도입 검토
- Google ADK(Agent Development Kit) 등 새로운 표준이 등장하는 경우 → 마이그레이션 비용 대비 검토
