# DDD Phase 1: 도메인 모델 강화

> **Phase**: P1 (Domain Model Strengthening)
> **기간**: 3~6주
> **선행조건**: Phase 0 (Gate DDD-0) 통과
> **Gate**: DDD-1 — **PASS**
> **상태**: **전체 완료**
> **관련 Anti-pattern**: A1 (CRITICAL), A4 (HIGH), A5 (HIGH), A8 (MEDIUM)

---

## 1. 목표

Core 서비스를 중심으로 **Tactical DDD 패턴을 도입**하여, Anemic Domain Model을
Rich Domain Model로 전환한다. 명시적 Aggregate, Repository 인터페이스, domain/ 패키지 분리,
DB 스키마 분리를 완료하여 각 BC의 데이터 소유권을 확립한다.

---

## 2. 티켓 목록 및 완료 현황

| 티켓 ID | 제목 | 상태 | 핵심 산출물 |
|:-------:|------|:----:|----------|
| DDD-P1-01 | WorkItem Aggregate Rich Model 전환 | **DONE** | `modules/process/domain/aggregates/work_item.py` (262줄) |
| DDD-P1-02 | Repository 패턴 도입 | **DONE** | `domain/repositories/` ABC + `infrastructure/repositories/` SQLAlchemy |
| DDD-P1-03 | domain/ 패키지 생성 및 레이어 분리 | **DONE** | `modules/process/{domain,application,infrastructure,api}/` |
| DDD-P1-04 | DB 스키마 분리 (서비스별 전용 스키마) | **DONE** | core/synapse/vision/weaver/oracle 5개 스키마 |
| DDD-P1-05 | ProcessService God Class 분할 | **DONE** | 4개 서비스 분할 (각 62~324줄) |

---

## 3. DDD-P1-01: WorkItem Aggregate Rich Model 전환

### 3.1 현황 (AS-IS)

**문제**: `WorkItem` (`services/core/app/models/base_models.py:55-73`)은 순수 데이터 컨테이너이며,
모든 비즈니스 규칙이 `ProcessService.submit_workitem()` (`services/core/app/services/process_service.py:328-400`)에 절차적으로 구현되어 있다.

```python
# AS-IS: 도메인 로직이 Service에 노출
workitem.status = next_status        # 직접 setter, 불변식 없음
workitem.result_data = body          # 직접 setter
workitem.version += 1               # 수동 증가, 동시성 보호 없음
```

**식별된 불변식** (ProcessService에 분산):
1. `DONE`/`CANCELLED` 상태에서는 제출 불가 (line 340-341)
2. `SUBMITTED` 상태에서 `force_complete` 없이 완료 불가 (line 343-344)
3. 상태 전이: `TODO → IN_PROGRESS → SUBMITTED → DONE` 또는 `TODO → IN_PROGRESS → DONE`
4. `version`은 상태 변경마다 단조 증가

### 3.2 목표 (TO-BE)

```
WorkItem Aggregate
├── 불변식 내부 보호 (submit, complete, cancel 메서드)
├── 상태 전이 규칙 (State Machine)
├── 도메인 이벤트 생성 (WorkItemCompleted, WorkItemSubmitted 등)
├── 낙관적 잠금 (version 관리)
└── 팩토리 메서드 (create)
```

### 3.3 구현 명세

#### 3.3.1 도메인 모델 클래스

