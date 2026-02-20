# Axiom Core - 에이전트 오케스트레이션 아키텍처

## 이 문서가 답하는 질문

- LangGraph 멀티에이전트 오케스트레이션은 어떻게 동작하는가?
- 에이전트 도구(Tool)의 우선순위는 어떻게 결정되는가?
- HITL(Human-in-the-Loop) 중단점은 어디에 존재하는가?
- 3티어 지식 학습(Memory/DMN/Skills)은 어떻게 작동하는가?
- K-AIR의 CrewAI + A2A 패턴을 LangGraph로 어떻게 전환하는가?

<!-- affects: api, llm, frontend -->
<!-- requires-update: 05_llm/agent-architecture.md, 02_api/agent-api.md -->

---

## 1. 에이전트 오케스트레이션 개요

### 1.1 설계 원칙

```
[결정] CrewAI + A2A SDK를 LangGraph 단일 프레임워크로 통합한다.
[근거] CrewAI는 역할 기반 에이전트에 특화되어 있지만, LangGraph는 순환 가능한
       상태 머신을 지원하여 더 유연한 에이전트 워크플로우를 구성할 수 있다.
       A2A SDK의 HTTP 폴링 방식보다 LangGraph의 내장 에이전트 간 통신이 효율적이다.

[결정] 모든 에이전트는 ReAct (Reasoning + Acting) 패턴을 기반으로 한다.
[근거] K-AIR의 Text2SQL, agent-feedback, langchain-react 모두 ReAct를 사용하며,
       검증된 패턴이다. "추론 후 행동" 루프가 신뢰도를 높인다.

[결정] HITL 중단점은 LangGraph의 interrupt_before/interrupt_after로 구현한다.
[근거] 프로세스 실행 중 사람의 승인이 필요한 지점을 명시적으로 선언할 수 있다.
```

### 1.2 K-AIR -> Axiom 에이전트 전환 매핑

| K-AIR 컴포넌트 | 프레임워크 | Axiom 전환 | 전환 방식 |
|---------------|-----------|-----------|----------|
| crewai-action | CrewAI | LangGraph Tool Node | Role -> Tool 함수 전환 |
| deep-research | CrewAI Flow | LangGraph StateGraph | 5-Crew 상태머신 -> 노드 그래프 |
| agent-feedback | LangChain ReAct | LangGraph ReAct | 패턴 유지, 프레임워크만 전환 |
| langchain-react | LangGraph ReAct | LangGraph ReAct | 거의 그대로 이식 |
| a2a-orch | A2A SDK | LangGraph 멀티에이전트 | HTTP 폴링 -> 내부 에이전트 호출 |
| agent-utils (SafeToolLoader) | 자체 구현 | 그대로 이식 | 도구 우선순위 로직 보존 |

---

## 2. LangGraph 오케스트레이터 아키텍처

### 2.1 10-노드 오케스트레이터 그래프

```
                          +--[START]--+
                          |           |
                          v           |
                   +------+------+    |
                   | 1. Route    |    |
                   | (의도 분류) |    |
                   +------+------+    |
                          |           |
            +-------------+-------------+--------------+
            |             |             |              |
            v             v             v              v
     +------+------+ +---+----+ +------+------+ +-----+--------+
     | 2. Process  | | 3. Doc | | 4. Query    | | 10. Mining   |
     | (BPM 실행)  | | (문서) | | (데이터)    | | (프로세스    |
     +------+------+ +---+----+ +------+------+ |  마이닝)     |
            |             |             |        +-----+--------+
            v             v             v              |
     +------+------+ +---+----+ +------+------+       |
     | 5. Agent    | | 6. RAG | | 7. NL2SQL   |       |
     | (도구 실행) | | (검색) | | (Oracle)    |       |
     +------+------+ +---+----+ +------+------+       |
            |             |             |              |
            +-------------+-------------+--------------+
                          |
                          v
                   +------+------+
                   | 8. HITL     |
                   | (사람 확인) |  <-- interrupt_before (SUPERVISED 모드)
                   +------+------+
                          |
                          v
                   +------+------+
                   | 9. Complete |
                   | (결과 반환) |
                   +------+------+
                          |
                          v
                       [END]
```

