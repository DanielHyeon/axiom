# ADR-005: Saga 보상 트랜잭션 패턴 채택

## 상태

Accepted

## 배경

K-AIR/Process-GPT 시스템의 BPM 엔진(`process-gpt-completion-main`)은 **Saga 패턴**으로 분산 트랜잭션을 처리한다. 프로세스 실행 중 AI 에이전트가 여러 단계의 작업을 수행하며, 중간 단계에서 실패 시 이전 단계의 결과를 자동으로 보상(롤백)한다.

**K-AIR 현행 Saga 구조**:

```python
# process-gpt-completion-main - Saga 보상 로직

# 각 활동(Activity)에 compensation 정의
class ProcessActivity:
    name: str
    instruction: str
    compensation: dict  # 보상 액션 정의
    # compensation = {
    #     "type": "mcp_tool",
    #     "server": "claude-skills",
    #     "tool": "rollback_record_status",
    #     "params": {"record_id": "$output.record_id", "previous_status": "$input.status"}
    # }
```

**문제**:
1. 비즈니스 프로세스는 다단계이며, 각 단계가 외부 시스템(ERP, CRM, 금융 API 등)과 상호작용한다.
2. 전통적 2PC(Two-Phase Commit)는 마이크로서비스 아키텍처에서 사용 불가하다.
3. AI 에이전트의 작업은 비결정적(non-deterministic)이므로, 실패 시 동일 결과로 복원하기 어렵다.
4. 비즈니스 프로세스 도메인에서 LOCK 상태의 데이터는 불변이어야 하며, LOCK 위반 시 자동 롤백이 운영 요구사항이다.
5. K-AIR의 Saga 패턴은 MCP 도구로 보상 액션을 실행하는데, 이 패턴의 장점을 Axiom에 계승해야 한다.

## 검토한 옵션

### 옵션 1: 2PC (Two-Phase Commit)

**장점**:
- 강력한 일관성(Strong Consistency) 보장
- 롤백 로직이 자동

**단점**:
- FastAPI 단일 서비스에서도 외부 시스템(ERP API, 금융 API)과의 분산 트랜잭션에는 2PC 불가
- 장시간 실행 프로세스(수일~수주)에서 잠금(Lock) 유지 불가능
- AI 에이전트 실행은 비결정적이므로 롤백 = 원상복구가 아님

### 옵션 2: 이벤트 소싱 (Event Sourcing)

**장점**:
- 모든 상태 변경을 이벤트로 기록 → 시간 여행 가능
- 보상 = 역방향 이벤트 발행

**단점**:
- 전체 아키텍처를 이벤트 소싱으로 설계해야 함 (대규모 리팩토링)
- CQRS 패턴 필수 → 복잡도 급증
- 소규모 팀에서 이벤트 소싱 + CQRS 운영은 비현실적
- K-AIR의 기존 CRUD 패턴과 호환 불가

### 옵션 3: Saga 보상 트랜잭션 + MCP 도구 (선택)

**장점**:
- 각 단계(Activity)에 보상 액션을 정의하여 역방향 복원
- MCP 도구로 보상 액션을 실행하므로 확장성 높음 (새 보상 액션 = 새 MCP 도구)
- K-AIR에서 검증된 패턴
- 장시간 실행 프로세스에 적합 (잠금 불필요)
- AI 에이전트의 비결정적 결과에 대한 "의미적 보상" 가능

**단점**:
- 보상 액션 자체가 실패할 수 있음 → 재시도 + 수동 개입 필요
- 최종 일관성(Eventual Consistency)만 보장
- 보상 로직을 Activity별로 별도 정의해야 함

## 선택한 결정

**옵션 3: Saga 보상 트랜잭션 + MCP 도구 기반 자동 롤백**

## 근거

### 1. Saga 실행 흐름