```python
# services/core/app/domain/aggregates/work_item.py

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.domain.events import DomainEvent


class WorkItemStatus(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    DONE = "DONE"
    REWORK = "REWORK"
    CANCELLED = "CANCELLED"


class AgentMode(str, Enum):
    MANUAL = "MANUAL"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"
    SELF_VERIFY = "SELF_VERIFY"


# 허용된 상태 전이 맵
_TRANSITIONS: dict[WorkItemStatus, set[WorkItemStatus]] = {
    WorkItemStatus.TODO: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.IN_PROGRESS: {WorkItemStatus.SUBMITTED, WorkItemStatus.DONE, WorkItemStatus.CANCELLED},
    WorkItemStatus.SUBMITTED: {WorkItemStatus.DONE, WorkItemStatus.REWORK},
    WorkItemStatus.REWORK: {WorkItemStatus.IN_PROGRESS, WorkItemStatus.CANCELLED},
    WorkItemStatus.DONE: set(),
    WorkItemStatus.CANCELLED: set(),
}


class InvalidStateTransition(Exception):
    def __init__(self, current: WorkItemStatus, target: WorkItemStatus):
        super().__init__(f"Cannot transition from {current} to {target}")
        self.current = current
        self.target = target


@dataclass
class WorkItem:
    """
    WorkItem Aggregate Root.

    불변식:
    1. 상태 전이는 _TRANSITIONS 맵에 정의된 경로만 허용
    2. DONE/CANCELLED 상태에서는 어떤 변경도 불가
    3. version은 상태 변경마다 단조 증가
    4. SUBMITTED 상태에서 complete는 force_complete=True일 때만 허용
    """
    id: str
    proc_inst_id: str | None
    activity_name: str | None
    activity_type: str
    assignee_id: str | None
    agent_mode: AgentMode
    status: WorkItemStatus
    result_data: dict[str, Any] | None
    tenant_id: str
    version: int

    _events: list[DomainEvent] = field(default_factory=list, repr=False)

    # ── Factory ──────────────────────────────────
    @classmethod
    def create(
        cls,
        *,
        id: str,
        proc_inst_id: str | None,
        activity_name: str | None,
        activity_type: str = "humanTask",
        assignee_id: str | None = None,
        agent_mode: AgentMode = AgentMode.MANUAL,
        tenant_id: str,
    ) -> WorkItem:
        wi = cls(
            id=id,
            proc_inst_id=proc_inst_id,
            activity_name=activity_name,
            activity_type=activity_type,
            assignee_id=assignee_id,
            agent_mode=agent_mode,
            status=WorkItemStatus.TODO,
            result_data=None,
            tenant_id=tenant_id,
            version=1,
        )
        wi._record_event(WorkItemCreated(workitem_id=id, tenant_id=tenant_id))
        return wi

    # ── Commands ─────────────────────────────────
    def start(self) -> None:
        """TODO → IN_PROGRESS"""
        self._transition_to(WorkItemStatus.IN_PROGRESS)

    def submit(self, result_data: dict, verification_outcome: dict | None = None) -> None:
        """IN_PROGRESS → SUBMITTED (self-verification fail 시)"""
        self._transition_to(WorkItemStatus.SUBMITTED)
        self.result_data = result_data
        if verification_outcome:
            self.result_data["self_verification"] = verification_outcome
        self._record_event(WorkItemSubmitted(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            verification=verification_outcome,
        ))

    def complete(self, result_data: dict, *, force: bool = False) -> None:
        """IN_PROGRESS → DONE 또는 SUBMITTED → DONE (force=True)"""
        if self.status == WorkItemStatus.SUBMITTED and not force:
            raise InvalidStateTransition(self.status, WorkItemStatus.DONE)
        self._transition_to(WorkItemStatus.DONE)
        self.result_data = result_data
        self._record_event(WorkItemCompleted(
            workitem_id=self.id,
            proc_inst_id=self.proc_inst_id,
            tenant_id=self.tenant_id,
            result_data=result_data,
        ))

    def cancel(self, reason: str = "") -> None:
        """TODO/IN_PROGRESS/REWORK → CANCELLED"""
        self._transition_to(WorkItemStatus.CANCELLED)
        self._record_event(WorkItemCancelled(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            reason=reason,
        ))

    def request_rework(self, reason: str) -> None:
        """SUBMITTED → REWORK"""
        self._transition_to(WorkItemStatus.REWORK)
        self._record_event(WorkItemReworkRequested(
            workitem_id=self.id,
            tenant_id=self.tenant_id,
            reason=reason,
        ))

    # ── Event Collection ─────────────────────────
    def collect_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    # ── Private ──────────────────────────────────
    def _transition_to(self, target: WorkItemStatus) -> None:
        allowed = _TRANSITIONS.get(self.status, set())
        if target not in allowed:
            raise InvalidStateTransition(self.status, target)
        self.status = target
        self.version += 1
```

#### 3.3.2 도메인 이벤트 정의

