# Axiom Core - BPM 엔진 상세 설계

## 이 문서가 답하는 질문

- BPM 엔진은 프로세스를 어떻게 정의하고 실행하는가?
- Workitem의 라이프사이클은 어떻게 관리되는가?
- Saga 보상 트랜잭션은 언제, 어떻게 작동하는가?
- 에이전트 모드(AUTONOMOUS/SUPERVISED/MANUAL)는 어떻게 전환되는가?
- K-AIR의 process-gpt-completion-main에서 무엇을 이식하는가?

<!-- affects: api, frontend, llm -->
<!-- requires-update: 02_api/process-api.md, 03_backend/transaction-boundaries.md -->

---

## 1. BPM 엔진 개요

### 1.1 설계 철학

Axiom의 BPM 엔진은 **자연언어 중심 프로세스 자동화**를 목표로 한다:

```
[사실] BPMN 표준을 기반으로 하되, 프로세스 정의를 자연언어로 작성할 수 있다.
[사실] 각 Activity에 AI 에이전트를 할당하여 자동/반자동/수동 실행을 선택한다.
[사실] 프로세스 실패 시 Saga 패턴으로 보상 트랜잭션을 자동 실행한다.
```

### 1.2 K-AIR 이식 범위

```
process-gpt-completion-main/
  ├── process_definition.py  --> app/bpm/models.py (Pydantic 모델)
  ├── process_engine.py      --> app/bpm/engine.py (실행 엔진)
  ├── process_service.py     --> app/services/process_service.py (서비스 레이어)
  ├── compensation_handler.py --> app/bpm/saga.py (Saga 보상)
  └── features/
      └── process_chat/     --> app/orchestrator/ (LLM 통합)

process-gpt-bpmn-extractor-main/
  ├── entity_extractor.py   --> app/bpm/extractor.py (PDF -> 엔티티)
  ├── bpmn_generator.py     --> app/bpm/extractor.py (엔티티 -> BPMN)
  └── dmn_generator.py      --> app/bpm/extractor.py (엔티티 -> DMN)
```

---

## 2. 프로세스 정의 모델

### 2.1 프로세스 계층 구조

```
MegaProcess (최상위: "엔터프라이즈 운영 최적화 전체")
  |
  +-- MajorProcess ("데이터 검증 단계")
  |     |
  |     +-- BaseProcess ("데이터 등록 접수") = BPMN 프로세스
  |     |     |
  |     |     +-- Activity: "데이터 등록서 접수" (humanTask)
  |     |     +-- Activity: "데이터 수치 검증" (serviceTask, AUTONOMOUS)
  |     |     +-- Activity: "데이터 분류" (serviceTask, SUPERVISED)
  |     |     +-- Gateway: "이슈 있는가?" (exclusiveGateway)
  |     |     +-- Activity: "이슈 처리" (humanTask)
  |     |
  |     +-- BaseProcess ("이해관계자 목록 확정")
  |
  +-- MajorProcess ("최적화 시나리오 수립 단계")
        |
        +-- BaseProcess ("현금흐름 분석")
        +-- BaseProcess ("최적화 비율 산정")
```

### 2.2 ProcessDefinition 데이터 모델

```python
# app/bpm/models.py
# K-AIR process_definition.py에서 이식

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

class AgentMode(str, Enum):
    AUTONOMOUS = "AUTONOMOUS"    # AI 자동 실행 (사람 개입 없음)
    SUPERVISED = "SUPERVISED"    # AI 실행 + 사람 확인 후 승인
    MANUAL = "MANUAL"            # 사람이 직접 처리

class ActivityType(str, Enum):
    HUMAN_TASK = "humanTask"         # 사람이 처리
    SERVICE_TASK = "serviceTask"     # 시스템/AI가 처리
    SCRIPT_TASK = "scriptTask"       # Python 코드 실행
    SUB_PROCESS = "subProcess"       # 하위 프로세스 호출

class GatewayType(str, Enum):
    EXCLUSIVE = "exclusiveGateway"   # 조건 분기 (하나만 선택)
    PARALLEL = "parallelGateway"     # 병렬 분기 (모두 실행)
    INCLUSIVE = "inclusiveGateway"    # 조건 분기 (여러 개 선택 가능)

class ProcessData(BaseModel):
    """프로세스에서 사용되는 데이터 소스"""
    name: str
    type: str                        # "sql", "db", "api", "file"
    source: str                      # 실제 데이터 소스 참조
    fields: List[str] = []

class ProcessRole(BaseModel):
    """프로세스에 참여하는 역할"""
    name: str
    id: str
    assignment_rule: Optional[str] = None  # 자동 할당 규칙

class ProcessActivity(BaseModel):
    """BPMN 태스크 (Activity)"""
    name: str
    id: str
    type: ActivityType
    instruction: str = ""            # AI 에이전트 지시사항
    input_data: List[ProcessData] = []
    output_data: List[ProcessData] = []
    python_code: Optional[str] = None  # scriptTask 전용
    agent: Optional[str] = None      # 할당 에이전트 ID
    agent_mode: AgentMode = AgentMode.MANUAL
    orchestration: Optional[dict] = None  # 오케스트레이션 설정
    compensation: Optional[str] = None    # 보상 Activity ID

class Gateway(BaseModel):
    """BPMN 게이트웨이"""
    id: str
    name: str
    type: GatewayType
    conditions: dict = {}            # 분기 조건 (transition_id -> condition)

class Transition(BaseModel):
    """BPMN 시퀀스 플로우"""
    id: str
    source: str                      # Activity/Gateway ID
    target: str                      # Activity/Gateway ID
    condition: Optional[str] = None  # 조건식

class ProcessDefinition(BaseModel):
    """프로세스 정의 (BPMN 기반)"""
    process_definition_id: str
    process_definition_name: str
    description: str = ""
    data: List[ProcessData] = []
    roles: List[ProcessRole] = []
    activities: List[ProcessActivity] = []
    gateways: List[Gateway] = []
    transitions: List[Transition] = []
    version: int = 1
    tenant_id: str = ""
```