### 2.2 그래프 구현

```python
# app/orchestrator/langgraph_flow.py

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated, Literal
from operator import add

class OrchestratorState(TypedDict):
    """오케스트레이터 상태"""
    # 입력
    user_message: str
    workitem_id: str
    activity: dict                    # ProcessActivity 직렬화
    tenant_id: str

    # 라우팅
    intent: str                       # process, document, query, agent
    agent_mode: str                   # AUTONOMOUS, SUPERVISED, MANUAL

    # 도구 실행
    tools_called: Annotated[list, add]
    tool_results: Annotated[list, add]

    # 결과
    result: dict
    confidence: float                 # 0.0 ~ 1.0
    needs_human_review: bool

    # 에러
    error: str | None

def build_orchestrator_graph():
    """10-노드 오케스트레이터 그래프 빌드"""

    graph = StateGraph(OrchestratorState)

    # 노드 등록
    graph.add_node("route", route_intent)
    graph.add_node("process_exec", execute_bpm_activity)
    graph.add_node("document_proc", process_document)
    graph.add_node("query_data", query_external_data)
    graph.add_node("agent_tools", execute_agent_tools)
    graph.add_node("rag_search", perform_rag_search)
    graph.add_node("nl2sql", call_oracle_service)
    graph.add_node("process_mining_analysis", execute_process_mining)  # NEW
    graph.add_node("hitl_check", check_human_review)
    graph.add_node("complete", finalize_result)

    # 엣지 (조건부 라우팅)
    graph.set_entry_point("route")

    graph.add_conditional_edges("route", decide_route, {
        "process": "process_exec",
        "document": "document_proc",
        "query": "query_data",
        "mining": "process_mining_analysis",  # NEW
    })

    graph.add_edge("process_exec", "agent_tools")
    graph.add_edge("document_proc", "rag_search")
    graph.add_edge("query_data", "nl2sql")
    graph.add_edge("process_mining_analysis", "hitl_check")  # NEW

    graph.add_edge("agent_tools", "hitl_check")
    graph.add_edge("rag_search", "hitl_check")
    graph.add_edge("nl2sql", "hitl_check")

    graph.add_conditional_edges("hitl_check", decide_hitl, {
        "approved": "complete",
        "needs_review": END,          # HITL interrupt - 사람 대기
    })

    graph.add_edge("complete", END)

    # HITL 중단점 설정
    checkpointer = MemorySaver()
    compiled = graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_check"],  # SUPERVISED 모드 시 중단
    )

    return compiled

# 노드 함수들
async def route_intent(state: OrchestratorState) -> dict:
    """의도 분류 (프로세스/문서/데이터 쿼리/프로세스 마이닝)"""
    activity = state["activity"]
    activity_type = activity.get("type", "humanTask")
    message = state["user_message"].lower()

    # 프로세스 마이닝 관련 키워드 감지
    mining_keywords = [
        "프로세스 마이닝", "process mining", "병목", "bottleneck",
        "적합성", "conformance", "프로세스 발견", "이벤트 로그",
    ]
    if any(kw in message for kw in mining_keywords):
        return {"intent": "mining"}
    elif activity_type in ("serviceTask", "scriptTask"):
        return {"intent": "process"}
    elif "document" in message:
        return {"intent": "document"}
    else:
        return {"intent": "query"}

async def execute_agent_tools(state: OrchestratorState) -> dict:
    """MCP 도구를 사용하여 에이전트 태스크 실행"""
    from app.orchestrator.tool_loader import SafeToolLoader

    # 우선순위 기반 도구 로드
    tools = await SafeToolLoader.create_tools_for_activity(
        activity=state["activity"],
        tenant_id=state["tenant_id"],
    )

    # LangGraph ReAct 에이전트 실행
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    react_agent = create_react_agent(llm, tools)

    result = await react_agent.ainvoke({
        "messages": [{"role": "user", "content": state["activity"]["instruction"]}]
    })

    return {
        "result": result,
        "tools_called": [t.name for t in tools],
        "confidence": calculate_confidence(result),
    }

async def check_human_review(state: OrchestratorState) -> dict:
    """HITL 필요 여부 결정"""
    agent_mode = state.get("agent_mode", "MANUAL")
    confidence = state.get("confidence", 0.0)

    if agent_mode == "AUTONOMOUS" and confidence >= 0.99:
        return {"needs_human_review": False}
    elif agent_mode == "SUPERVISED" or confidence < 0.80:
        return {"needs_human_review": True}
    else:
        return {"needs_human_review": False}

def decide_hitl(state: OrchestratorState) -> Literal["approved", "needs_review"]:
    """HITL 라우팅 결정"""
    if state.get("needs_human_review", False):
        return "needs_review"
    return "approved"
```