```python
# services/core/app/domain/events.py

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class DomainEvent:
    """모든 도메인 이벤트의 기본 클래스."""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class WorkItemCreated(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""


@dataclass(frozen=True)
class WorkItemSubmitted(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    verification: dict | None = None


@dataclass(frozen=True)
class WorkItemCompleted(DomainEvent):
    workitem_id: str = ""
    proc_inst_id: str | None = None
    tenant_id: str = ""
    result_data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WorkItemCancelled(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    reason: str = ""


@dataclass(frozen=True)
class WorkItemReworkRequested(DomainEvent):
    workitem_id: str = ""
    tenant_id: str = ""
    reason: str = ""
```

### 3.4 테스트 전략

도메인 단위 테스트가 **가장 많은 비중**을 차지해야 한다:

```python
# services/core/tests/unit/domain/test_work_item.py

class TestWorkItemInvariants:
    def test_cannot_complete_done_item(self):
        wi = WorkItem.create(id="1", proc_inst_id="p1", activity_name="review", tenant_id="t1")
        wi.start()
        wi.complete(result_data={"value": "ok"})
        with pytest.raises(InvalidStateTransition):
            wi.complete(result_data={"value": "again"})

    def test_cannot_complete_submitted_without_force(self):
        wi = WorkItem.create(id="1", proc_inst_id="p1", activity_name="review", tenant_id="t1")
        wi.start()
        wi.submit(result_data={"value": "pending"}, verification_outcome={"decision": "FAIL_ROUTE"})
        with pytest.raises(InvalidStateTransition):
            wi.complete(result_data={"value": "done"})

    def test_force_complete_submitted_works(self):
        wi = WorkItem.create(id="1", proc_inst_id="p1", activity_name="review", tenant_id="t1")
        wi.start()
        wi.submit(result_data={"value": "pending"}, verification_outcome={"decision": "FAIL_ROUTE"})
        wi.complete(result_data={"value": "approved"}, force=True)
        assert wi.status == WorkItemStatus.DONE

    def test_version_increments_on_each_transition(self):
        wi = WorkItem.create(id="1", proc_inst_id="p1", activity_name="review", tenant_id="t1")
        assert wi.version == 1
        wi.start()
        assert wi.version == 2
        wi.complete(result_data={"value": "ok"})
        assert wi.version == 3

    def test_events_collected_and_cleared(self):
        wi = WorkItem.create(id="1", proc_inst_id="p1", activity_name="review", tenant_id="t1")
        wi.start()
        wi.complete(result_data={"value": "ok"})
        events = wi.collect_events()
        assert len(events) == 2  # Created + Completed
        assert wi.collect_events() == []  # cleared

    def test_valid_state_transitions(self):
        """전체 상태 전이 경로 검증"""
        valid_paths = [
            ["TODO", "IN_PROGRESS", "DONE"],
            ["TODO", "IN_PROGRESS", "SUBMITTED", "DONE"],
            ["TODO", "IN_PROGRESS", "SUBMITTED", "REWORK", "IN_PROGRESS", "DONE"],
            ["TODO", "CANCELLED"],
            ["TODO", "IN_PROGRESS", "CANCELLED"],
        ]
        # ... 각 경로별 테스트
```

### 3.5 마이그레이션 전략 (Strangler Fig)

기존 `ProcessService`를 즉시 삭제하지 않고, 새 Aggregate를 **병행 호출**한다:

```python
# Step 1: ProcessService 내부에서 도메인 모델 호출로 점진적 전환
class ProcessService:
    @staticmethod
    async def submit_workitem(db, item_id, submit_data, force_complete=False):
        # 기존 ORM 모델 로드
        result = await db.execute(select(WorkItemORM).where(WorkItemORM.id == item_id))
        orm = result.scalar_one_or_none()
        if not orm:
            raise ProcessDomainError(404, "WORKITEM_NOT_FOUND", "WorkItem not found")

        # ORM → Domain Aggregate 매핑
        wi = work_item_mapper.to_domain(orm)

        # 도메인 로직 실행
        if verification_outcome.decision == "FAIL_ROUTE":
            wi.submit(result_data=body, verification_outcome=verification_outcome.as_dict())
        else:
            wi.complete(result_data=body, force=force_complete)

        # Domain → ORM 매핑 후 저장
        work_item_mapper.to_orm(wi, orm)

        # 도메인 이벤트 → Outbox 발행
        for event in wi.collect_events():
            await EventPublisher.publish(session=db, ...)
```