### 2.3 DB 스키마 매핑

```sql
-- proc_def: 프로세스 정의 저장
CREATE TABLE proc_def (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    bpmn TEXT,                       -- BPMN XML (프론트엔드 렌더링용)
    definition JSONB NOT NULL,       -- ProcessDefinition JSON (AI 접근용)
    type VARCHAR(50) DEFAULT 'base', -- mega, major, base, sub
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- proc_def_version: 프로세스 정의 버전 관리
CREATE TABLE proc_def_version (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proc_def_id UUID NOT NULL REFERENCES proc_def(id),
    version INT NOT NULL,
    snapshot JSONB NOT NULL,         -- 해당 버전의 전체 스냅샷
    diff JSONB,                      -- 이전 버전과의 차이
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 3. 프로세스 실행 엔진

### 3.1 실행 흐름

```
[Initiate]
     |
     v
+----------------+    +-----------------+    +------------------+
| Load Process   |--->| Create Process  |--->| Create First     |
| Definition     |    | Instance        |    | Workitem (TODO)  |
+----------------+    +-----------------+    +------------------+
                                                     |
                                                     v
                                           +------------------+
                                    +----->| Evaluate         |
                                    |      | Agent Mode       |
                                    |      +--------+---------+
                                    |               |
                                    |     +---------+---------+
                                    |     |         |         |
                                    |     v         v         v
                                    | +------+  +------+  +------+
                                    | |AUTO  |  |SUPER |  |MANUAL|
                                    | |Agent |  |Agent |  |Human |
                                    | |Exec  |  |+HITL |  |Exec  |
                                    | +--+---+  +--+---+  +--+---+
                                    |    |         |         |
                                    |    v         v         v
                                    | +---------------------------+
                                    | | Submit Workitem           |
                                    | | (status: SUBMITTED->DONE)|
                                    | +-------------+-------------+
                                    |               |
                                    |               v
                                    |      +------------------+
                                    |      | Evaluate Gateway |
                                    |      | (branch logic)   |
                                    |      +--------+---------+
                                    |               |
                                    |     +---------+---------+
                                    |     |                   |
                                    |     v                   v
                                    | +----------+    +-----------+
                                    | |Next      |    |Process    |
                                    | |Activity  |    |COMPLETED  |
                                    | +----+-----+    +-----------+
                                    |      |
                                    +------+
```

### 3.2 BPM 엔진 코어 코드

```python
# app/bpm/engine.py
# K-AIR process_engine.py에서 이식

from typing import Optional
from app.bpm.models import (
    ProcessDefinition, ProcessActivity, AgentMode,
    GatewayType, ActivityType
)
from app.core.database import get_session