---

## 3. 도구(Tool) 우선순위 시스템

### 3.1 SafeToolLoader

K-AIR의 agent-utils에서 이식하는 핵심 컴포넌트. 에이전트가 사용할 도구를 보안 정책과 우선순위에 따라 동적으로 로드한다.

```python
# app/orchestrator/tool_loader.py
# K-AIR agent-utils/SafeToolLoader에서 이식

from typing import List
from langchain_core.tools import BaseTool

class ToolPriority:
    """도구 우선순위 (높을수록 먼저 사용)"""
    SKILLS = 100          # 도메인 특화 스킬 (비즈니스 프로세스 전용 도구)
    DMN_RULE = 80         # DMN 의사결정 테이블 평가
    MEM0_MEMORY = 60      # 에이전트 장기 기억 검색
    MCP_TOOLS = 40        # MCP 프로토콜 도구 (외부 서비스)
    GENERAL = 20          # 범용 도구 (파일 읽기, 웹 검색 등)

class SafeToolLoader:
    """보안 정책 기반 도구 동적 로더"""

    @staticmethod
    async def create_tools_for_activity(
        activity: dict,
        tenant_id: str,
    ) -> List[BaseTool]:
        """Activity에 필요한 도구를 우선순위 순으로 로드"""
        all_tools = []

        # 1. Skills (도메인 특화 도구) - 최고 우선순위
        skill_tools = await SafeToolLoader._load_skill_tools(
            activity, tenant_id
        )
        all_tools.extend([(ToolPriority.SKILLS, t) for t in skill_tools])

        # 2. DMN Rules (의사결정 테이블)
        dmn_tools = await SafeToolLoader._load_dmn_tools(
            activity, tenant_id
        )
        all_tools.extend([(ToolPriority.DMN_RULE, t) for t in dmn_tools])

        # 3. Mem0 Memory (에이전트 장기 기억)
        memory_tools = await SafeToolLoader._load_memory_tools(
            activity, tenant_id
        )
        all_tools.extend([(ToolPriority.MEM0_MEMORY, t) for t in memory_tools])

        # 4. MCP Tools (외부 서비스)
        mcp_tools = await SafeToolLoader._load_mcp_tools(
            activity, tenant_id
        )
        all_tools.extend([(ToolPriority.MCP_TOOLS, t) for t in mcp_tools])

        # 5. 보안 필터링
        filtered = SafeToolLoader._apply_security_policy(
            all_tools, tenant_id
        )

        # 6. 우선순위 정렬
        filtered.sort(key=lambda x: x[0], reverse=True)

        return [tool for _, tool in filtered]

    @staticmethod
    async def _load_mcp_tools(
        activity: dict,
        tenant_id: str,
    ) -> List[BaseTool]:
        """MCP 서버에서 도구를 동적으로 로드"""
        from app.core.mcp_client import MCPClient

        mcp_config = await MCPClient.get_tenant_config(tenant_id)
        tools = []

        for server in mcp_config.get("servers", []):
            server_tools = await MCPClient.list_tools(server["url"])
            for tool_def in server_tools:
                # 서버 출처 태깅
                tool = MCPClient.create_langchain_tool(
                    tool_def,
                    source_server=server["name"],
                )
                tools.append(tool)

        return tools

    @staticmethod
    def _apply_security_policy(
        tools: list,
        tenant_id: str,
    ) -> list:
        """보안 정책 적용 - 위험한 도구 필터링"""
        BLOCKED_TOOLS = [
            "shell_execute",     # 쉘 명령 실행 금지
            "file_delete",       # 파일 삭제 금지
            "db_drop",           # DB 드롭 금지
        ]

        return [
            (priority, tool) for priority, tool in tools
            if tool.name not in BLOCKED_TOOLS
        ]
```