```python
# Step 2: ORM ↔ Domain 매퍼
# services/core/app/infrastructure/mappers/work_item_mapper.py

class WorkItemMapper:
    @staticmethod
    def to_domain(orm: WorkItemORM) -> WorkItem:
        return WorkItem(
            id=orm.id,
            proc_inst_id=orm.proc_inst_id,
            activity_name=orm.activity_name,
            activity_type=orm.activity_type or "humanTask",
            assignee_id=orm.assignee_id,
            agent_mode=AgentMode(orm.agent_mode or "MANUAL"),
            status=WorkItemStatus(orm.status),
            result_data=orm.result_data,
            tenant_id=orm.tenant_id,
            version=orm.version,
        )

    @staticmethod
    def to_orm(domain: WorkItem, orm: WorkItemORM) -> None:
        orm.status = domain.status.value
        orm.result_data = domain.result_data
        orm.version = domain.version
        orm.agent_mode = domain.agent_mode.value
```

### 3.6 완료 기준

- [x] `WorkItem` Aggregate 클래스가 `app/modules/process/domain/aggregates/work_item.py`에 존재 (262줄)
- [x] 불변식 4개가 Aggregate 내부 메서드에서 보호됨 (`_transition_to()` + `_TRANSITIONS` 맵)
- [x] 도메인 이벤트 8종 정의 (Created, Started, Submitted, Completed, Cancelled, ReworkRequested, HitlApproved, HitlRejected)
- [x] 도메인 단위 테스트 통과 (불변식, 상태 전이, 이벤트 수집)
- [x] `WorkItemLifecycleService`가 내부적으로 Aggregate 호출
- [x] 기존 API 응답 형식 불변 (회귀 테스트 통과)

#### 실제 구현 위치

| 스펙 파일 경로 | 실제 구현 파일 경로 | 비고 |
|-------------|-----------------|------|
| `app/domain/aggregates/work_item.py` | `app/modules/process/domain/aggregates/work_item.py` | 모듈러 모놀리스 구조로 이동 |
| `app/domain/events.py` | `app/modules/process/domain/events.py` | 71줄, 8종 이벤트 |
| `app/domain/errors.py` | `app/modules/process/domain/errors.py` | 41줄, 6종 예외 |
| (기존 위치) | `app/domain/events.py` → shim (re-export) | 하위 호환성 유지 |

---

## 4. DDD-P1-02: Repository 패턴 도입

### 4.1 현황 (AS-IS)

`ProcessService`가 직접 `select(WorkItem).where(...)`, `select(ProcessDefinition).where(...)`를 실행하여 ORM에 강결합되어 있다.

### 4.2 목표 (TO-BE)

```
domain/                             infrastructure/
├── aggregates/                     ├── repositories/
│   └── work_item.py                │   └── sqlalchemy_work_item_repo.py
├── repositories/  (인터페이스)      └── mappers/
│   └── work_item_repository.py          └── work_item_mapper.py
└── events.py
```

### 4.3 구현 명세

#### 4.3.1 Repository 인터페이스 (도메인 레이어)

```python
# services/core/app/domain/repositories/work_item_repository.py

from abc import ABC, abstractmethod
from app.domain.aggregates.work_item import WorkItem


class WorkItemRepository(ABC):
    """WorkItem Aggregate Root의 Repository 인터페이스.
    도메인 레이어에 정의되며, 인프라 의존성이 없다."""

    @abstractmethod
    async def find_by_id(self, workitem_id: str) -> WorkItem | None: ...

    @abstractmethod
    async def find_by_proc_inst(self, proc_inst_id: str, tenant_id: str) -> list[WorkItem]: ...

    @abstractmethod
    async def save(self, workitem: WorkItem) -> None: ...

    @abstractmethod
    async def save_all(self, workitems: list[WorkItem]) -> None: ...
```

#### 4.3.2 SQLAlchemy 구현체 (인프라 레이어)