class BPMEngine:
    """BPM 프로세스 실행 엔진"""

    async def initiate(
        self,
        proc_def_id: str,
        initiator_id: str,
        input_data: dict = {},
    ) -> str:
        """프로세스 인스턴스 시작"""
        # 1. 프로세스 정의 로드
        proc_def = await self._load_definition(proc_def_id)

        # 2. 프로세스 인스턴스 생성
        proc_inst = await self._create_instance(proc_def, initiator_id)

        # 3. 시작 Activity 탐색 (incoming transition이 없는 Activity)
        start_activity = self._find_start_activity(proc_def)

        # 4. 첫 Workitem 생성
        await self._create_workitem(proc_inst.id, start_activity)

        # 5. 이벤트 발행
        await self._publish_event("PROCESS_STARTED", {
            "proc_inst_id": proc_inst.id,
            "proc_def_id": proc_def_id,
        })

        return proc_inst.id

    async def submit_workitem(
        self,
        workitem_id: str,
        result_data: dict = {},
        submitter_id: str = "",
    ) -> dict:
        """워크아이템 제출 (완료 처리)"""
        # 1. Workitem 로드 및 상태 검증
        workitem = await self._load_workitem(workitem_id)
        assert workitem.status in ("TODO", "IN_PROGRESS"), \
            f"Cannot submit workitem in {workitem.status} status"

        # 2. 결과 데이터 저장
        await self._save_workitem_result(workitem_id, result_data)

        # 3. Workitem 상태 변경: SUBMITTED -> DONE
        await self._update_workitem_status(workitem_id, "DONE")

        # 4. 다음 노드 결정 (Gateway 평가)
        next_nodes = await self._evaluate_next(workitem, result_data)

        # 5. 다음 Activity의 Workitem 생성 또는 프로세스 완료
        for node in next_nodes:
            if isinstance(node, ProcessActivity):
                await self._create_workitem(workitem.proc_inst_id, node)
            # Gateway인 경우 재귀적으로 다음 노드 평가

        if not next_nodes:
            await self._complete_process(workitem.proc_inst_id)

        return {"next_nodes": [n.id for n in next_nodes]}

    async def _evaluate_next(
        self,
        workitem,
        result_data: dict
    ) -> list:
        """게이트웨이 평가 - 다음 실행 노드 결정"""
        proc_def = await self._load_definition(workitem.proc_def_id)
        current_id = workitem.activity_id

        # 현재 Activity에서 나가는 Transition 탐색
        outgoing = [t for t in proc_def.transitions if t.source == current_id]

        next_nodes = []
        for transition in outgoing:
            target = self._find_node(proc_def, transition.target)

            if isinstance(target, Gateway):
                # 게이트웨이 유형별 처리
                if target.type == GatewayType.EXCLUSIVE:
                    # 조건을 만족하는 첫 번째 분기만 선택
                    selected = self._evaluate_exclusive(target, result_data, proc_def)
                    if selected:
                        next_nodes.append(selected)

                elif target.type == GatewayType.PARALLEL:
                    # 모든 분기를 병렬 실행
                    parallel_targets = self._get_gateway_targets(target, proc_def)
                    next_nodes.extend(parallel_targets)
            else:
                next_nodes.append(target)

        return next_nodes
```

### 3.4 ParallelGateway Join (합류)

병렬 분기(Fork)로 생성된 워크아이템들이 모두 완료되면, Join 게이트웨이에서 합류하여 다음 Activity를 시작한다.

```python
# app/bpm/engine.py (계속)

async def _on_workitem_completed(
    self, workitem: Workitem, proc_inst_id: str
) -> list:
    """워크아이템 완료 시 다음 노드 결정 (Join 포함)"""
    proc_def = await self._load_definition(workitem.proc_def_id)
    current_id = workitem.activity_id

    outgoing = [t for t in proc_def.transitions if t.source == current_id]

    next_nodes = []
    for transition in outgoing:
        target = self._find_node(proc_def, transition.target)

        if isinstance(target, Gateway) and target.type == GatewayType.PARALLEL:
            # Join 게이트웨이: 모든 incoming 분기 완료 확인
            if await self._check_join_completion(target, proc_inst_id, proc_def):
                # 모든 분기 완료 → Join 통과, 다음 노드로 진행
                join_outgoing = self._get_gateway_targets(target, proc_def)
                next_nodes.extend(join_outgoing)
            # else: 아직 완료되지 않은 분기 있음 → 대기
        else:
            next_nodes.append(target)

    return next_nodes

async def _check_join_completion(
    self, gateway: Gateway, proc_inst_id: str, proc_def
) -> bool:
    """병렬 분기 합류 조건 확인 (AND-join)"""
    # 이 게이트웨이로 들어오는 모든 incoming transition의 소스 확인
    incoming = [t for t in proc_def.transitions if t.target == gateway.id]

    for transition in incoming:
        source_workitem = await self._get_latest_workitem(
            proc_inst_id, transition.source
        )
        if not source_workitem or source_workitem.status != "DONE":
            return False  # 아직 완료되지 않은 분기 있음

    return True  # 모든 분기 완료 → 다음 Activity 진행
```

```
[결정] ParallelGateway는 Fork(분기)와 Join(합류) 두 가지 역할을 모두 수행한다.
  - Fork: outgoing transition이 2개 이상 → 모든 분기를 병렬 실행 (§3.3)
  - Join: incoming transition이 2개 이상 → 모든 분기 완료 후 진행 (AND-join)
[근거] BPMN 2.0 표준에서 ParallelGateway는 Fork/Join 역할을 겸한다.
       비즈니스 프로세스에서 병렬 작업은 모두 완료되어야 다음 단계로 진행할 수 있다.
[사실] 개별 분기의 완료 순서는 보장하지 않는다. 마지막 분기 완료 시 _on_workitem_completed에서
       Join 통과를 감지하고 다음 노드를 생성한다.
[사실] Join 완료 시점의 동시성 제어는 낙관적 잠금(version 컬럼)으로 보장한다.
       두 분기가 동시에 완료되어도 하나만 Join 통과에 성공한다.