### 3.2 도구 우선순위 결정 근거

```
[결정] Skills > DMN > Mem0 > MCP 순서로 도구를 우선 사용한다.

[근거]
1. Skills (최고 우선순위):
   - 도메인 전문가가 검증한 비즈니스 프로세스 특화 도구
   - 예: kpi_calculator(KPI 계산), optimization_schedule(최적화 스케줄)
   - 가장 정확하고 신뢰할 수 있는 결과

2. DMN Rules:
   - 의사결정 테이블로 형식화된 규칙
   - 예: 데이터 분류 기준, 최적화 비율 산정 기준
   - 규칙 기반이므로 결정적(deterministic) 결과

3. Mem0 Memory:
   - 에이전트의 과거 경험/학습 결과
   - 예: "지난번 유사 사건에서 이런 결정을 내렸다"
   - 유사도 검색 기반이므로 참고용

4. MCP Tools (최저 우선순위):
   - 외부 서비스 도구 (범용)
   - 도메인 특화 도구가 없을 때의 폴백
```

---

## 4. 3티어 지식 학습 루프

### 4.1 개요

K-AIR agent-feedback-main에서 이식하는 핵심 기능. 사용자 피드백을 분석하여 3가지 유형의 지식 저장소에 자동으로 학습한다.

```
사용자 피드백 (예: "데이터 분류가 잘못됐다. 이건 핵심 데이터가 아니라 일반 데이터이다")
     |
     v
[FeedbackProcessor - ReAct 5단계]
     |
     |-- STEP 1: 목표/상황 이해 (피드백 분석)
     |-- STEP 2: 기존 지식 분석 (Memory/DMN/Skill 조회)
     |-- STEP 3: 충돌 분석 (ConflictAnalyzer)
     |-- STEP 4: 라우팅 결정 (LearningRouter)
     |-- STEP 5: 머지 전략 수립 (MergeStrategy)
     |
     v
[LearningCommitter]
     |
     +---> Memory (Mem0/pgvector): 벡터 기억 추가/갱신
     +---> DMN Rule (proc_def XML): 의사결정 테이블 수정
     +---> Skill (HTTP API / MCP): 새로운 도구 등록
```

### 4.2 충돌 분석기(ConflictAnalyzer)

```python
# app/orchestrator/conflict_analyzer.py
# K-AIR agent-feedback-main에서 이식

from enum import Enum

class ConflictLevel(str, Enum):
    NO = "NO"             # 충돌 없음 - 새 지식 추가
    LOW = "LOW"           # 경미한 충돌 - 자동 머지 가능
    MEDIUM = "MEDIUM"     # 중간 충돌 - LLM 판단 필요
    HIGH = "HIGH"         # 심각한 충돌 - 사람 개입 필요

class Operation(str, Enum):
    CREATE = "CREATE"     # 새 지식 생성
    UPDATE = "UPDATE"     # 기존 지식 갱신
    DELETE = "DELETE"     # 기존 지식 삭제
    MERGE = "MERGE"       # 여러 지식 병합
    SKIP = "SKIP"         # 처리 불필요

class ConflictAnalyzer:
    """기존 지식과 새 피드백 간 충돌 분석"""

    async def analyze(
        self,
        feedback: dict,
        existing_knowledge: list,
    ) -> dict:
        """
        Returns:
            {
                "operation": "UPDATE",
                "conflict_level": "LOW",
                "affected_items": [...],
                "merge_strategy": "REPLACE",
                "confidence": 0.85,
            }
        """
        # 1. 유사도 기반 기존 지식 탐색
        similar = await self._find_similar_knowledge(
            feedback["content"],
            existing_knowledge,
            threshold=0.7,
        )

        if not similar:
            return {
                "operation": Operation.CREATE,
                "conflict_level": ConflictLevel.NO,
                "confidence": 0.95,
            }

        # 2. 의미적 충돌 분석 (LLM 사용)
        conflict = await self._analyze_semantic_conflict(
            feedback["content"],
            [s["content"] for s in similar],
        )

        return {
            "operation": conflict["operation"],
            "conflict_level": conflict["conflict_level"],
            "affected_items": similar,
            "merge_strategy": conflict["merge_strategy"],
            "confidence": conflict["confidence"],
        }
```