```
프로세스 인스턴스 시작 (proc_inst)
    │
    ▼
┌─ Activity 1: 데이터 등록 접수 ──────────────────┐
│  실행: agent.execute(instruction)                 │
│  결과: record_id=REC-001, status=FILED           │
│  보상 정의: rollback_record_status(REC-001, DRAFT)│
└──────────────────────────────┬────────────────────┘
                               │ 성공
                               ▼
┌─ Activity 2: 검증 보고서 생성 ───────────────────┐
│  실행: agent.execute(instruction)                  │
│  결과: report_id=RPT-001, status=GENERATED        │
│  보상 정의: delete_report(RPT-001)                │
└──────────────────────────────┬─────────────────────┘
                               │ 성공
                               ▼
┌─ Activity 3: 이해관계자 통지 발송 ────────────────┐
│  실행: agent.execute(instruction)                   │
│  결과: 실패! (이메일 서버 장애)                     │
│  보상 정의: (해당 없음 - 실패했으므로 보상 불필요)  │
└──────────────────────────────┬──────────────────────┘
                               │ 실패!
                               ▼
           ┌─ 보상 트랜잭션 시작 (역순 실행) ─┐
           │                                    │
           │  보상 2: delete_report(RPT-001)    │
           │  보상 1: rollback_record_status(   │
           │           REC-001, DRAFT)          │
           │                                    │
           └─ 보상 완료 ──────────────────────┘
```

### 2. Saga 엔진 구현

```python
# app/bpm/saga.py

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class SagaStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
    FAILED = "FAILED"  # 보상도 실패

@dataclass
class CompensationAction:
    """보상 액션 정의"""
    type: str                  # "mcp_tool" | "db_rollback" | "api_call"
    server: str                # MCP 서버 이름
    tool: str                  # MCP 도구 이름
    params: dict               # 파라미터 (변수 바인딩 지원)
    max_retries: int = 3
    retry_delay_seconds: int = 5

@dataclass
class SagaStep:
    """Saga 단계"""
    activity_id: str
    activity_name: str
    status: str                # "PENDING" | "COMPLETED" | "FAILED" | "COMPENSATED"
    result: Optional[dict] = None
    compensation: Optional[CompensationAction] = None
    compensated_at: Optional[str] = None

@dataclass
class SagaContext:
    """Saga 실행 컨텍스트"""
    proc_inst_id: str
    tenant_id: str
    steps: List[SagaStep] = field(default_factory=list)
    status: SagaStatus = SagaStatus.RUNNING
    current_step_index: int = 0

class SagaExecutor:
    """Saga 패턴 실행기"""

    def __init__(self, mcp_client, db_session):
        self.mcp_client = mcp_client
        self.db = db_session

    async def execute_step(
        self, context: SagaContext, activity, agent_result: dict
    ) -> SagaStep:
        """단계 실행 및 보상 정보 기록"""
        step = SagaStep(
            activity_id=activity.id,
            activity_name=activity.name,
            status="COMPLETED",
            result=agent_result,
            compensation=self._build_compensation(
                activity.compensation, agent_result
            ),
        )
        context.steps.append(step)
        context.current_step_index += 1

        # Saga 상태를 DB에 영속화 (장애 복구용)
        await self._persist_saga_state(context)

        return step

    async def compensate(self, context: SagaContext) -> None:
        """보상 트랜잭션 실행 (역순)"""
        context.status = SagaStatus.COMPENSATING

        # 완료된 단계를 역순으로 보상
        completed_steps = [
            s for s in context.steps if s.status == "COMPLETED"
        ]

        for step in reversed(completed_steps):
            if step.compensation is None:
                continue

            success = await self._execute_compensation(
                step.compensation, context
            )

            if success:
                step.status = "COMPENSATED"
                step.compensated_at = datetime.utcnow().isoformat()
            else:
                # 보상 실패 → 수동 개입 필요
                context.status = SagaStatus.FAILED
                await self._alert_manual_intervention(context, step)
                return

        context.status = SagaStatus.COMPENSATED
        await self._persist_saga_state(context)

    async def _execute_compensation(
        self, compensation: CompensationAction, context: SagaContext
    ) -> bool:
        """MCP 도구로 보상 액션 실행"""
        for attempt in range(compensation.max_retries):
            try:
                if compensation.type == "mcp_tool":
                    result = await self.mcp_client.execute_tool(
                        server=compensation.server,
                        tool=compensation.tool,
                        params=self._resolve_params(
                            compensation.params, context
                        ),
                    )
                    return result.get("success", False)

                elif compensation.type == "db_rollback":
                    await self._db_rollback(compensation.params)
                    return True

            except Exception as e:
                logger.warning(
                    f"Compensation attempt {attempt + 1} failed: {e}"
                )
                if attempt < compensation.max_retries - 1:
                    await asyncio.sleep(compensation.retry_delay_seconds)

        return False  # 모든 재시도 실패

    def _build_compensation(
        self, comp_def: dict, result: dict
    ) -> Optional[CompensationAction]:
        """활동 정의에서 보상 액션 빌드"""
        if not comp_def:
            return None

        # 파라미터에서 변수 바인딩 해결
        # "$output.record_id" → result["record_id"]
        params = {}
        for key, value in comp_def.get("params", {}).items():
            if isinstance(value, str) and value.startswith("$output."):
                field_name = value[len("$output."):]
                params[key] = result.get(field_name)
            elif isinstance(value, str) and value.startswith("$input."):
                field_name = value[len("$input."):]
                params[key] = result.get(f"input_{field_name}")
            else:
                params[key] = value

        return CompensationAction(
            type=comp_def["type"],
            server=comp_def.get("server", ""),
            tool=comp_def.get("tool", ""),
            params=params,
            max_retries=comp_def.get("max_retries", 3),
        )

    def _resolve_params(
        self, params: dict, context: SagaContext
    ) -> dict:
        """컨텍스트에서 파라미터 값 해결"""
        resolved = {}
        for key, value in params.items():
            if isinstance(value, str) and value.startswith("$context."):
                field_name = value[len("$context."):]
                resolved[key] = getattr(context, field_name, value)
            else:
                resolved[key] = value
        return resolved
```