```

---

## 4. Workitem 라이프사이클

### 4.1 상태 전이

```
                  +------+
           +----->| TODO |<----- (생성 시 초기 상태)
           |      +--+---+
           |         |
           |         | (담당자가 작업 시작 또는 에이전트 시작)
           |         v
           |   +-----+-------+
           |   | IN_PROGRESS  |
           |   +-----+-------+
           |         |
           |         | (결과 제출)
           |         v
           |   +-----+-------+
           |   | SUBMITTED    |<---- (SUPERVISED 모드: HITL 대기)
           |   +-----+-------+
           |         |
           |         | (승인 완료 또는 자동 승인)
           |         v
      (재작업) +-----+-------+
           |   | DONE        |
           |   +-------------+
           |
           |   +-------------+
           +---| REWORK      |<---- (관리자가 재작업 지시)
               +-------------+
```

### 4.2 에이전트 모드별 실행 차이

| 모드 | 실행 주체 | 승인 | 재작업 가능 | 코드 경로 |
|------|----------|------|-----------|----------|
| **AUTONOMOUS** | LangGraph 에이전트가 자동 실행 | 불필요 (직접 DONE) | 가능 | `orchestrator/langgraph_flow.py` |
| **SUPERVISED** | LangGraph 에이전트 실행 후 SUBMITTED 상태로 대기 | 사람이 확인/승인 필요 | 가능 | `orchestrator/langgraph_flow.py` + HITL |
| **MANUAL** | 사람이 Canvas UI에서 직접 처리 | 불필요 (사람이 직접 처리) | 가능 | Canvas -> API -> submit |

### 4.3 에이전트 실행 상세

```python
# app/orchestrator/langgraph_flow.py
# Workitem을 에이전트가 실행하는 경우

async def execute_workitem_with_agent(
    workitem_id: str,
    activity: ProcessActivity,
) -> dict:
    """에이전트가 Workitem을 실행"""

    # 1. Workitem 상태: TODO -> IN_PROGRESS
    await update_workitem_status(workitem_id, "IN_PROGRESS")

    # 2. LangGraph 에이전트 구성
    agent = build_agent_for_activity(activity)

    # 3. 입력 데이터 준비
    input_data = await prepare_input_data(activity.input_data)

    # 4. 에이전트 실행
    try:
        result = await agent.ainvoke({
            "instruction": activity.instruction,
            "input_data": input_data,
            "tools": await load_tools_for_activity(activity),
        })
    except AgentExecutionError as e:
        # 실패 시 Saga 보상 트리거
        await trigger_compensation(workitem_id, str(e))
        raise

    # 5. 모드에 따른 후처리
    if activity.agent_mode == AgentMode.AUTONOMOUS:
        # 자동 완료
        await submit_workitem(workitem_id, result)
    elif activity.agent_mode == AgentMode.SUPERVISED:
        # SUBMITTED 상태로 전환, HITL 대기
        await update_workitem_status(workitem_id, "SUBMITTED")
        await save_workitem_draft(workitem_id, result)

    return result
```

---

## 5. Saga 보상 트랜잭션

### 5.1 Saga 패턴 개요

Axiom의 BPM 엔진은 분산 환경에서의 트랜잭션 일관성을 **Saga 패턴**으로 보장한다.

```
[결정] 2PC(Two-Phase Commit) 대신 Saga 보상 패턴을 사용한다.
[근거] 마이크로서비스 간 긴 트랜잭션은 2PC로 처리하기 어렵고,
       MCP 도구(외부 서비스)는 XA 트랜잭션을 지원하지 않는다.
       Saga의 "보상 트랜잭션"이 더 실용적이다.
```

### 5.2 보상 트랜잭션 흐름

```
정상 실행:
  Activity A (성공) --> Activity B (성공) --> Activity C (성공) = 프로세스 완료

보상 실행 (Activity C 실패):
  Activity A (성공) --> Activity B (성공) --> Activity C (실패!)
                                                    |
                                                    v
                                         Saga Manager 개시
                                                    |
                              +---------------------+---------------------+
                              |                                           |
                              v                                           v
                    Compensate B                              Compensate A
                    (B의 결과 롤백)                            (A의 결과 롤백)
                              |                                           |
                              v                                           v
                    MCP 도구로 자동 롤백                        MCP 도구로 자동 롤백
```

### 5.3 Saga Manager 구현

```python
# app/bpm/saga.py
# K-AIR compensation_handler.py에서 이식

from typing import List, Optional
from dataclasses import dataclass

@dataclass
class CompensationStep:
    """보상 단계 정의"""
    activity_id: str
    activity_name: str
    compensation_action: str          # MCP 도구 호출 명세
    compensation_data: dict           # 보상에 필요한 데이터
    status: str = "PENDING"           # PENDING, EXECUTED, FAILED, SKIPPED