### 4.3 지식 커밋터(LearningCommitter)

| 커밋 대상 | 저장소 | 커밋 방식 | 예시 |
|----------|--------|----------|------|
| **Memory** | pgvector (Mem0 호환) | 벡터 임베딩 UPSERT | "핵심 데이터는 비즈니스 KPI에 직접 영향을 미치는 데이터이다" |
| **DMN Rule** | proc_def.definition (JSONB) | DMN XML 노드 수정 | Decision Table: input="중요도" -> output="데이터분류" |
| **Skill** | MCP 서버 등록 | HTTP API 또는 Skill Creator MCP | `verify_data_quality()` - 데이터 품질 검증 도구 등록 |

---

## 5. HITL (Human-in-the-Loop) 상세

### 5.1 신뢰도 3단계 모델

```
+----------------------------------------------------+
| 신뢰도 99%+                                         |
| 자동 실행 (사람 개입 불필요)                          |
| 예: 반복적 데이터 입력, 형식 검증                    |
+----------------------------------------------------+

+----------------------------------------------------+
| 신뢰도 80% ~ 99%                                    |
| 사람 확인 후 실행 (SUPERVISED)                        |
| 예: 데이터 분류, 최적화 비율 산정, 문서 요약         |
+----------------------------------------------------+

+----------------------------------------------------+
| 신뢰도 < 80%                                        |
| 사람이 직접 수정 -> 학습 데이터로 활용               |
| 예: 복잡한 전문적 판단, 새로운 유형의 프로젝트        |
+----------------------------------------------------+
```

### 5.2 HITL 구현

```python
# LangGraph interrupt를 사용한 HITL

async def run_with_hitl(workitem_id: str, graph, state):
    """HITL 중단점이 포함된 에이전트 실행"""

    # 1. 에이전트 실행 (hitl_check 노드 직전에 중단)
    config = {"configurable": {"thread_id": workitem_id}}
    result = await graph.ainvoke(state, config)

    # 2. 중단된 경우 (SUPERVISED 모드)
    if result.get("needs_human_review"):
        # Workitem 상태: SUBMITTED (사람 대기)
        await update_workitem_status(workitem_id, "SUBMITTED")
        await save_draft_result(workitem_id, result)

        # Canvas UI에서 사람이 승인/수정 후:
        # POST /process/approve-hitl (아래 함수 호출)
        return {"status": "AWAITING_HUMAN_REVIEW", "draft": result}

    return result

async def approve_hitl(workitem_id: str, approved: bool, modifications: dict = {}):
    """사람이 HITL 검토 완료"""
    config = {"configurable": {"thread_id": workitem_id}}

    if approved:
        # 원래 결과 그대로 진행
        result = await graph.ainvoke(None, config)  # 중단점에서 재개
    else:
        # 수정된 결과로 진행
        modified_state = {**modifications}
        result = await graph.ainvoke(modified_state, config)

    # Workitem 완료
    await submit_workitem(workitem_id, result)
    return result
```

---

## 6. ProcessMiningAgent

### 6.1 에이전트 개요

