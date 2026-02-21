# Axiom Core - 프로세스 실행 API

> 구현 상태 태그: `Implemented`
> 기준일: 2026-02-21

## 이 문서가 답하는 질문

- 프로세스를 시작/완료/재작업하는 API는 어떻게 사용하는가?
- 각 엔드포인트의 요청/응답 형식은 무엇인가?
- 어떤 필드가 nullable이고, 어떤 권한이 필요한가?

<!-- affects: frontend, backend -->
<!-- requires-update: 01_architecture/bpm-engine.md -->

---

## 1. 엔드포인트 목록

| Method | Path | 설명 | 인증 | 타임아웃 | 상태 | 근거(구현/티켓) |
|--------|------|------|------|---------|------|------------------|
| POST | `/api/v1/process/initiate` | 프로세스 인스턴스 시작 | 필수 | 60s | Implemented | `services/core/app/api/process/routes.py` |
| POST | `/api/v1/process/submit` | 워크아이템 제출 (완료) | 필수 | 60s | Implemented | `services/core/app/api/process/routes.py` |
| POST | `/api/v1/process/role-binding` | 역할-사용자 바인딩 | 필수 | 30s | Implemented | `services/core/app/api/process/routes.py` |
| GET | `/api/v1/process/{proc_inst_id}/status` | 프로세스 상태 조회 | 필수 | 10s | Implemented | `services/core/app/api/process/routes.py` |
| GET | `/api/v1/process/{proc_inst_id}/workitems` | 워크아이템 목록 조회 | 필수 | 10s | Implemented | `services/core/app/api/process/routes.py` |
| GET | `/api/v1/process/feedback/{workitem_id}` | 피드백 조회 | 필수 | 10s | Implemented | `services/core/app/api/process/routes.py` |
| POST | `/api/v1/process/rework` | 재작업 요청 | 필수 | 30s | Implemented | `services/core/app/api/process/routes.py` |
| POST | `/api/v1/process/approve-hitl` | HITL 승인/거부 | 필수 | 30s | Implemented | `services/core/app/api/process/routes.py` |
| GET | `/api/v1/process/definitions` | 프로세스 정의 목록 | 필수 | 10s | Implemented | `services/core/app/api/process/routes.py` |
| POST | `/api/v1/process/definitions` | 프로세스 정의 생성 | 필수 | 120s | Implemented | `services/core/app/api/process/routes.py` |

---

## 2. 엔드포인트 상세

### 2.1 POST /api/v1/process/initiate

프로세스 인스턴스를 시작한다.

#### 요청

```json
{
  "proc_def_id": "uuid (required) - 프로세스 정의 ID",
  "input_data": {
    "case_id": "uuid (optional) - 연결할 사건 ID",
    "initial_values": {}
  },
  "role_bindings": [
    {
      "role_name": "string (required) - 역할 이름",
      "user_id": "uuid (optional) - 할당 사용자. null이면 자동 할당"
    }
  ]
}
```

#### 응답 (201 Created)

```json
{
  "proc_inst_id": "uuid",
  "status": "RUNNING",
  "current_workitems": [
    {
      "workitem_id": "uuid",
      "activity_name": "데이터 등록서 접수",
      "activity_type": "humanTask",
      "assignee_id": "uuid | null",
      "agent_mode": "MANUAL",
      "status": "TODO",
      "created_at": "2026-02-19T10:00:00Z"
    }
  ]
}
```

#### 에러

| 코드 | 조건 |
|------|------|
| 404 | proc_def_id에 해당하는 프로세스 정의가 없음 |
| 400 | role_bindings에 필수 역할이 누락됨 |
| 403 | 현재 사용자가 프로세스를 시작할 권한이 없음 |

#### 권한

- `process:initiate` 권한 필요
- 프로젝트 범위: 같은 테넌트 내

---

### 2.2 POST /api/v1/process/submit

워크아이템을 제출(완료 처리)한다.

#### 요청

```json
{
  "workitem_id": "uuid (required) - 워크아이템 ID",
  "result_data": {
    "output_fields": {},
    "comments": "string (optional) - 처리 의견"
  },
  "force_complete": false
}
```

#### 응답 (200 OK)