class SagaManager:
    """Saga 보상 트랜잭션 관리자"""

    async def trigger_compensation(
        self,
        proc_inst_id: str,
        failed_activity_id: str,
        failure_reason: str,
    ) -> dict:
        """보상 트랜잭션 시작"""

        # 1. 완료된 Activity 목록 역순 조회
        completed = await self._get_completed_activities(
            proc_inst_id,
            up_to=failed_activity_id
        )

        # 2. 보상 단계 생성 (역순)
        compensation_steps = []
        for activity in reversed(completed):
            if activity.compensation:
                step = CompensationStep(
                    activity_id=activity.id,
                    activity_name=activity.name,
                    compensation_action=activity.compensation,
                    compensation_data=await self._get_activity_result(
                        proc_inst_id, activity.id
                    ),
                )
                compensation_steps.append(step)

        # 3. 보상 실행
        results = []
        for step in compensation_steps:
            try:
                result = await self._execute_compensation(step)
                step.status = "EXECUTED"
                results.append({"step": step.activity_name, "status": "EXECUTED"})
            except Exception as e:
                step.status = "FAILED"
                results.append({
                    "step": step.activity_name,
                    "status": "FAILED",
                    "error": str(e)
                })
                # 보상 실패 시 수동 개입 필요 -> 알림 발송
                await self._notify_compensation_failure(proc_inst_id, step, str(e))

        # 4. 프로세스 상태 변경
        await self._update_process_status(proc_inst_id, "TERMINATED")

        # 5. 이벤트 발행
        await self._publish_event("SAGA_COMPENSATION_COMPLETED", {
            "proc_inst_id": proc_inst_id,
            "failed_activity": failed_activity_id,
            "failure_reason": failure_reason,
            "compensation_results": results,
        })

        return {"compensation_steps": results}

    async def _execute_compensation(self, step: CompensationStep) -> dict:
        """개별 보상 단계 실행 (MCP 도구 호출)"""
        # MCP 도구를 사용하여 보상 실행
        # 예: "cancel_payment" MCP 도구로 이미 실행된 결제 취소
        from app.orchestrator.mcp_client import execute_mcp_tool

        result = await execute_mcp_tool(
            tool_name=step.compensation_action,
            parameters=step.compensation_data,
            timeout=30,
        )
        return result
```

### 5.4 Axiom 도메인 보상 예시

| Activity | 정상 동작 | 보상 동작 |
|---------|----------|----------|
| 데이터 등록 | DB에 데이터 레코드 INSERT | 데이터 레코드 DELETE + 감사 로그 |
| 최적화 비율 계산 | 최적화 스케줄 생성 | 최적화 스케줄 취소 |
| 문서 생성 | 보고서 PDF 생성/저장 | PDF 삭제 + 생성 이벤트 취소 |
| 알림 발송 | 이해관계자에게 이메일 발송 | 정정 알림 발송 |

### 5.5 병렬 분기(Parallel Gateway) 보상

#### 보상 전략

```
[결정] 병렬 분기 보상 시, 완료된 분기는 역순 보상(COMPENSATED)하고
       진행 중인 분기는 취소(CANCELLED) 처리한다.
[근거] 진행 중인(TODO/IN_PROGRESS) 워크아이템에 대해 보상 트랜잭션을 실행하면
       아직 커밋되지 않은 작업을 되돌리려는 모순이 발생한다.
       완료되지 않은 작업은 취소하고, 완료된 작업만 보상하는 것이 안전하다.
[결정] 병렬 분기의 모든 브랜치가 보상/취소 완료된 후에만 분기 이전 Activity 보상을 진행한다.
[근거] 분기 내 보상이 불완전한 상태에서 이전 단계를 보상하면 데이터 정합성이 깨진다.
```

#### 보상 흐름 예시

```
ParallelGateway Fork
├── Branch A: [데이터 수치 검증]    → DONE          ← 보상 실행 (역순)
├── Branch B: [문서 생성]           → DONE          ← 보상 실행 (역순)
└── Branch C: [데이터 분류]         → IN_PROGRESS   ← 취소 처리 (CANCELLED)

보상 순서:
  Phase 1 - 진행 중 분기 취소:
    Branch C: IN_PROGRESS → CANCELLED (에이전트 중단 + 워크아이템 상태 변경)

  Phase 2 - 완료된 분기 보상 (분기 간 순서 없음):
    Branch B: DONE → COMPENSATED (PDF 삭제 + 생성 이벤트 취소)
    Branch A: DONE → COMPENSATED (검증 결과 삭제)

  Phase 3 - 분기 이전 Activity 보상 (기존 §5.3 SagaManager 로직):
    이전 Activity 역순 보상 계속...
```

#### CompensationStep 확장

```python
@dataclass
class CompensationStep:
    """보상 단계 정의 (병렬 분기 지원 확장)"""
    activity_id: str
    activity_name: str
    compensation_action: str          # MCP 도구 호출 명세
    compensation_data: dict           # 보상에 필요한 데이터
    status: str = "PENDING"           # PENDING, EXECUTED, FAILED, SKIPPED, CANCELLED
    parallel_group_id: Optional[str] = None   # 병렬 분기 그룹 ID (Fork Gateway ID)
    branch_index: Optional[int] = None         # 분기 내 순서 (0-based)