```
[결정] 프로세스 마이닝 분석을 전담하는 ProcessMiningAgent를 에이전트 로스터에 추가한다.
[근거] 프로세스 마이닝은 다음과 같은 고유한 특성을 가져 범용 에이전트로 처리하기 어렵다:
       1. Synapse pm4py API를 전용 도구로 사용한다
       2. 마이닝 결과 해석에 도메인 지식이 필요하다 (Fitness, Precision 등 지표)
       3. 적합성 검사 결과를 비전문가에게 자연어로 설명해야 한다
       4. 병목 분석 결과로 개선 방안을 제안해야 한다

[사실] ProcessMiningAgent는 LangGraph 오케스트레이터의 process_mining_analysis 노드에서 실행된다.
[사실] Synapse Process Mining API를 MCP 도구(또는 직접 HTTP 호출)로 사용한다.
```

### 6.2 에이전트 역할 정의

| 역할 | 설명 |
|------|------|
| **프로세스 발견 트리거** | 이벤트 로그에 대해 프로세스 모델 발견(Alpha/Heuristic/Inductive Miner)을 실행 |
| **적합성 결과 해석** | Token Replay / Alignment 결과를 자연어로 설명, 이탈 패턴 요약 |
| **병목 분석 보고** | 성능 분석 결과에서 주요 병목 구간을 식별하고 개선 방안 제안 |
| **프로세스 비교** | 설계 모델(BPM)과 발견 모델(Mining)을 비교하여 차이점 설명 |
| **대화형 마이닝** | 사용자 질문에 대해 마이닝 도구를 호출하여 답변 생성 |

### 6.3 사용 도구 (Tools)

| 도구 | 호출 대상 | 설명 |
|------|----------|------|
| `trigger_process_discovery` | Synapse API | 이벤트 로그에 대한 프로세스 발견 실행 |
| `run_conformance_check` | Synapse API | 참조 모델 대비 적합성 검사 실행 |
| `analyze_performance` | Synapse API | 성능 분석 및 병목 탐지 실행 |
| `get_process_variants` | Synapse API | 프로세스 변형(Variant) 목록 조회 |
| `compare_models` | Synapse API | 두 프로세스 모델 간 차이 비교 |
| `get_event_log_statistics` | Synapse API | 이벤트 로그 기본 통계 조회 |

#### 사용 가능 알고리즘 (Synapse Process Mining API, pm4py 기반)

| algorithm 값 | 알고리즘 | 설명 |
|-------------|---------|------|
| `alpha` | Alpha Miner | 이론적 기본 알고리즘 (정확한 로그에 적합) |
| `heuristic` | Heuristic Miner | 노이즈 내성 (실제 비즈니스 로그 권장, 기본값) |
| `inductive` | Inductive Miner | 건전한 모델 보장 (적합도 검사 필수 시) |

### 6.4 LangGraph 노드 구현