```json
{
  "workitem_id": "uuid",
  "status": "DONE",
  "next_workitems": [
    {
      "workitem_id": "uuid",
      "activity_name": "데이터 수치 검증",
      "activity_type": "serviceTask",
      "agent_mode": "SUPERVISED",
      "status": "TODO"
    }
  ],
  "process_status": "RUNNING",
  "is_process_completed": false
}
```

#### 에러

| 코드 | 조건 |
|------|------|
| 404 | workitem_id에 해당하는 워크아이템이 없음 |
| 409 | 이미 DONE 상태인 워크아이템 |
| 422 | 현재 상태에서 제출 불가 (예: 다른 사용자가 진행 중) |
| 403 | 현재 사용자가 이 워크아이템의 담당자가 아님 |

---

### 2.3 POST /api/v1/process/approve-hitl

SUPERVISED 모드에서 에이전트 실행 결과를 승인하거나 거부한다.

#### 요청

```json
{
  "workitem_id": "uuid (required)",
  "approved": true,
  "modifications": {
    "corrected_fields": {},
    "feedback": "string (optional) - 피드백 (거부 시 사유)"
  }
}
```

#### 응답 (200 OK)

```json
{
  "workitem_id": "uuid",
  "status": "DONE",
  "approved": true,
  "feedback_captured": true,
  "next_workitems": []
}
```

#### 비즈니스 규칙

```
[필수] approved=false인 경우, modifications.feedback은 필수이다.
[사실] 거부된 결과는 자동으로 3티어 지식 학습 루프에 입력된다.
[사실] 승인된 결과도 신뢰도가 80%~99%이면 학습 데이터로 활용한다.
```

---

### 2.4 POST /api/v1/process/rework

이미 완료된 워크아이템을 재작업 상태로 되돌린다.

#### 요청

```json
{
  "workitem_id": "uuid (required)",
  "reason": "string (required) - 재작업 사유",
  "revert_to_activity_id": "uuid (optional) - 특정 활동으로 되돌리기. null이면 직전 활동"
}
```

#### 응답 (200 OK)

```json
{
  "workitem_id": "uuid",
  "status": "TODO",
  "reworked_from": "uuid",
  "reason": "데이터 분류가 잘못되었습니다",
  "saga_compensations": [
    {
      "activity": "최적화 스케줄 생성",
      "status": "COMPENSATED",
      "action": "최적화 스케줄 삭제"
    }
  ]
}
```

#### 병렬 분기 재작업 시 응답 예시

병렬 게이트웨이(ParallelGateway)로 분기된 작업 중 재작업이 발생하면, 완료된 분기는 `COMPENSATED`, 진행 중인 분기는 `CANCELLED`로 처리된다.

```json
{
  "workitem_id": "uuid",
  "status": "TODO",
  "reworked_from": "uuid",
  "reason": "데이터 수치 검증 결과 오류 발견",
  "saga_compensations": [
    {
      "activity": "데이터 수치 검증",
      "status": "COMPENSATED",
      "action": "검증 결과 삭제"
    },
    {
      "activity": "데이터 분류",
      "status": "CANCELLED",
      "action": "진행 중인 에이전트 작업 취소"
    }
  ]
}
```

#### saga_compensations 상태 값

| 상태 | 의미 | 발생 조건 |
|------|------|----------|
| `COMPENSATED` | 보상 트랜잭션 정상 완료 | 완료된(DONE/SUBMITTED) 워크아이템 |
| `CANCELLED` | 진행 중 작업 취소 | TODO/IN_PROGRESS 워크아이템 (병렬 분기) |
| `FAILED` | 보상 실패 (수동 개입 필요) | 보상 재시도 모두 실패 |
| `SKIPPED` | 보상 불필요 | 보상 액션이 정의되지 않은 Activity |

> **상세**: 병렬 분기 보상 전략은 [bpm-engine.md](../01_architecture/bpm-engine.md) §5.5, Saga 불변성은 [ADR-005](../99_decisions/ADR-005-saga-compensation.md) §7을 참조한다.

#### 비즈니스 규칙