```

#### SagaManager 병렬 보상 확장

```python
# app/bpm/saga.py (SagaManager 확장)

async def trigger_compensation(
    self,
    proc_inst_id: str,
    failed_activity_id: str,
    failure_reason: str,
) -> dict:
    """보상 트랜잭션 시작 (병렬 분기 인식)"""

    # 1. 완료된 Activity 목록 역순 조회
    completed = await self._get_completed_activities(
        proc_inst_id, up_to=failed_activity_id
    )

    # 2. 병렬 분기 그룹 식별
    parallel_groups = self._group_by_parallel(completed)

    results = []
    for group_id, branches in parallel_groups.items():
        if group_id is None:
            # 순차 Activity → 기존 로직 (§5.3)
            for activity in reversed(branches):
                result = await self._compensate_activity(activity, proc_inst_id)
                results.append(result)
        else:
            # 병렬 분기 → 병렬 보상 로직
            parallel_results = await self._handle_parallel_compensation(
                proc_inst_id, group_id
            )
            results.extend(parallel_results)

    return {"compensation_steps": results}

async def _handle_parallel_compensation(
    self, proc_inst_id: str, gateway_id: str
) -> list:
    """병렬 분기 보상 처리"""
    branches = await self._get_parallel_branches(proc_inst_id, gateway_id)
    results = []

    # Phase 1: 진행 중인 분기 취소
    for branch in branches:
        workitem = branch.current_workitem
        if workitem.status in ("TODO", "IN_PROGRESS"):
            await self._cancel_workitem(workitem)
            results.append({
                "step": branch.activity_name,
                "status": "CANCELLED",
                "action": "진행 중인 에이전트 작업 취소",
            })

    # Phase 2: 완료된 분기 보상 (분기 간 순서 없음)
    for branch in branches:
        workitem = branch.current_workitem
        if workitem.status in ("DONE", "SUBMITTED"):
            if branch.compensation:
                result = await self._execute_compensation(branch.compensation)
                results.append({
                    "step": branch.activity_name,
                    "status": "COMPENSATED" if result else "FAILED",
                    "action": branch.compensation.tool,
                })

    return results

async def _cancel_workitem(self, workitem) -> None:
    """진행 중인 워크아이템 취소"""
    async with get_session() as session:
        workitem.status = "CANCELLED"
        workitem.cancelled_at = datetime.utcnow()
        workitem.cancel_reason = "Saga compensation - parallel branch cancellation"
        await session.commit()

    # 에이전트가 실행 중이면 중단 시그널 전송
    if workitem.agent_task_id:
        await self._signal_agent_cancellation(workitem.agent_task_id)
```

#### Workitem 상태 전이 확장

§4.1 상태 전이도에 CANCELLED 상태가 추가된다:

```
  TODO / IN_PROGRESS → CANCELLED (병렬 분기 보상 시)
```

| 기존 상태 | CANCELLED 전이 조건 |
|----------|-------------------|
| TODO | 병렬 분기 Saga 보상 시, 아직 시작되지 않은 워크아이템 |
| IN_PROGRESS | 병렬 분기 Saga 보상 시, 에이전트가 실행 중인 워크아이템 |

> CANCELLED는 DONE/SUBMITTED 상태에서는 발생하지 않는다. 완료된 워크아이템은 COMPENSATED로 처리된다.

> **관련 문서**: 병렬 분기 보상 불변성 규칙은 [ADR-005](../99_decisions/ADR-005-saga-compensation.md) §7에 정의되어 있다. 크로스서비스 Saga(문서 추출 + 온톨로지 갱신)는 [transaction-boundaries.md](../03_backend/transaction-boundaries.md) §2.3을 참조한다.

---

## 6. BPMN 추출 파이프라인

### 6.1 PDF -> BPMN 자동 추출

```
업무 매뉴얼 PDF
     |
     v
[1. 텍스트 추출 (pdfplumber)]
     |
     v
[2. 청킹 (800 토큰)]
     |
     v
[3. EntityExtractor (GPT-4o)]
     |-- 프로세스명
     |-- 활동(Activity) 목록
     |-- 역할(Role) 목록
     |-- 데이터 항목
     |-- 게이트웨이(분기 조건)
     v
[4. BPMNGenerator (GPT-4o)]
     |-- 엔티티 -> BPMN XML 변환
     |-- 시퀀스 플로우 연결
     |-- 게이트웨이 배치
     v
[5. DMNGenerator (GPT-4o)]
     |-- 의사결정 테이블 추출
     |-- DMN XML 생성
     v
[6. HITL 검토]
     |-- 신뢰도 < 80%: 사람 검토 필요
     |-- 신뢰도 >= 80%: 자동 승인
     v
[ProcessDefinition JSON + BPMN XML]
```

### 6.2 비즈니스 프로세스 적용 예시

```
입력: "공급망 데이터 검증 절차 매뉴얼.pdf"