```python
# app/orchestrator/agents/process_mining_agent.py

from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
import httpx

SYNAPSE_BASE_URL = "http://synapse:8000/api/v1"

# --- Tool Definitions ---

@tool
async def trigger_process_discovery(
    case_id: str,
    log_id: str,
    algorithm: str = "heuristic",
) -> dict:
    """이벤트 로그에 대해 프로세스 모델 자동 발견을 실행한다.
    case_id: Axiom 케이스 UUID.
    log_id: 이벤트 로그 UUID.
    algorithm: alpha, heuristic, inductive 중 선택.
    heuristic가 노이즈에 강건하여 기본값으로 권장."""
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{SYNAPSE_BASE_URL}/process-mining/discover",
            json={
                "case_id": case_id,
                "log_id": log_id,
                "algorithm": algorithm,
            },
        )
        return response.json()

@tool
async def run_conformance_check(
    case_id: str,
    log_id: str,
    reference_model_id: str,
    method: str = "token_replay",
) -> dict:
    """이벤트 로그와 참조 프로세스 모델 간 적합성 검사를 실행한다.
    case_id: Axiom 케이스 UUID.
    log_id: 이벤트 로그 UUID.
    method: token_replay (빠름) 또는 alignment (정확함) 선택."""
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{SYNAPSE_BASE_URL}/process-mining/conformance",
            json={
                "case_id": case_id,
                "log_id": log_id,
                "reference_model_id": reference_model_id,
                "method": method,
            },
        )
        return response.json()

@tool
async def analyze_performance(
    case_id: str,
    log_id: str,
) -> dict:
    """이벤트 로그에 대해 성능 분석을 실행하여 병목 구간을 탐지한다.
    case_id: Axiom 케이스 UUID.
    log_id: 이벤트 로그 UUID.
    평균 대기 시간, 처리 시간, 빈도별 병목을 식별한다."""
    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(
            f"{SYNAPSE_BASE_URL}/process-mining/bottlenecks",
            json={"case_id": case_id, "log_id": log_id},
        )
        return response.json()

@tool
async def get_process_variants(
    case_id: str,
    log_id: str,
    top_k: int = 10,
) -> dict:
    """이벤트 로그의 프로세스 변형(Variant) 목록을 빈도순으로 조회한다.
    case_id: Axiom 케이스 UUID.
    log_id: 이벤트 로그 UUID.
    Variant는 동일한 활동 순서를 가진 케이스들의 그룹이다."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"{SYNAPSE_BASE_URL}/process-mining/variants",
            params={"case_id": case_id, "log_id": log_id, "top_k": top_k},
        )
        return response.json()

@tool
async def compare_models(
    model_a_id: str,
    model_b_id: str,
) -> dict:
    """두 프로세스 모델을 비교하여 차이점을 분석한다.
    설계 모델(BPM)과 발견 모델(Mining)의 비교에 사용한다."""
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{SYNAPSE_BASE_URL}/process-mining/compare",
            json={
                "model_a_id": model_a_id,
                "model_b_id": model_b_id,
            },
        )
        return response.json()


# --- Agent Node ---

PROCESS_MINING_SYSTEM_PROMPT = """당신은 프로세스 마이닝 전문 분석가 에이전트입니다.

역할:
- 이벤트 로그 데이터에서 실제 비즈니스 프로세스를 자동으로 발견합니다.
- 설계된 프로세스와 실제 실행 간의 차이를 적합성 검사로 분석합니다.
- 프로세스의 병목 구간을 식별하고 개선 방안을 제안합니다.

분석 결과 설명 규칙:
1. Fitness(적합도): 0.0~1.0 스케일. 0.8 이상이면 양호, 0.6 미만이면 심각한 이탈.
2. Precision(정밀도): 모델이 허용하는 행동 중 실제 관찰된 비율. 높을수록 모델이 정확.
3. 병목 보고 시: 대기 시간과 처리 시간을 구분하여 설명하고, 구체적 개선 방안을 제시.
4. 비전문가도 이해할 수 있는 자연어로 설명하되, 수치적 근거를 반드시 포함.

금지:
- 데이터 없이 추측하지 않는다.
- 마이닝 결과를 과대/과소 해석하지 않는다.
"""

MINING_TOOLS = [
    trigger_process_discovery,
    run_conformance_check,
    analyze_performance,
    get_process_variants,
    compare_models,
]


async def execute_process_mining(state: OrchestratorState) -> dict:
    """ProcessMiningAgent - 프로세스 마이닝 분석 실행 노드"""

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    mining_agent = create_react_agent(
        llm,
        MINING_TOOLS,
        state_modifier=PROCESS_MINING_SYSTEM_PROMPT,
    )

    result = await mining_agent.ainvoke({
        "messages": [
            {"role": "user", "content": state["user_message"]},
        ],
    })

    return {
        "result": result,
        "tools_called": [t.name for t in MINING_TOOLS if t.name in str(result)],
        "confidence": calculate_mining_confidence(result),
    }


def calculate_mining_confidence(result: dict) -> float:
    """마이닝 결과의 신뢰도 계산
    - 도구 호출 성공 + 수치 결과 포함: 0.9+
    - 도구 호출 성공 + 해석만: 0.7~0.9
    - 도구 호출 실패: 0.3 이하
    """
    ...
```