### 3. 비즈니스 프로세스 도메인의 LOCK 불변성

```
[결정] LOCK 상태 데이터의 변경 시도는 Saga 보상으로 자동 롤백한다.
[근거] 비즈니스 프로세스에서 확정된 데이터(승인 완료 결정, 확정 데이터)는
       운영 불변성을 가진다. AI 에이전트가 실수로 변경하더라도
       Saga 보상으로 원상 복구해야 한다.
```

LOCK 위반 감지 및 보상 흐름:

```python
# BPM 엔진에서 LOCK 불변성 검사

async def validate_lock_invariants(
    activity_result: dict,
    saga_context: SagaContext,
) -> bool:
    """LOCK 불변성 위반 검사"""

    violations = []

    # 확정 데이터 수치 변경 시도 검사
    if "record_value" in activity_result:
        record = await get_record(activity_result["record_id"])
        if record.status == "CONFIRMED":
            violations.append({
                "type": "LOCK_VIOLATION",
                "entity": "record",
                "field": "value",
                "locked_value": record.value,
                "attempted_value": activity_result["record_value"],
            })

    # 승인 완료 후 최적화 계획 변경 시도 검사
    if "optimization_plan" in activity_result:
        case = await get_case(saga_context.case_id)
        if case.status == "PLAN_APPROVED":
            violations.append({
                "type": "LOCK_VIOLATION",
                "entity": "optimization_plan",
                "field": "schedule",
                "reason": "Plan already approved by decision maker",
            })

    if violations:
        logger.error(f"LOCK violations detected: {violations}")
        # Event Outbox에 위반 이벤트 기록
        await publish_event("lock.violation_detected", {
            "proc_inst_id": saga_context.proc_inst_id,
            "violations": violations,
        })
        # Saga 보상 트리거
        await saga_executor.compensate(saga_context)
        return False

    return True
```

### 4. MCP 도구 기반 보상의 장점

보상 액션을 MCP 도구로 구현하면:

| 장점 | 설명 |
|------|------|
| **확장성** | 새 보상 액션 = 새 MCP 도구 추가 (코드 변경 최소) |
| **테넌트 격리** | SafeToolLoader가 테넌트별 도구 접근 제어 |
| **감사 가능성** | 모든 MCP 도구 호출이 로깅됨 |
| **재사용성** | 동일 MCP 도구를 다른 Saga에서도 사용 가능 |
| **보안** | SafeToolLoader의 보안 정책으로 위험한 보상 차단 |