추출 결과:
  ProcessDefinition:
    name: "공급망 데이터 검증 절차"
    activities:
      - name: "데이터 등록서 접수"
        type: humanTask
        instruction: "이해관계자가 제출한 데이터 등록서를 접수하고 형식 검증"
      - name: "데이터 수치 검증"
        type: serviceTask
        agent_mode: SUPERVISED
        instruction: "제출된 수치 데이터와 시스템 기록을 대조 검증"
      - name: "데이터 분류"
        type: serviceTask
        agent_mode: AUTONOMOUS
        instruction: "데이터를 일반/핵심/우선/보조로 분류"
    gateways:
      - name: "이슈 유무"
        type: exclusiveGateway
        conditions:
          "이슈 있음": "has_issue == true"
          "이슈 없음": "has_issue == false"
```

---

## 7. 프로세스 마이닝 연동

### 7.1 설계 철학

```
[결정] BPM 엔진과 프로세스 마이닝은 양방향으로 연동한다.
[근거] 프로세스 설계(Design)와 프로세스 발견(Discovery)은 상호 보완적이다.
       - BPM이 실행한 프로세스 로그를 마이닝 입력으로 활용 (Design -> Discovery)
       - 마이닝이 발견한 프로세스 모델을 BPM에 임포트 (Discovery -> Design)
       이 양방향 루프가 지속적 프로세스 개선(CPI)을 가능하게 한다.

[사실] 프로세스 마이닝 엔진은 Synapse 모듈(pm4py 기반)에서 실행된다.
[사실] Core는 이벤트 로그 수집/전달과 결과 라우팅을 담당한다.
```

### 7.2 양방향 연동 흐름

```
+----------------------------------------------------------+
|                  Design -> Discovery                      |
|                                                          |
|  [BPM Engine]                                            |
|       |                                                  |
|       | BPM 실행 로그 축적                                |
|       | (ProcessInstance, Workitem 이력)                  |
|       v                                                  |
|  [EventLogExporter]                                      |
|       |                                                  |
|       | XES 형식으로 변환                                 |
|       | case_id = proc_inst_id                           |
|       | activity = activity_name                         |
|       | timestamp = workitem.completed_at                |
|       v                                                  |
|  [Core EventLogWorker] --stream--> [Synapse pm4py]       |
|                                         |                |
+----------------------------------------------------------+
                                          |
                                          v
+----------------------------------------------------------+
|                  Discovery -> Design                      |
|                                                          |
|  [Synapse pm4py]                                         |
|       |                                                  |
|       | 프로세스 모델 발견 (BPMN XML 출력)                |
|       | 적합성 검사 결과                                  |
|       | 병목 구간 분석                                    |
|       v                                                  |
|  [PROCESS_DISCOVERED 이벤트]                              |
|       |                                                  |
|       v                                                  |
|  [BPM Engine - 모델 임포트]                              |
|       |                                                  |
|       | pm4py BPMN -> ProcessDefinition 변환             |
|       | 기존 BPM 모델과 비교 (Diff 생성)                  |
|       | HITL: 분석가가 발견 모델 승인/수정 후 적용        |
|       v                                                  |
|  [proc_def 테이블에 저장]                                |
|       | type = "discovered" (마이닝 발견 모델)            |
|       | source_event_log_id = uuid (출처 추적)           |
|                                                          |
+----------------------------------------------------------+
```

### 7.3 BPM 실행 로그 -> 이벤트 로그 변환

```python
# app/bpm/event_log_exporter.py

from typing import List
from datetime import datetime

class EventLogExporter:
    """BPM 실행 이력을 프로세스 마이닝용 이벤트 로그로 변환"""

    async def export_to_xes(
        self,
        proc_def_id: str,
        date_from: datetime,
        date_to: datetime,
        tenant_id: str,
    ) -> dict:
        """
        BPM 실행 이력을 XES 호환 이벤트 로그로 변환

        매핑 규칙:
          - case_id    <- proc_inst.id (프로세스 인스턴스 ID)
          - activity   <- workitem.activity_name (활동명)
          - timestamp  <- workitem.completed_at (완료 시각)
          - resource   <- workitem.assignee (담당자/에이전트)
          - lifecycle  <- workitem.status 매핑 (start/complete)
        """
        # 1. 해당 기간의 완료된 Workitem 조회
        workitems = await self._query_completed_workitems(
            proc_def_id, date_from, date_to, tenant_id
        )

        # 2. XES 이벤트 로그 구조로 변환
        event_log = {
            "name": f"BPM Export - {proc_def_id}",
            "source": "axiom_bpm_engine",
            "export_date": datetime.utcnow().isoformat(),
            "traces": self._group_by_case(workitems),
        }

        return event_log

    def _group_by_case(self, workitems: List[dict]) -> List[dict]:
        """Workitem 목록을 Case(프로세스 인스턴스)별로 그룹화"""
        cases = {}
        for wi in workitems:
            case_id = str(wi["proc_inst_id"])
            if case_id not in cases:
                cases[case_id] = {
                    "case_id": case_id,
                    "events": [],
                }
            cases[case_id]["events"].append({
                "activity": wi["activity_name"],
                "timestamp": wi["completed_at"].isoformat(),
                "resource": wi.get("assignee", "system"),
                "lifecycle": "complete",
                "agent_mode": wi.get("agent_mode", "MANUAL"),
            })

        # 시간순 정렬
        for case in cases.values():
            case["events"].sort(key=lambda e: e["timestamp"])

        return list(cases.values())