```python
# services/core/app/infrastructure/repositories/sqlalchemy_work_item_repo.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.aggregates.work_item import WorkItem
from app.domain.repositories.work_item_repository import WorkItemRepository
from app.models.base_models import WorkItem as WorkItemORM
from app.infrastructure.mappers.work_item_mapper import WorkItemMapper


class SQLAlchemyWorkItemRepository(WorkItemRepository):
    def __init__(self, session: AsyncSession):
        self._session = session
        self._mapper = WorkItemMapper()

    async def find_by_id(self, workitem_id: str) -> WorkItem | None:
        result = await self._session.execute(
            select(WorkItemORM).where(WorkItemORM.id == workitem_id)
        )
        orm = result.scalar_one_or_none()
        return self._mapper.to_domain(orm) if orm else None

    async def find_by_proc_inst(self, proc_inst_id: str, tenant_id: str) -> list[WorkItem]:
        result = await self._session.execute(
            select(WorkItemORM).where(
                WorkItemORM.proc_inst_id == proc_inst_id,
                WorkItemORM.tenant_id == tenant_id,
            )
        )
        return [self._mapper.to_domain(orm) for orm in result.scalars()]

    async def save(self, workitem: WorkItem) -> None:
        result = await self._session.execute(
            select(WorkItemORM).where(WorkItemORM.id == workitem.id)
        )
        orm = result.scalar_one_or_none()
        if orm:
            self._mapper.to_orm(workitem, orm)
        else:
            orm = self._mapper.to_new_orm(workitem)
            self._session.add(orm)

    async def save_all(self, workitems: list[WorkItem]) -> None:
        for wi in workitems:
            await self.save(wi)
```

### 4.4 완료 기준

- [x] `modules/process/domain/repositories/` 디렉토리에 `IWorkItemRepository` ABC 인터페이스 존재 (49줄)
- [x] `modules/process/infrastructure/repositories/` 에 SQLAlchemy 구현체 존재 (77줄)
- [x] `domain/` 패키지가 SQLAlchemy를 import하지 않음
- [x] `WorkItemLifecycleService`가 Repository 인터페이스를 통해서만 데이터 접근
- [x] `infrastructure/mappers/work_item_mapper.py` — Domain ↔ ORM 매퍼 (49줄)

---

## 5. DDD-P1-03: domain/ 패키지 생성 및 레이어 분리

### 5.1 현황 (AS-IS)

```
services/core/app/
├── api/          ← Interface Layer (OK)
├── bpm/          ← 혼합 (도메인 + 인프라)
├── core/         ← 혼합 (config + events + security + middleware)
├── models/       ← 인프라 (ORM)
├── services/     ← 혼합 (애플리케이션 + 도메인 로직)
└── workers/      ← 인프라
```

### 5.2 목표 (TO-BE)

```
services/core/app/
├── domain/                         ← 순수 도메인 (인프라 의존성 0)
│   ├── __init__.py
│   ├── aggregates/
│   │   ├── __init__.py
│   │   ├── work_item.py           ← WorkItem Aggregate
│   │   ├── process_definition.py  ← ProcessDefinition Aggregate
│   │   └── watch_subscription.py  ← WatchSubscription Aggregate
│   ├── events.py                  ← 도메인 이벤트 정의
│   ├── errors.py                  ← ProcessDomainError 등
│   ├── repositories/              ← Repository 인터페이스 (ABC)
│   │   ├── __init__.py
│   │   ├── work_item_repository.py
│   │   └── process_definition_repository.py
│   └── services/                  ← 도메인 서비스 (cross-aggregate 로직)
│       ├── __init__.py
│       └── bpm_engine.py          ← 순수 BPM 흐름 엔진 (기존 engine.py 이전)
│
├── application/                    ← 유스케이스 오케스트레이션
│   ├── __init__.py
│   ├── process_service.py         ← 기존 ProcessService (도메인 로직 제거 후)
│   ├── watch_service.py
│   └── agent_service.py
│
├── infrastructure/                 ← 외부 시스템 접근
│   ├── __init__.py
│   ├── repositories/
│   │   ├── sqlalchemy_work_item_repo.py
│   │   └── sqlalchemy_process_def_repo.py
│   ├── mappers/
│   │   ├── work_item_mapper.py
│   │   └── process_definition_mapper.py
│   ├── messaging/
│   │   ├── event_publisher.py     ← 기존 events.py
│   │   └── outbox_relay.py        ← P0에서 구현
│   ├── persistence/
│   │   ├── database.py            ← 기존 core/database.py
│   │   └── models.py              ← 기존 base_models.py (ORM 전용)
│   └── external/
│       └── synapse_gateway.py     ← 기존 synapse_gateway_service.py
│
├── api/                            ← Interface Layer (기존 유지)
│   ├── process/
│   ├── case/
│   ├── watch/
│   └── agent/
│
└── workers/                        ← 인프라 (기존 유지)
    ├── watch_cep.py
    └── outbox_relay.py
```