```
[필수] 재작업 시 해당 활동 이후의 모든 결과는 Saga 보상으로 롤백된다.
[필수] 병렬 분기 재작업 시, 진행 중인 분기는 취소(CANCELLED) 처리한다.
[사실] 재작업 이력은 감사 로그에 기록된다.
[사실] 병렬 분기의 모든 브랜치가 보상/취소 완료된 후에만 이전 Activity 보상을 진행한다.
[금지] PROCESS_COMPLETED 상태의 프로세스는 재작업할 수 없다. 새 인스턴스를 시작해야 한다.
```

---

### 2.5 POST /api/v1/process/definitions

자연언어 또는 BPMN XML로 프로세스를 정의한다.

#### 요청 (자연언어)

```json
{
  "name": "string (required)",
  "description": "string (required) - 자연언어 프로세스 설명",
  "type": "base",
  "source": "natural_language",
  "activities_hint": [
    "데이터 등록서 접수 (수동)",
    "데이터 수치 자동 검증 (AI 자율)",
    "데이터 분류 (AI 반자동)",
    "이슈 있으면 이슈 처리, 없으면 확정"
  ]
}
```

#### 요청 (BPMN XML)

```json
{
  "name": "string (required)",
  "bpmn_xml": "string (required) - BPMN 2.0 XML",
  "type": "base",
  "source": "bpmn_upload"
}
```

#### 응답 (201 Created)

```json
{
  "proc_def_id": "uuid",
  "name": "공급망 데이터 검증",
  "version": 1,
  "activities_count": 4,
  "gateways_count": 1,
  "definition": { ... },
  "bpmn_xml": "<bpmn:definitions ...>",
  "confidence": 0.87,
  "needs_review": true
}
```

---

## 3. 공통 규약

### 3.1 페이지네이션

목록 조회 API는 커서 기반 페이지네이션을 사용한다.

```
GET /api/v1/process/definitions?cursor=uuid&limit=20&sort=created_at:desc
```

응답:

```json
{
  "data": [...],
  "cursor": {
    "next": "uuid | null",
    "has_more": true
  },
  "total_count": 42
}
```

### 3.2 필터링

```
GET /api/v1/process/{proc_inst_id}/workitems?status=TODO&agent_mode=SUPERVISED
```

### 3.3 일괄 작업(Batch)

```json
POST /api/v1/process/batch/submit
{
  "workitem_ids": ["uuid1", "uuid2", "uuid3"],
  "result_data": {}
}
```

### 3.4 Workitem 상태 전이

워크아이템은 다음 6개 상태를 가진다. 이 상태 체계는 API 응답의 `status` 필드와 필터링 파라미터(§3.2)에 공통 적용된다.

| 상태 | 의미 | 진입 조건 |
|:----:|------|----------|
| `TODO` | 생성됨, 미착수 | 프로세스 시작(§2.1) 또는 이전 Activity 완료 시 |
| `IN_PROGRESS` | 진행 중 (에이전트 실행 또는 사용자 작업 중) | 담당자가 작업 시작 또는 에이전트 자동 착수 |
| `SUBMITTED` | 에이전트 완료, HITL 검토 대기 | SUPERVISED 모드 에이전트 실행 완료 시 |
| `DONE` | 완료 | submit(§2.2) 또는 approve-hitl(§2.3) 승인 |
| `REWORK` | 재작업 중 | rework(§2.4) 요청 시 |
| `CANCELLED` | 취소됨 (병렬 분기) | 병렬 분기 보상 시 진행 중인 분기 취소 |

상태 전이 다이어그램:

```
TODO ──→ IN_PROGRESS ──→ SUBMITTED ──→ DONE
  │           │              │            │
  │           │              └──→ REWORK ──┘ (approve-hitl 거부 시)
  │           │                     ↑
  │           └─────────────────────┘ (rework)
  │
  └──→ CANCELLED (병렬 분기 보상)

IN_PROGRESS ──→ CANCELLED (병렬 분기 보상)
```

> **상세**: BPM 엔진의 상태 관리는 [bpm-engine.md](../01_architecture/bpm-engine.md) §3, 병렬 분기 보상은 §5.5를 참조한다.

---

## 근거

- K-AIR 역설계 보고서 섹션 15.3 (process-gpt-completion API)
- process-gpt-completion-main 소스코드 (라우터 10개 모듈)
- 01_architecture/bpm-engine.md (BPM 엔진 설계)