보상 MCP 도구 예시:

```json
{
  "보상 도구 카탈로그": {
    "rollback_record_status": {
      "server": "axiom-bpm-tools",
      "description": "데이터 레코드 상태를 이전 값으로 되돌림",
      "params": {
        "record_id": "대상 레코드 ID",
        "previous_status": "되돌릴 상태 값"
      }
    },
    "delete_generated_report": {
      "server": "axiom-document-tools",
      "description": "생성된 보고서를 삭제",
      "params": {
        "report_id": "삭제할 보고서 ID"
      }
    },
    "cancel_notification": {
      "server": "axiom-notification-tools",
      "description": "발송 예약된 통지를 취소",
      "params": {
        "notification_id": "취소할 통지 ID"
      }
    },
    "restore_case_snapshot": {
      "server": "axiom-case-tools",
      "description": "프로젝트 데이터를 스냅샷으로 복원",
      "params": {
        "case_id": "대상 프로젝트 ID",
        "snapshot_id": "복원할 스냅샷 ID"
      }
    }
  }
}
```

### 5. Saga 상태 영속화

장애 발생 시 보상 트랜잭션을 재개하기 위해 Saga 상태를 DB에 영속화한다:

```sql
-- Saga 상태 테이블 (event_outbox와 별도)

CREATE TABLE saga_state (
    saga_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proc_inst_id UUID NOT NULL REFERENCES bpm_proc_inst(proc_inst_id),
    tenant_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'RUNNING',
    steps JSONB NOT NULL DEFAULT '[]',
    current_step_index INT NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    compensated_at TIMESTAMPTZ,
    error_detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS 정책
ALTER TABLE saga_state ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON saga_state
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 인덱스
CREATE INDEX idx_saga_state_proc_inst ON saga_state(proc_inst_id);
CREATE INDEX idx_saga_state_status ON saga_state(status)
    WHERE status IN ('RUNNING', 'COMPENSATING');
```

서버 재시작 후 `status = 'COMPENSATING'`인 Saga를 자동 재개:

```python
# app/bpm/saga_recovery.py

async def recover_incomplete_sagas():
    """서버 시작 시 미완료 Saga 복구"""
    async with get_session() as session:
        incomplete = await session.execute(
            select(SagaStateModel).where(
                SagaStateModel.status.in_(["RUNNING", "COMPENSATING"])
            )
        )

        for saga_record in incomplete.scalars():
            context = SagaContext.from_db(saga_record)

            if context.status == SagaStatus.COMPENSATING:
                logger.info(f"Resuming compensation for saga {context.saga_id}")
                await saga_executor.compensate(context)
            elif context.status == SagaStatus.RUNNING:
                # 실행 중이던 Saga는 타임아웃 검사
                if is_timed_out(saga_record.started_at):
                    logger.warning(f"Saga {context.saga_id} timed out, compensating")
                    await saga_executor.compensate(context)
```

### 6. 보상 실패 시 에스컬레이션

보상 자체가 실패하면 자동 복구가 불가능하다. 이 경우 수동 개입을 위한 에스컬레이션 프로세스:

```
보상 실패
    │
    ├─ 1. 재시도 (max_retries=3, 지수 백오프)
    │
    ├─ 2. 재시도 모두 실패
    │   ├─ Saga 상태 → FAILED
    │   ├─ Event Outbox에 "saga.compensation_failed" 이벤트 발행
    │   └─ Watch Alert 생성 (severity=CRITICAL)
    │
    └─ 3. 관리자 수동 처리
        ├─ 관리자 대시보드에서 실패한 Saga 조회
        ├─ 개별 보상 단계 수동 실행 또는 건너뛰기
        └─ 수동 완료 후 Saga 상태 → COMPENSATED (수동)
```

### 7. 병렬 분기(Parallel Gateway) 보상 불변성

ParallelGateway로 생성된 병렬 분기에 대한 Saga 보상 규칙이다. 상세 구현은 [bpm-engine.md](../01_architecture/bpm-engine.md) §5.5를 참조한다.

#### 불변성 규칙