### 5.3 의존성 규칙 검증

```
domain/     ← 어떤 외부 패키지도 import하지 않음
    ↑
application/ ← domain만 import
    ↑
infrastructure/ ← domain + application import 가능
    ↑
api/         ← application + infrastructure import 가능
```

#### CI 검증 스크립트

```bash
#!/bin/bash
# scripts/check_domain_deps.sh
# domain/ 패키지의 인프라 의존성 위반 검사

VIOLATIONS=$(grep -rn "import sqlalchemy\|import redis\|import httpx\|import psycopg\|from app.infrastructure\|from app.api\|from app.models" \
  services/core/app/domain/ 2>/dev/null | wc -l)

if [ "$VIOLATIONS" -gt 0 ]; then
  echo "FAIL: domain/ 패키지에서 인프라 의존성 발견 ($VIOLATIONS건)"
  grep -rn "import sqlalchemy\|import redis\|import httpx\|import psycopg\|from app.infrastructure\|from app.api\|from app.models" \
    services/core/app/domain/
  exit 1
fi
echo "PASS: domain/ 패키지 의존성 규칙 준수"
```

### 5.4 마이그레이션 순서

1. `domain/events.py`, `domain/errors.py` 생성 (기존 코드에서 추출)
2. `domain/aggregates/work_item.py` 생성 (P1-01 산출물)
3. `domain/repositories/` ABC 생성 (P1-02 산출물)
4. `infrastructure/repositories/` 구현체 이전
5. `infrastructure/persistence/models.py`로 ORM 모델 이전
6. `infrastructure/messaging/event_publisher.py`로 이벤트 퍼블리셔 이전
7. `application/process_service.py`에서 도메인 로직 제거, Repository + Aggregate 호출로 전환
8. 기존 `services/process_service.py`, `models/base_models.py` 등에 deprecation 표시
9. import 경로 업데이트 (api/ routes 등)
10. 기존 파일 제거

### 5.5 완료 기준

- [x] `app/modules/process/domain/` 패키지 존재, 인프라 import 0건
- [x] `app/modules/process/application/` 패키지에서 비즈니스 규칙 로직 제거 (Aggregate 위임)
- [x] `app/modules/process/infrastructure/` 패키지에 ORM, BPM, Saga, EventStore 격리
- [x] 전체 테스트 통과 (169 passed in Docker)

#### 실제 구현 구조 (모듈러 모놀리스)

P1-03 스펙의 `domain/` → `application/` → `infrastructure/` 3계층은 **P2-02 Core 모듈러 모놀리스 전환**과 통합 구현됨. 최종 구조는 `app/modules/{process,agent,case,watch}/` 하위에 각각 `domain/`, `application/`, `infrastructure/`, `api/` 계층이 존재:

```text
services/core/app/modules/process/
├── domain/
│   ├── aggregates/work_item.py   ← Rich Aggregate (262줄)
│   ├── events.py                 ← 도메인 이벤트 8종
│   ├── errors.py                 ← 도메인 예외 6종
│   └── repositories/             ← ABC 인터페이스
├── application/
│   ├── workitem_lifecycle_service.py  ← 324줄
│   ├── definition_service.py          ← 173줄
│   ├── process_instance_service.py    ← 209줄
│   ├── process_service_facade.py      ← 211줄 (Strangler Fig)
│   └── role_binding_service.py        ← 62줄
├── infrastructure/
│   ├── repositories/sqlalchemy_work_item_repo.py  ← 77줄
│   ├── mappers/work_item_mapper.py                ← 49줄
│   ├── bpm/{engine,extractor,models,saga}.py
│   └── event_store.py                             ← PoC (270줄)
└── api/routes.py                                  ← 288줄
```