### 6.5 에이전트 사용 시나리오 예시

```
사용자: "구매 프로세스 이벤트 로그에서 병목 구간을 분석해줘"

ProcessMiningAgent 실행:
  1. [route] intent = "mining" (키워드: "병목", "이벤트 로그")
  2. [process_mining_analysis] 노드 진입
  3. ReAct Loop:
     - Thought: "병목 분석을 위해 먼저 이벤트 로그를 확인하고 성능 분석을 실행해야 한다"
     - Action: get_event_log_statistics(event_log_id="...")
     - Observation: {case_count: 1250, event_count: 45000, ...}
     - Thought: "충분한 데이터가 있다. 성능 분석을 실행한다"
     - Action: analyze_performance(event_log_id="...")
     - Observation: {bottlenecks: [{activity: "데이터 수치 검증", avg_waiting: 48.5h, ...}]}
     - Thought: "병목이 '데이터 수치 검증'에서 발생. 대기 시간이 48.5시간으로 매우 길다"
  4. 결과 생성:
     "분석 결과, '데이터 수치 검증' 활동에서 가장 큰 병목이 발생하고 있습니다.
      평균 대기 시간이 48.5시간으로, 전체 사이클 타임(168시간)의 29%를 차지합니다.
      실제 처리 시간은 2.3시간에 불과하므로, 작업 할당 및 대기열 관리 개선이 필요합니다.

      개선 제안:
      1. 데이터 수치 검증을 AI 에이전트(AUTONOMOUS 모드)로 자동화
      2. 검증 대기열에 우선순위 정책 적용
      3. 병렬 검증자 배정으로 처리량 확대"
  5. [hitl_check] confidence = 0.91 -> SUPERVISED 모드이면 사람 확인 대기
```

### 6.6 금지/필수 규칙

```
[금지] ProcessMiningAgent가 직접 DB를 조회하지 않는다.
       반드시 Synapse API(도구)를 통해서만 마이닝 기능에 접근한다.
[금지] 마이닝 결과 수치를 변조하거나 임의로 해석하지 않는다.
       도구가 반환한 수치를 그대로 인용한다.

[필수] 병목 분석 결과에는 반드시 구체적인 개선 방안을 1개 이상 포함한다.
[필수] 적합성 검사 결과는 이탈 빈도가 높은 상위 5개 패턴을 요약한다.
[필수] 모든 분석 결과에 사용된 도구명과 파라미터를 기록한다 (감사 추적).
```

<!-- affects: api, llm, frontend -->
<!-- requires-update: 05_llm/agent-architecture.md, 02_api/agent-api.md -->

---

## 7. 재평가 조건

| 조건 | 재평가 대상 |
|------|-----------|
| 에이전트 응답 시간 > 60초 빈발 | LLM 프로바이더 분산 또는 스트리밍 최적화 |
| HITL 거부율 > 30% | 에이전트 프롬프트 최적화, 학습 데이터 품질 검토 |
| 도구 충돌 (같은 이름의 도구가 여러 MCP 서버에 존재) | 네임스페이스 도입 |
| 지식 학습 충돌 HIGH 비율 > 10% | 지식 구조 재설계, 온톨로지 도입 |
| ProcessMiningAgent 도구 호출 실패율 > 15% | Synapse API 안정성 검토, 타임아웃 조정 |
| 마이닝 결과 해석 HITL 거부율 > 40% | 시스템 프롬프트 개선, Few-shot 예시 보강 |

---

## 근거

- K-AIR 역설계 보고서 섹션 8 (에이전트 시스템)
- process-gpt-crewai-action-main, process-gpt-a2a-orch-main 소스코드
- process-gpt-agent-feedback-main 소스코드 (FeedbackProcessor, ConflictAnalyzer)
- process-gpt-agent-utils-main 소스코드 (SafeToolLoader)
- ADR-002: LangGraph 선택 (CrewAI 대체)