```
[불변성] 병렬 분기 보상 시, 진행 중인(IN_PROGRESS/TODO) 워크아이템은 보상하지 않고
         취소(CANCELLED) 처리한다.
[불변성] 병렬 분기의 모든 브랜치가 보상/취소 완료된 후에만 분기 이전 Activity 보상을 진행한다.
[불변성] 병렬 분기 내 Activity의 보상 순서는 분기 내 실행 순서의 역순이다.
         분기 간(inter-branch) 보상 순서는 없다 (독립 실행).
```

#### Saga 상태 전이 확장

기존 상태 전이에 `CANCELLING` 단계가 추가된다:

```
RUNNING → COMPENSATING → CANCELLING (병렬 분기 취소) → COMPENSATED | FAILED
                                          ↓
                            (취소 완료 후 완료된 분기 보상 계속)
```

| 상태 | 의미 |
|------|------|
| `CANCELLING` | 병렬 분기의 진행 중 워크아이템을 취소하는 중 |

#### CompensationStep 확장 필드

```python
# saga_state.steps JSONB에 추가되는 필드
{
  "activity_id": "uuid",
  "activity_name": "데이터 분류",
  "status": "CANCELLED",                 # CANCELLED 상태 추가
  "parallel_group_id": "gateway-uuid",   # Fork Gateway ID (null이면 순차)
  "branch_index": 2,                     # 병렬 분기 내 인덱스
  "cancelled_at": "2026-02-20T10:00:00Z"
}
```

#### 보상 MCP 도구 확장

```json
{
  "cancel_agent_task": {
    "server": "axiom-bpm-tools",
    "description": "진행 중인 에이전트 작업을 취소",
    "params": {
      "workitem_id": "취소할 워크아이템 ID",
      "agent_task_id": "에이전트 태스크 ID (실행 중인 경우)"
    }
  },
  "revert_extraction": {
    "server": "axiom-synapse-tools",
    "description": "Synapse에서 committed 온톨로지 엔티티/관계를 되돌림",
    "params": {
      "doc_id": "문서 ID",
      "entity_ids": "되돌릴 엔티티 ID 배열",
      "relation_ids": "되돌릴 관계 ID 배열"
    }
  }
}
```

## 결과

### 긍정적 영향
- 비즈니스 프로세스의 운영 불변성(LOCK) 자동 보장
- MCP 도구 기반으로 보상 액션 확장이 용이
- K-AIR 검증 패턴 계승으로 구현 위험 최소
- Saga 상태 영속화로 장애 복구 가능
- AI 에이전트의 비결정적 결과에 대한 "의미적 보상" 지원

### 부정적 영향
- 최종 일관성(Eventual Consistency)만 보장 → 보상 실행 중 일시적 불일치
- 보상 액션 정의가 Activity별로 필요 → 프로세스 정의 복잡도 증가
- 보상 실패 시 수동 개입 불가피
- Saga 상태 테이블 추가 → DB 스키마 확장

### K-AIR 대비 개선사항

| 항목 | K-AIR | Axiom |
|------|-------|-------|
| 보상 실행 | 동기 MCP 호출 | 비동기 + 재시도 (지수 백오프) |
| 상태 영속화 | 메모리에만 보관 | DB 영속화 (장애 복구) |
| 장애 복구 | 수동 | 자동 재개 (saga_recovery) |
| LOCK 검사 | 수동 코드 | 자동화된 불변성 검증 |
| 에스컬레이션 | 없음 | Watch Alert + 관리자 대시보드 |
| 감사 로그 | 부분적 | 모든 보상 단계 기록 |

## 재평가 조건

- 외부 시스템(ERP API, 금융 API)이 분산 트랜잭션(XA)을 지원하는 경우 → 2PC 부분 도입 검토
- 프로세스 단계가 20개 이상으로 복잡해져 보상 정의 비용이 과도한 경우 → 이벤트 소싱 검토
- 보상 실패율이 5%를 초과하는 경우 → 보상 전략 재설계 + 스냅샷 기반 복원 검토
- 규제 기관이 강력한 일관성(Strong Consistency)을 요구하는 경우 → 아키텍처 재검토