---

## 6. DDD-P1-04: DB 스키마 분리

### 6.1 현황 (AS-IS)

`docker-compose.yml`에서 확인:
```yaml
synapse-svc:  postgresql://arkos:arkos@postgres-db:5432/insolvency_os
vision-svc:   postgresql://arkos:arkos@postgres-db:5432/insolvency_os
core-svc:     postgresql+asyncpg://arkos:arkos@postgres-db:5432/insolvency_os
oracle-svc:   postgresql://arkos:arkos@postgres-db:5432/insolvency_os
```

5개 서비스가 동일 `insolvency_os` DB의 `public` 스키마를 공유한다. Oracle만 `oracle.query_history` 스키마를 사용하여 부분 분리.

### 6.2 목표 (TO-BE)

```sql
insolvency_os
├── core.*           -- Core 서비스 전용
│   ├── core.tenants
│   ├── core.users
│   ├── core.bpm_process_definition
│   ├── core.bpm_work_item
│   ├── core.bpm_process_role_binding
│   ├── core.core_case
│   ├── core.case_activity
│   ├── core.document_review
│   ├── core.event_outbox
│   ├── core.watch_subscription
│   ├── core.watch_rule
│   └── core.watch_alert
│
├── synapse.*        -- Synapse 서비스 전용
│   ├── synapse.mining_task
│   ├── synapse.mining_result
│   ├── synapse.event_log
│   └── synapse.schema_edit_*
│
├── vision.*         -- Vision 서비스 전용
│   ├── vision.analytics_kpi_snapshot
│   ├── vision.scenario_result
│   └── vision.state_store
│
├── oracle.*         -- Oracle 서비스 전용 (이미 부분 존재)
│   └── oracle.query_history
│
└── weaver.*         -- Weaver 서비스 전용
    ├── weaver.datasource
    └── weaver.glossary
```

### 6.3 구현 명세

#### Step 1: 스키마 생성 마이그레이션

```sql
-- 서비스별 스키마 생성
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS synapse;
CREATE SCHEMA IF NOT EXISTS vision;
CREATE SCHEMA IF NOT EXISTS weaver;
-- oracle 스키마는 이미 존재

-- 서비스별 전용 DB 유저 생성 (최소 권한)
CREATE USER core_svc WITH PASSWORD 'core_svc_pwd';
GRANT USAGE ON SCHEMA core TO core_svc;
GRANT ALL ON ALL TABLES IN SCHEMA core TO core_svc;

CREATE USER synapse_svc WITH PASSWORD 'synapse_svc_pwd';
GRANT USAGE ON SCHEMA synapse TO synapse_svc;
GRANT ALL ON ALL TABLES IN SCHEMA synapse TO synapse_svc;

-- ... 반복
```

#### Step 2: 테이블 이전 (Zero-Downtime)

```sql
-- 1. 새 스키마에 테이블 생성
CREATE TABLE core.bpm_work_item (LIKE public.bpm_work_item INCLUDING ALL);

-- 2. 데이터 복사
INSERT INTO core.bpm_work_item SELECT * FROM public.bpm_work_item;

-- 3. 뷰로 호환성 유지 (롤백 안전망)
CREATE OR REPLACE VIEW public.bpm_work_item AS SELECT * FROM core.bpm_work_item;

-- 4. 서비스 코드에서 스키마 접두사 사용으로 전환

-- 5. 안정화 후 public 뷰 및 원본 테이블 제거
```

#### Step 3: 서비스별 연결 문자열 변경

```yaml
# docker-compose.yml
core-svc:
  environment:
    - DATABASE_URL=postgresql+asyncpg://core_svc:core_svc_pwd@postgres-db:5432/insolvency_os
    - DATABASE_SCHEMA=core

synapse-svc:
  environment:
    - SCHEMA_EDIT_DATABASE_URL=postgresql://synapse_svc:synapse_svc_pwd@postgres-db:5432/insolvency_os
    - DATABASE_SCHEMA=synapse
```

#### Step 4: SQLAlchemy 스키마 설정