```

### 7.4 발견된 프로세스 모델 임포트

```python
# app/bpm/mining_importer.py

class MiningModelImporter:
    """Synapse에서 발견된 프로세스 모델을 BPM에 임포트"""

    async def import_discovered_model(
        self,
        event_log_id: str,
        bpmn_xml: str,
        mining_metadata: dict,
        tenant_id: str,
    ) -> str:
        """
        pm4py가 생성한 BPMN XML을 ProcessDefinition으로 변환하여 저장

        Returns:
            proc_def_id: 생성된 프로세스 정의 ID
        """
        # 1. BPMN XML -> ProcessDefinition 변환
        proc_def = await self._parse_bpmn_to_definition(bpmn_xml)

        # 2. 메타데이터 보강
        proc_def.description = (
            f"프로세스 마이닝으로 자동 발견된 모델\n"
            f"알고리즘: {mining_metadata.get('algorithm', 'unknown')}\n"
            f"Fitness: {mining_metadata.get('fitness', 0):.2f}\n"
            f"케이스 수: {mining_metadata.get('case_count', 0)}"
        )

        # 3. DB 저장 (type="discovered"로 구분)
        async with get_session() as session:
            db_proc_def = ProcDef(
                name=proc_def.process_definition_name,
                bpmn=bpmn_xml,
                definition=proc_def.model_dump(),
                type="discovered",  # BPM 설계 모델과 구분
                tenant_id=tenant_id,
            )
            session.add(db_proc_def)

            # 4. 출처 추적을 위한 연결
            link = ProcDefMiningLink(
                proc_def_id=db_proc_def.id,
                event_log_id=event_log_id,
                fitness=mining_metadata.get("fitness"),
                precision=mining_metadata.get("precision"),
            )
            session.add(link)

            await session.commit()

        # 5. 이벤트 발행
        await EventPublisher.publish(
            event_type="DISCOVERED_MODEL_IMPORTED",
            aggregate_type="proc_def",
            aggregate_id=db_proc_def.id,
            payload={
                "proc_def_id": str(db_proc_def.id),
                "event_log_id": event_log_id,
                "source": "process_mining",
            },
        )

        return str(db_proc_def.id)
```

### 7.5 금지/필수 규칙

```
[금지] 발견된 모델을 자동으로 BPM 실행 모델에 적용하지 않는다.
       반드시 프로세스 분석가의 검토(HITL)를 거쳐야 한다.
[금지] BPM 로그 내보내기 시 다른 테넌트의 데이터를 포함하지 않는다.
       tenant_id 필터링은 필수이다.

[필수] 발견된 모델은 type="discovered"로 저장하여 설계 모델(type="base")과 구분한다.
[필수] 이벤트 로그 변환 시 agent_mode 정보를 포함하여,
       AI 자동실행과 사람 실행을 구분할 수 있도록 한다.
[필수] 모든 임포트에 source_event_log_id를 기록하여 출처 추적이 가능해야 한다.
```

<!-- affects: api, data, llm -->
<!-- requires-update: 02_api/process-api.md, 06_data/event-log-schema.md, 05_llm/agent-architecture.md -->

---

## 8. 재평가 조건

| 조건 | 재평가 대상 |
|------|-----------|
| 프로세스 정의 100개 초과 | 프로세스 정의 캐싱 전략 |
| 동시 실행 인스턴스 500개 초과 | BPM 엔진 수평 확장 (상태 외부화) |
| Saga 보상 실패율 5% 초과 | 보상 전략 재검토 (수동 개입 비율 분석) |
| BPMN 추출 정확도 70% 미만 | 프롬프트 최적화 또는 Fine-tuning 검토 |
| 마이닝 발견 모델 Fitness < 0.7 | 이벤트 로그 품질 검토, 전처리 파이프라인 개선 |
| BPM 로그 내보내기 10만 건 초과 | 배치 내보내기 전략, 증분 내보내기 도입 |
| 발견 모델 HITL 승인율 < 50% | 마이닝 알고리즘 파라미터 튜닝, 노이즈 필터링 강화 |

---

## 근거

- K-AIR 역설계 보고서 섹션 9 (프로세스 엔진)
- process-gpt-completion-main 소스코드 (process_engine.py, compensation_handler.py)
- process-gpt-bpmn-extractor-main 소스코드 (entity_extractor.py, bpmn_generator.py)
- ADR-005: Saga 보상 트랜잭션 패턴