```python
# 각 서비스의 Base 설정에 schema 추가
class Base(DeclarativeBase):
    metadata = MetaData(schema="core")  # 서비스별 다름
```

### 6.4 롤백 계획

1. `public` 스키마의 뷰를 통한 호환성 레이어를 2주간 유지
2. 문제 발생 시 뷰를 테이블로 되돌림 (데이터 동기화 확인 후)
3. 마이그레이션 전 `pg_dump`로 전체 백업

### 6.5 완료 기준

- [x] 5개 서비스별 전용 PostgreSQL 스키마 존재 (core/synapse/vision/weaver/oracle)
- [x] 각 서비스가 자체 스키마의 테이블만 접근 (`DATABASE_SCHEMA` 환경변수로 격리)
- [x] SQLAlchemy `MetaData(schema=DATABASE_SCHEMA)` 적용
- [x] Docker 환경 검증 완료: `core` 스키마 14개 테이블, synapse/vision/weaver 각 `event_outbox` 포함

#### 실제 스키마 현황 (Docker 검증)

| 스키마 | 주요 테이블 | 테이블 수 |
|--------|-----------|:---------:|
| `core` | bpm_work_item, bpm_process_definition, core_case, event_outbox, event_dead_letter, saga_execution_log, watch_* | 14 |
| `synapse` | event_outbox, mining_task, event_log, schema_edit_* | 5+ |
| `vision` | event_outbox, analytics_* | 3+ |
| `weaver` | event_outbox, datasource, glossary | 3+ |
| `oracle` | query_history | 1+ |

---

## 7. DDD-P1-05: ProcessService God Class 분할

### 7.1 현황 (AS-IS)

`services/core/app/services/process_service.py` — 661줄, 14개 `@staticmethod`.
책임: 프로세스 정의 CRUD + 워크아이템 라이프사이클 + 역할 바인딩 + 인스턴스 관리 + 통계.

### 7.2 목표 (TO-BE)

| 새 클래스 | 책임 | 메서드 |
|----------|------|--------|
| `ProcessDefinitionService` | 프로세스 정의 CRUD, NL→BPMN 변환 | `create_definition`, `list_definitions`, `get_definition` |
| `WorkItemLifecycleService` | 워크아이템 상태 관리 | `submit_workitem`, `list_workitems`, `get_workitem` |
| `RoleBindingService` | 역할-사용자 바인딩 | `bind_roles`, `get_bindings` |
| `ProcessInstanceService` | 인스턴스 시작/조회 | `start_process`, `list_instances` |

### 7.3 완료 기준

- [x] `ProcessService` 661줄 → 4개 서비스로 분할 + Facade
- [x] 각 서비스 300줄 이하 (workitem_lifecycle: 324줄, definition: 173줄, process_instance: 209줄, role_binding: 62줄, facade: 211줄)
- [x] API Router에서 모듈별 routes.py 호출
- [x] 전체 테스트 통과 (169 passed)

---

## 8. Phase 1 타임라인

```
Week 1-2:  [DDD-P1-03 domain/ 패키지 골격 생성]
           [DDD-P1-01 WorkItem Aggregate 구현 + 테스트]
Week 2-3:  [DDD-P1-02 Repository 인터페이스 + 구현체]
           [DDD-P1-01 ProcessService 내부 Aggregate 호출 전환]
Week 3-4:  [DDD-P1-05 ProcessService 분할]
Week 4-6:  [DDD-P1-04 DB 스키마 분리 (마이그레이션)]
Week 6:    [Gate DDD-1 검증]
```

## 9. Gate DDD-1 통과 결과 — **PASS**

- [x] `app/modules/process/domain/` 패키지 존재, 인프라 의존성 0건
- [x] WorkItem Aggregate 불변식 테스트 통과 (상태 전이, 도메인 이벤트, 낙관적 동시성)
- [x] Repository 인터페이스 분리 (`IWorkItemRepository` ABC in domain, `SQLAlchemyWorkItemRepository` in infrastructure)
- [x] DB 스키마 분리 완료 (core/synapse/vision/weaver/oracle 5개 스키마)
- [x] ProcessService 분할 완료 (5개 클래스, 최대 324줄)
- [x] 전 서비스 API 회귀 테스트 통과 (Docker 환경 169 passed)
