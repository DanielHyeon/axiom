# BusinessOS Kinetic Layer 통합 설계서

> **문서 버전**: 2.0.0 (최종)
> **작성일**: 2026-03-20
> **최종 수정**: 2026-03-20 (Phase 1+2+3 전체 구현 + 미반영 8건 해소 + 최종 종합 리뷰 APPROVED)
> **근거**: BusinessOS 3개 프로젝트 분석 + 팔란티어 온톨로지 구현 방법.pdf + KAIR 갭 분석
> **목적**: Axiom 온톨로지를 "읽기 전용 지식 그래프"에서 "실행 가능한 디지털 트윈"으로 진화시키기 위한 Kinetic Layer 도입 상세 설계

---

## 목차

1. [Executive Summary](#1-executive-summary)
2. [현재 상태 분석 (As-Is)](#2-현재-상태-분석-as-is)
3. [목표 아키텍처 (To-Be): 3-Layer 온톨로지](#3-목표-아키텍처-to-be-3-layer-온톨로지)
4. [설계 1: GWT 룰 엔진 (Kinetic Core)](#4-설계-1-gwt-룰-엔진-kinetic-core)
5. [설계 2: Graph Projector (이벤트→그래프 동기화)](#5-설계-2-graph-projector-이벤트그래프-동기화)
6. [설계 3: Event Fork 기반 What-If 브랜칭](#6-설계-3-event-fork-기반-what-if-브랜칭)
7. [설계 4: 문서→온톨로지 자동 추출 파이프라인](#7-설계-4-문서온톨로지-자동-추출-파이프라인)
8. [설계 5: Policy Orchestrator (사가/정책 자동 실행)](#8-설계-5-policy-orchestrator-사가정책-자동-실행)
9. [설계 6: 프론트엔드 (도메인 모델러 + What-If 위자드 + 워크플로 에디터)](#9-설계-6-프론트엔드)
10. [Neo4j 스키마 확장](#10-neo4j-스키마-확장)
11. [PostgreSQL 스키마 확장](#11-postgresql-스키마-확장)
12. [API 명세](#12-api-명세)
13. [Phase별 구현 계획 (코드 레벨)](#13-phase별-구현-계획-코드-레벨)
14. [위험 요소 및 완화 전략](#14-위험-요소-및-완화-전략)

---

## 1. Executive Summary

### 1.1 왜 Kinetic Layer가 필요한가

| 현재 (As-Is) | 목표 (To-Be) |
|-------------|-------------|
| 온톨로지가 읽기 전용 "지식 그래프" | 온톨로지가 실행 가능한 "디지털 트윈" |
| 비즈니스 로직이 Python 코드에 하드코딩 | GWT DSL로 선언적 정의, 런타임 해석 |
| 이벤트가 발생해도 온톨로지 그래프 변화 없음 | Graph Projector가 이벤트→그래프 실시간 동기화 |
| What-If이 인메모리 DAG 계산만 수행 | Event Fork로 결정적 시뮬레이션 + 시나리오 저장 |
| 문서에서 온톨로지 수동 구성 | LLM이 문서→DDD 개념→온톨로지 자동 추출 |
| 서비스 간 이벤트 반응형 오케스트레이션 없음 | Policy Orchestrator가 자동 커맨드 발행 |

### 1.2 BusinessOS에서 가져온 핵심 개념

```
팔란티어 온톨로지 = Semantic + Kinetic + Dynamic

BusinessOS 핵심 공식:
  어그리거트 = 디지털 트윈 오브젝트(온톨로지 노드)
  노드들 사이의 링크 + 이벤트 흐름 + GWT 룰을
  3 레이어(시맨틱/키네틱/다이나믹)로 명확히 쪼개서 설계

Axiom 적용:
  Semantic = 기존 5계층 온톨로지 (KPI/Driver/Measure/Process/Resource)
  Kinetic  = 신규 ActionType + GWT Rule + Policy (이 문서의 핵심)
  Dynamic  = Vision What-If + Event Fork + Simulation Branch
```

### 1.3 영향 범위

| 서비스 | 변경 유형 | 영향도 |
|--------|---------|-------|
| **Synapse** | Neo4j 스키마 확장 + GraphProjector 워커 + GWT 서비스 | 높음 |
| **Core** | EventOutbox 확장 (simulation_id) + PolicyExecutor 워커 | 중간 |
| **Vision** | Event Fork 모드 추가 (기존 DAG 모드 유지) | 중간 |
| **Weaver** | 문서 업로드 + 텍스트 추출 파이프라인 | 중간 |
| **Canvas** | 도메인 모델러 + What-If 위자드 + 워크플로 에디터 | 높음 |

---

## 2. 현재 상태 분석 (As-Is)

### 2.1 Synapse 온톨로지 — Semantic Layer만 존재

```
현재 Neo4j 노드:
  (:KPI), (:Driver), (:Measure), (:Process), (:Resource)
  (:OntologyBehavior:Model)  ← ML 모델 메타데이터 (Kinetic에 가깝지만 룰 실행 없음)
  (:Table), (:Column), (:Query)
  (:OntologySnapshot)

현재 관계:
  DERIVED_FROM, OBSERVED_IN, PRECEDES, SUPPORTS, USES,
  CAUSES, INFLUENCES, RELATED_TO,
  READS_FIELD, PREDICTS_FIELD, HAS_BEHAVIOR,
  DEFINES, MAPS_TO, ...
```

**문제점**:
- 온톨로지가 "무슨 객체가 존재하는가"만 정의 (Semantic)
- "무슨 액션이 일어나며, 무엇을 바꾸나" (Kinetic)가 없음
- "시뮬레이션/의사결정" (Dynamic)이 온톨로지와 분리됨

### 2.2 Core 이벤트 — 그래프와 단절

```
현재 이벤트 흐름:
  WorkItemCompleted → EventOutbox → Redis Relay → axiom:core:events

  수신 측: CaseEventConsumer (Vision)만 Redis에서 읽음
  결과: Case 테이블 업데이트만 수행

  ❌ Neo4j 온톨로지 그래프에는 아무런 변화 없음
```

### 2.3 Vision What-If — 인메모리 계산만

```
현재 알고리즘:
  사용자 intervention → BehaviorModel 그래프 순회 → FallbackPredictor
  결과: 인메모리 SimulationResult (traces, timeline, deltas)

  ❌ 이벤트 로그 기반이 아님 → 비결정적 (모델 의존)
  ❌ 시나리오 저장 = 결과만 저장 (재현 불가)
  ❌ 부분 시뮬레이션 불가 (전체 DAG 순회 필수)
```

---

## 3. 목표 아키텍처 (To-Be): 3-Layer 온톨로지

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DYNAMIC LAYER (Vision 서비스)                     │
│                                                                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ What-If DAG     │  │ Event Fork       │  │ Scenario         │  │
│  │ (기존 유지)      │  │ (신규: 브랜칭)    │  │ Comparator       │  │
│  │                 │  │                  │  │ (신규: 비교 UI)   │  │
│  └─────────────────┘  └──────────────────┘  └──────────────────┘  │
│           ↑                    ↑                     ↑             │
│           │            Simulation Branch              │             │
│           │            (이벤트 포크)                    │             │
├───────────┼────────────────────┼──────────────────────┼─────────────┤
│                    KINETIC LAYER (Synapse 확장)                      │
│                                                                     │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ ActionType      │  │ GWT Rule Engine  │  │ Policy           │  │
│  │ (Neo4j 노드)    │  │ (Given-When-Then)│  │ Orchestrator     │  │
│  │                 │  │                  │  │ (Core 워커)       │  │
│  └────────┬────────┘  └────────┬─────────┘  └────────┬─────────┘  │
│           │                    │                      │             │
│  ┌────────┴────────────────────┴──────────────────────┴─────────┐  │
│  │              Graph Projector (이벤트→그래프 동기화)              │  │
│  │    Redis Stream Consumer → Cypher MERGE → Neo4j 업데이트       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                    SEMANTIC LAYER (Synapse 기존)                     │
│                                                                     │
│  ┌──────┐  ┌────────┐  ┌─────────┐  ┌─────────┐  ┌──────────┐   │
│  │ KPI  │  │ Driver │  │ Measure │  │ Process │  │ Resource │   │
│  └──┬───┘  └───┬────┘  └────┬────┘  └────┬────┘  └─────┬────┘   │
│     └──────────┴────────────┴─────────────┴─────────────┘         │
│               기존 5계층 온톨로지 (변경 없음)                         │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ BehaviorModel (:OntologyBehavior:Model)                    │    │
│  │ READS_FIELD / PREDICTS_FIELD (기존 유지)                     │    │
│  └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. 설계 1: GWT 룰 엔진 (Kinetic Core)

### 4.1 개념

GWT(Given-When-Then) 룰 엔진은 BusinessOS의 핵심 개념:
- **Given**: 온톨로지 상태 + 관련 링크 조건 (전제 조건)
- **When**: 인입 이벤트/커맨드 (트리거)
- **Then**: 상태 변경 + 새로운 이벤트 발행 (결과)

팔란티어의 Kinetic Layer에서 Action/Function에 해당하며,
코드 변경 없이 비즈니스 로직을 선언적으로 정의/변경 가능.

### 4.2 Neo4j 스키마: ActionType 노드

```cypher
-- ActionType: GWT 룰을 저장하는 Kinetic Layer 노드
CREATE (a:ActionType {
  id: "action_approve_order",
  case_id: "case-001",
  tenant_id: "tenant-001",

  -- 메타데이터
  name: "주문 승인",
  description: "결제 확인 후 주문을 자동 승인하는 액션",
  layer: "kinetic",                    -- 3-Layer 구분
  enabled: true,                       -- 활성화 여부
  priority: 100,                       -- 룰 우선순위 (높을수록 먼저 실행)
  version: 1,                          -- 룰 버전

  -- GWT 정의 (JSON 문자열)
  given_conditions: '[
    {"type": "state", "node_layer": "process", "field": "status", "op": "==", "value": "PENDING"},
    {"type": "relation", "source_layer": "measure", "rel_type": "OBSERVED_IN", "target_layer": "process", "field": "payment_status", "op": "==", "value": "CONFIRMED"}
  ]',

  when_event: "ApproveOrderCommand",   -- 트리거 이벤트 타입

  then_actions: '[
    {"op": "SET", "target_node": "$trigger.source_node_id", "field": "status", "value": "APPROVED"},
    {"op": "EMIT", "event_type": "OrderApproved", "payload": {"order_id": "$trigger.aggregate_id"}},
    {"op": "EXECUTE", "action_id": "action_notify_customer", "params": {"channel": "email"}}
  ]',

  -- 감사 추적
  created_at: datetime(),
  updated_at: datetime(),
  created_by: "admin@local.axiom"
})
```

### 4.3 ActionType과 온톨로지 노드 연결

```cypher
-- ActionType이 읽는 노드 (Given 조건의 소스)
(process:Process)-[:TRIGGERS]->(action:ActionType)

-- ActionType이 영향을 주는 노드 (Then 결과의 타겟)
(action:ActionType)-[:MODIFIES]->(process:Process)

-- ActionType 간 체이닝 (EXECUTE로 연결)
(action1:ActionType)-[:CHAINS_TO]->(action2:ActionType)

-- ActionType과 BehaviorModel 연결
(action:ActionType)-[:USES_MODEL]->(model:OntologyBehavior:Model)
```

### 4.4 전제조건: Neo4jClient 확장

기존 `Neo4jClient`는 `session()` 메서드만 제공한다.
GWT Engine, Graph Projector 등이 공통으로 사용할 편의 메서드를 추가한다.

**파일**: `services/synapse/app/core/neo4j_client.py` (기존 파일 확장)

```python
from neo4j import AsyncGraphDatabase, AsyncDriver
import structlog
from app.core.config import settings

logger = structlog.get_logger()

class Neo4jClient:
    def __init__(self):
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )

    async def close(self):
        await self.driver.close()

    def session(self):
        return self.driver.session()

    # ── 신규: 편의 메서드 (GWT/Projector용) ──

    async def execute_read(self, query: str, params: dict | None = None, timeout: float = 10.0) -> list[dict]:
        """읽기 트랜잭션 실행 — ontology_service._run_neo4j_query 패턴 준수"""
        async with self.driver.session() as session:
            result = await session.run(query, **(params or {}))
            return [dict(record) async for record in result]

    async def execute_write(self, query: str, params: dict | None = None) -> list[dict]:
        """쓰기 트랜잭션 실행 — execute_write 트랜잭션 함수 패턴"""
        async with self.driver.session() as session:
            async def _tx_work(tx):
                result = await tx.run(query, **(params or {}))
                return [dict(record) async for record in result]
            return await session.execute_write(_tx_work)

neo4j_client = Neo4jClient()
```

### 4.5 전제조건: Synapse EventPublisher Async 래퍼

기존 Synapse `EventPublisher`는 동기(psycopg2) 기반이다.
GWT Consumer 워커(async 컨텍스트)에서 사용하기 위한 래퍼를 추가한다.

**파일**: `services/synapse/app/events/outbox.py` (기존 파일 끝에 추가)

```python
import asyncio

class AsyncEventPublisher:
    """GWT Consumer 등 async 워커에서 동기 EventPublisher를 안전하게 호출하는 래퍼.

    asyncio.to_thread()로 psycopg2 블로킹 호출을 별도 스레드에서 실행.
    트랜잭션 보장: 독립 커넥션 모드 (conn=None) 사용 → 즉시 커밋.
    """

    @staticmethod
    async def publish(
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        payload: dict[str, Any],
        tenant_id: str = "",
    ) -> str:
        return await asyncio.to_thread(
            EventPublisher.publish,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            payload=payload,
            tenant_id=tenant_id,
            conn=None,
        )

async_event_publisher = AsyncEventPublisher()
```

> **Core 서비스의 EventPublisher** (`services/core/app/core/events.py`)는 async이며
> `session: AsyncSession`을 첫 인자로 요구한다. PolicyExecutor(Core 워커)는
> 자체 DB 세션을 생성하여 `EventPublisher.publish(session, ...)` 시그니처로 호출한다.

### 4.6 GWT Rule Engine 서비스 (Python)

**파일**: `services/synapse/app/services/gwt_engine.py`

```python
"""
GWT(Given-When-Then) 룰 엔진

BusinessOS의 Generic Interpreter 패턴을 Axiom에 적용:
- Given: 온톨로지 상태 조건 평가 (Cypher 패턴 매칭)
- When: 이벤트 타입 매칭
- Then: 상태 변경 + 이벤트 발행 + 액션 체이닝

⚠️ 보안 원칙 (리뷰 반영):
- Cypher 쿼리에 사용자 입력을 f-string으로 직접 삽입 금지
- 모든 라벨/필드명은 ALLOWED_LABELS, _ALNUM_UNDERSCORE 화이트리스트로 검증
- expression 평가는 ast.parse + safe_eval (eval() 사용 금지)
- ontology_service.py의 기존 보안 패턴을 그대로 준수
"""
from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from typing import Any
import json
import logging
import re

logger = logging.getLogger(__name__)

# ── 보안: ontology_service.py와 동일한 화이트리스트 ──
_ALNUM_UNDERSCORE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

ALLOWED_LABELS = {"Kpi", "Measure", "Process", "Resource", "Driver", "Entity",
                  "ActionType", "Policy"}

ALLOWED_REL_TYPES_KINETIC = {
    "TRIGGERS", "MODIFIES", "CHAINS_TO", "USES_MODEL",
    "EMITS_TO", "DISPATCHES_TO",
    # 기존 온톨로지 관계도 허용
    "DERIVED_FROM", "OBSERVED_IN", "PRECEDES", "SUPPORTS", "USES",
    "CAUSES", "INFLUENCES", "RELATED_TO",
    "READS_FIELD", "PREDICTS_FIELD", "HAS_BEHAVIOR", "DEFINES",
}

ALLOWED_UPDATE_FIELDS = {
    "name", "description", "enabled", "priority",
    "given_conditions", "when_event", "then_actions",
}


@dataclass(frozen=True)
class GWTCondition:
    """Given 조건 하나를 표현"""
    type: str                    # "state" | "relation" | "expression"
    node_layer: str = ""         # 대상 노드의 계층 (kpi, measure, process, resource)
    field: str = ""              # 비교할 필드명
    op: str = "=="               # ==, !=, >, <, >=, <=, in, not_in, contains
    value: Any = None            # 비교 대상 값
    # relation 타입 전용
    source_layer: str = ""
    rel_type: str = ""
    target_layer: str = ""

    def validate(self) -> None:
        """⚠️ Cypher 인젝션 방지 — 라벨/필드/관계 타입 화이트리스트 검증"""
        if self.node_layer and self.node_layer.capitalize() not in ALLOWED_LABELS:
            raise ValueError(f"허용되지 않는 node_layer: {self.node_layer}")
        if self.source_layer and self.source_layer.capitalize() not in ALLOWED_LABELS:
            raise ValueError(f"허용되지 않는 source_layer: {self.source_layer}")
        if self.target_layer and self.target_layer.capitalize() not in ALLOWED_LABELS:
            raise ValueError(f"허용되지 않는 target_layer: {self.target_layer}")
        if self.field and not _ALNUM_UNDERSCORE.match(self.field):
            raise ValueError(f"허용되지 않는 field 이름: {self.field}")
        if self.rel_type and self.rel_type not in ALLOWED_REL_TYPES_KINETIC:
            raise ValueError(f"허용되지 않는 rel_type: {self.rel_type}")


@dataclass(frozen=True)
class GWTAction:
    """Then 액션 하나를 표현"""
    op: str                      # "SET" | "EMIT" | "EXECUTE" | "CREATE_RELATION" | "DELETE_RELATION"
    target_node: str = ""        # 대상 노드 ID 또는 "$trigger.source_node_id"
    field: str = ""              # SET: 변경할 필드명
    value: Any = None            # SET: 새 값
    event_type: str = ""         # EMIT: 발행할 이벤트 타입
    payload: dict = field(default_factory=dict)  # EMIT: 이벤트 페이로드
    action_id: str = ""          # EXECUTE: 호출할 ActionType ID
    params: dict = field(default_factory=dict)   # EXECUTE: 파라미터

    def validate(self) -> None:
        """⚠️ field명 인젝션 방지"""
        if self.field and not _ALNUM_UNDERSCORE.match(self.field):
            raise ValueError(f"허용되지 않는 field 이름: {self.field}")


@dataclass
class GWTRule:
    """GWT 룰 전체 정의"""
    id: str
    name: str
    case_id: str
    tenant_id: str
    given: list[GWTCondition]
    when_event: str
    then: list[GWTAction]
    enabled: bool = True
    priority: int = 100
    version: int = 1


@dataclass
class GWTEvalContext:
    """룰 평가 시 사용되는 컨텍스트"""
    event_type: str
    aggregate_id: str
    source_node_id: str
    payload: dict
    case_id: str
    tenant_id: str
    # 온톨로지 상태 스냅샷 (Cypher 결과)
    node_states: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 관계 상태
    relation_states: dict[str, list[dict]] = field(default_factory=dict)


@dataclass
class GWTExecutionResult:
    """룰 실행 결과"""
    rule_id: str
    rule_name: str
    matched: bool
    state_changes: list[dict] = field(default_factory=list)
    emitted_events: list[dict] = field(default_factory=list)
    chained_actions: list[str] = field(default_factory=list)
    error: str | None = None


class GWTEngine:
    """
    GWT 룰 엔진 — BusinessOS의 Generic Interpreter를 Axiom에 구현

    동작 플로우:
    1. Redis Stream에서 이벤트 수신
    2. Neo4j에서 해당 case_id의 활성 ActionType 노드 조회
    3. when_event가 매칭되는 룰 필터링
    4. 각 룰의 given 조건을 Cypher로 평가
    5. 매칭된 룰의 then 액션 실행 (priority 순)
    6. 결과 이벤트를 EventOutbox에 기록
    """

    MAX_CHAIN_DEPTH = 10  # 무한 루프 방지

    def __init__(self, neo4j_client, async_publisher, dry_run: bool = False):
        """
        dry_run=True: 시뮬레이션 모드 — Neo4j 쓰기/이벤트 발행 없이 결과만 계산
        ⚠️ Major #5 수정: Event Fork Engine에서 호출 시 dry_run=True로 생성
        """
        """
        neo4j_client: Neo4jClient (execute_read/execute_write 확장 버전)
        async_publisher: AsyncEventPublisher (synapse outbox async 래퍼)
        """
        self._neo4j = neo4j_client
        self._publisher = async_publisher  # AsyncEventPublisher.publish()
        self._dry_run = dry_run            # True이면 Neo4j 쓰기/이벤트 발행 건너뜀

    async def load_rules(self, case_id: str, tenant_id: str, event_type: str) -> list[GWTRule]:
        """Neo4j에서 해당 case+tenant의 활성 ActionType 중 event_type 매칭 룰 조회

        ⚠️ Major #7 수정: tenant_id 필터 추가 (크로스 테넌트 룰 실행 방지)
        """
        query = """
        MATCH (a:ActionType {case_id: $case_id, tenant_id: $tenant_id, enabled: true})
        WHERE a.when_event = $event_type
        RETURN a
        ORDER BY a.priority DESC
        """
        records = await self._neo4j.execute_read(query, {
            "case_id": case_id,
            "tenant_id": tenant_id,
            "event_type": event_type,
        })
        return [self._parse_rule(r["a"]) for r in records]

    async def evaluate_given(
        self, rule: GWTRule, ctx: GWTEvalContext
    ) -> bool:
        """Given 조건 전체를 평가 (AND 결합)"""
        for cond in rule.given:
            if cond.type == "state":
                if not await self._eval_state_condition(cond, ctx):
                    return False
            elif cond.type == "relation":
                if not await self._eval_relation_condition(cond, ctx):
                    return False
            elif cond.type == "expression":
                if not self._eval_expression(cond, ctx):
                    return False
        return True

    async def execute_then(
        self, rule: GWTRule, ctx: GWTEvalContext, depth: int = 0
    ) -> GWTExecutionResult:
        """Then 액션 시퀀스 실행"""
        result = GWTExecutionResult(
            rule_id=rule.id,
            rule_name=rule.name,
            matched=True,
        )

        if depth >= self.MAX_CHAIN_DEPTH:
            result.error = f"최대 체이닝 깊이({self.MAX_CHAIN_DEPTH}) 초과"
            logger.warning(result.error)
            return result

        for action in rule.then:
            try:
                if action.op == "SET":
                    if self._dry_run:
                        # ⚠️ Major #5: dry-run에서는 Neo4j 쓰기 없이 결과만 계산
                        change = {
                            "node_id": self._resolve_ref(action.target_node, ctx),
                            "field": action.field,
                            "old_value": ctx.node_states.get(
                                self._resolve_ref(action.target_node, ctx), {}
                            ).get(action.field),
                            "new_value": action.value,
                        }
                    else:
                        change = await self._execute_set(action, ctx)
                    result.state_changes.append(change)
                elif action.op == "EMIT":
                    event = self._build_event(action, ctx)
                    result.emitted_events.append(event)
                elif action.op == "EXECUTE":
                    result.chained_actions.append(action.action_id)
                elif action.op == "CREATE_RELATION":
                    if not self._dry_run:
                        await self._execute_create_relation(action, ctx)
                elif action.op == "DELETE_RELATION":
                    if not self._dry_run:
                        await self._execute_delete_relation(action, ctx)
            except Exception as e:
                result.error = f"액션 {action.op} 실행 실패: {e}"
                logger.error(result.error, exc_info=True)
                break

        return result

    async def handle_event(
        self, event_type: str, aggregate_id: str,
        payload: dict, case_id: str, tenant_id: str
    ) -> list[GWTExecutionResult]:
        """
        이벤트 하나를 처리하는 메인 진입점

        1. 매칭 룰 로드
        2. 컨텍스트 구성 (관련 노드 상태 조회)
        3. Given 평가 → When 매칭 → Then 실행
        """
        rules = await self.load_rules(case_id, tenant_id, event_type)
        if not rules:
            return []

        ctx = GWTEvalContext(
            event_type=event_type,
            aggregate_id=aggregate_id,
            source_node_id=payload.get("source_node_id", ""),
            payload=payload,
            case_id=case_id,
            tenant_id=tenant_id,
        )

        # 관련 노드 상태를 Neo4j에서 한 번에 조회
        await self._load_context_states(ctx, rules)

        results = []
        for rule in rules:
            # 모든 조건의 화이트리스트 검증 (Cypher 인젝션 방지)
            try:
                for cond in rule.given:
                    cond.validate()
                for action in rule.then:
                    action.validate()
            except ValueError as e:
                logger.error("GWT 룰 검증 실패: rule=%s, error=%s", rule.id, e)
                continue

            if await self.evaluate_given(rule, ctx):
                exec_result = await self.execute_then(rule, ctx)
                results.append(exec_result)

                # 발행된 이벤트를 Synapse EventOutbox에 저장
                # ⚠️ Critical #4: AsyncEventPublisher 시그니처 사용
                # ⚠️ Major #5: dry_run이면 발행 건너뜀
                if self._dry_run:
                    continue
                for event in exec_result.emitted_events:
                    await self._publisher.publish(
                        event_type=event["event_type"],
                        aggregate_type="ActionType",
                        aggregate_id=rule.id,
                        payload=event["payload"],
                        tenant_id=tenant_id,
                    )

        return results

    # --- 내부 메서드 ---

    async def _eval_state_condition(
        self, cond: GWTCondition, ctx: GWTEvalContext
    ) -> bool:
        """노드 상태 조건 평가 — Cypher 조회 결과를 비교

        ⚠️ Critical #1 수정: f-string Cypher 인젝션 방지
        - cond.validate()가 이미 호출되어 node_layer, field가 화이트리스트 검증됨
        - 라벨은 ALLOWED_LABELS, 필드명은 _ALNUM_UNDERSCORE로 검증 완료
        - 파라미터화된 Cypher 사용 ($case_id, $node_id)
        """
        label = cond.node_layer.capitalize()  # validate()로 ALLOWED_LABELS 검증됨
        field_name = cond.field               # validate()로 _ALNUM_UNDERSCORE 검증됨
        # 안전하게 검증된 값만 Cypher 문자열에 삽입
        query = f"""
        MATCH (n:{label} {{case_id: $case_id}})
        WHERE n.node_id = $node_id
        RETURN n.{field_name} AS val
        """
        node_id = self._resolve_ref(
            cond.value if isinstance(cond.value, str) and cond.value.startswith("$") else "",
            ctx,
        ) or ctx.source_node_id
        records = await self._neo4j.execute_read(query, {
            "case_id": ctx.case_id,
            "node_id": node_id,
        })
        if not records:
            return False
        actual = records[0]["val"]
        return self._compare(actual, cond.op, cond.value)

    async def _eval_relation_condition(
        self, cond: GWTCondition, ctx: GWTEvalContext
    ) -> bool:
        """관계 조건 평가 — 관계의 존재 여부 + 속성 비교

        ⚠️ Critical #1 수정: 라벨/관계/필드 모두 validate()로 화이트리스트 검증됨
        """
        src_label = cond.source_layer.capitalize()  # ALLOWED_LABELS 검증됨
        tgt_label = cond.target_layer.capitalize()  # ALLOWED_LABELS 검증됨
        rel_type = cond.rel_type                     # ALLOWED_REL_TYPES_KINETIC 검증됨
        field_name = cond.field                      # _ALNUM_UNDERSCORE 검증됨
        query = f"""
        MATCH (a:{src_label} {{case_id: $case_id}})
              -[r:{rel_type}]->
              (b:{tgt_label} {{case_id: $case_id}})
        WHERE a.node_id = $source_id
        RETURN b.{field_name} AS val
        """
        records = await self._neo4j.execute_read(query, {
            "case_id": ctx.case_id,
            "source_id": ctx.source_node_id,
        })
        if not records:
            return False
        actual = records[0]["val"]
        return self._compare(actual, cond.op, cond.value)

    def _eval_expression(self, cond: GWTCondition, ctx: GWTEvalContext) -> bool:
        """⚠️ Critical #2 수정: eval() 완전 제거 → AST 기반 안전한 표현식 평가기

        허용하는 노드 타입만 화이트리스트로 처리:
        - Constant(숫자, 문자열, bool, None)
        - Name(변수 참조: state, payload, trigger)
        - Compare(==, !=, >, <, >=, <=, in, not in)
        - BoolOp(and, or)
        - UnaryOp(not)
        - Attribute(state.xxx)
        - Subscript(state["xxx"])

        ❌ 금지: Call, Import, Lambda, FunctionDef, ClassDef, ...
        """
        variables = {
            "state": ctx.node_states,
            "payload": ctx.payload,
            "trigger": {
                "event_type": ctx.event_type,
                "aggregate_id": ctx.aggregate_id,
                "source_node_id": ctx.source_node_id,
            },
        }
        try:
            return bool(safe_eval(cond.value, variables))
        except Exception as e:
            logger.warning("GWT expression 평가 실패: %s → %s", cond.value, e)
            return False

    async def _execute_set(self, action: GWTAction, ctx: GWTEvalContext) -> dict:
        """노드 상태 변경 — Neo4j SET

        ⚠️ field명은 action.validate()로 _ALNUM_UNDERSCORE 검증 완료 상태.
        Neo4j 동적 속성 SET은 n[$field] 파라미터 패턴 사용 (인젝션 안전).
        """
        target_id = self._resolve_ref(action.target_node, ctx)
        query = """
        MATCH (n {case_id: $case_id})
        WHERE n.node_id = $node_id OR n.id = $node_id
        SET n[$field] = $value, n.updated_at = datetime()
        RETURN n.node_id AS updated_id
        """
        await self._neo4j.execute_write(query, {
            "case_id": ctx.case_id,
            "node_id": target_id,
            "field": action.field,
            "value": action.value,
        })
        return {
            "node_id": target_id,
            "field": action.field,
            "old_value": ctx.node_states.get(target_id, {}).get(action.field),
            "new_value": action.value,
        }

    def _build_event(self, action: GWTAction, ctx: GWTEvalContext) -> dict:
        """이벤트 페이로드 구성 (변수 치환 포함)"""
        resolved_payload = {}
        for k, v in action.payload.items():
            if isinstance(v, str) and v.startswith("$"):
                resolved_payload[k] = self._resolve_ref(v, ctx)
            else:
                resolved_payload[k] = v
        return {
            "event_type": action.event_type,
            "payload": {
                **resolved_payload,
                "case_id": ctx.case_id,
                "tenant_id": ctx.tenant_id,
                "triggered_by_rule": ctx.event_type,
            },
        }

    def _resolve_ref(self, ref: str, ctx: GWTEvalContext) -> Any:
        """$trigger.xxx, $payload.xxx 등의 변수 참조 해석"""
        if not ref or not ref.startswith("$"):
            return ref
        parts = ref[1:].split(".")
        if parts[0] == "trigger":
            return getattr(ctx, parts[1], ref) if len(parts) > 1 else ctx.aggregate_id
        elif parts[0] == "payload":
            return ctx.payload.get(parts[1], ref) if len(parts) > 1 else ctx.payload
        return ref

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        """비교 연산자 평가"""
        if op == "==": return actual == expected
        if op == "!=": return actual != expected
        if op == ">":  return actual > expected
        if op == "<":  return actual < expected
        if op == ">=": return actual >= expected
        if op == "<=": return actual <= expected
        if op == "in": return actual in expected
        if op == "not_in": return actual not in expected
        if op == "contains": return expected in str(actual)
        return False

    def _parse_rule(self, node: dict) -> GWTRule:
        """Neo4j 노드 → GWTRule 변환"""
        return GWTRule(
            id=node["id"],
            name=node["name"],
            case_id=node["case_id"],
            tenant_id=node["tenant_id"],
            given=[GWTCondition(**c) for c in json.loads(node.get("given_conditions", "[]"))],
            when_event=node["when_event"],
            then=[GWTAction(**a) for a in json.loads(node.get("then_actions", "[]"))],
            enabled=node.get("enabled", True),
            priority=node.get("priority", 100),
            version=node.get("version", 1),
        )

    async def _load_context_states(
        self, ctx: GWTEvalContext, rules: list[GWTRule]
    ) -> None:
        """룰에서 참조하는 모든 노드의 현재 상태를 일괄 조회"""
        # 모든 룰의 given 조건에서 참조되는 layer 수집
        layers = set()
        for rule in rules:
            for cond in rule.given:
                if cond.node_layer:
                    layers.add(cond.node_layer)
                if cond.source_layer:
                    layers.add(cond.source_layer)
                if cond.target_layer:
                    layers.add(cond.target_layer)

        # 각 레이어별로 관련 노드 상태 조회
        # ⚠️ Critical #1 수정: 라벨 화이트리스트 검증 후에만 f-string 삽입
        for layer in layers:
            label = layer.capitalize()
            if label not in ALLOWED_LABELS:
                logger.warning("허용되지 않는 layer 무시: %s", layer)
                continue
            query = f"""
            MATCH (n:{label} {{case_id: $case_id}})
            RETURN n.node_id AS id, properties(n) AS props
            """
            records = await self._neo4j.execute_read(query, {
                "case_id": ctx.case_id,
            })
            for rec in records:
                ctx.node_states[rec["id"]] = rec["props"]


class GWTRuleManager:
    """
    GWT 룰 CRUD 관리자 — ActionType 노드의 생성/수정/삭제/조회

    프론트엔드의 도메인 모델러에서 사용
    """

    def __init__(self, neo4j_client):
        self._neo4j = neo4j_client

    async def create_rule(self, rule: GWTRule) -> str:
        """새 ActionType 노드 생성"""
        query = """
        CREATE (a:ActionType {
          id: $id,
          case_id: $case_id,
          tenant_id: $tenant_id,
          name: $name,
          description: $description,
          layer: "kinetic",
          enabled: $enabled,
          priority: $priority,
          version: $version,
          given_conditions: $given_conditions,
          when_event: $when_event,
          then_actions: $then_actions,
          created_at: datetime(),
          updated_at: datetime()
        })
        RETURN a.id AS id
        """
        records = await self._neo4j.execute_write(query, {
            "id": rule.id,
            "case_id": rule.case_id,
            "tenant_id": rule.tenant_id,
            "name": rule.name,
            "description": "",
            "enabled": rule.enabled,
            "priority": rule.priority,
            "version": rule.version,
            "given_conditions": json.dumps([c.__dict__ for c in rule.given], ensure_ascii=False),
            "when_event": rule.when_event,
            "then_actions": json.dumps([a.__dict__ for a in rule.then], ensure_ascii=False),
        })
        return records[0]["id"]

    async def list_rules(
        self, case_id: str, tenant_id: str,
        enabled_only: bool = False
    ) -> list[dict]:
        """해당 case의 모든 ActionType 조회"""
        where_clause = "AND a.enabled = true" if enabled_only else ""
        query = f"""
        MATCH (a:ActionType {{case_id: $case_id, tenant_id: $tenant_id}})
        {where_clause}
        RETURN a
        ORDER BY a.priority DESC, a.name
        """
        records = await self._neo4j.execute_read(query, {
            "case_id": case_id,
            "tenant_id": tenant_id,
        })
        return [dict(r["a"]) for r in records]

    async def update_rule(self, rule_id: str, updates: dict) -> bool:
        """ActionType 업데이트 (부분 수정)

        ⚠️ Major #8 수정: Cypher 인젝션 방지 — 허용 필드 화이트리스트 검증
        """
        # 허용되지 않는 필드 차단
        invalid_keys = set(updates.keys()) - ALLOWED_UPDATE_FIELDS
        if invalid_keys:
            raise ValueError(f"허용되지 않는 업데이트 필드: {invalid_keys}")

        set_clauses = ", ".join(f"a.{k} = ${k}" for k in updates.keys())
        query = f"""
        MATCH (a:ActionType {{id: $rule_id}})
        SET {set_clauses}, a.updated_at = datetime(), a.version = a.version + 1
        RETURN a.id AS id
        """
        records = await self._neo4j.execute_write(query, {
            "rule_id": rule_id,
            **updates,
        })
        return len(records) > 0

    async def delete_rule(self, rule_id: str) -> bool:
        """ActionType 삭제 (관계 포함)"""
        query = """
        MATCH (a:ActionType {id: $rule_id})
        DETACH DELETE a
        RETURN count(*) AS deleted
        """
        records = await self._neo4j.execute_write(query, {"rule_id": rule_id})
        return records[0]["deleted"] > 0

    ALLOWED_LINK_REL_TYPES = {"TRIGGERS", "MODIFIES", "CHAINS_TO", "USES_MODEL"}

    async def link_to_ontology(
        self, rule_id: str, node_id: str,
        rel_type: str = "TRIGGERS"
    ) -> None:
        """ActionType과 온톨로지 노드 간 관계 생성

        ⚠️ Major #9 수정:
        - rel_type 화이트리스트 검증
        - 라벨 제한 쿼리 (전체 노드 스캔 방지)
        """
        if rel_type not in self.ALLOWED_LINK_REL_TYPES:
            raise ValueError(f"허용되지 않는 link rel_type: {rel_type}. 허용: {self.ALLOWED_LINK_REL_TYPES}")

        if rel_type == "TRIGGERS":
            query = """
            MATCH (n) WHERE n.node_id = $node_id AND (n:Kpi OR n:Driver OR n:Measure OR n:Process OR n:Resource)
            MATCH (a:ActionType {id: $rule_id})
            MERGE (n)-[:TRIGGERS]->(a)
            """
        elif rel_type == "MODIFIES":
            query = """
            MATCH (a:ActionType {id: $rule_id})
            MATCH (n) WHERE n.node_id = $node_id AND (n:Kpi OR n:Driver OR n:Measure OR n:Process OR n:Resource)
            MERGE (a)-[:MODIFIES]->(n)
            """
        elif rel_type == "CHAINS_TO":
            query = """
            MATCH (a:ActionType {id: $rule_id})
            MATCH (b:ActionType {id: $node_id})
            MERGE (a)-[:CHAINS_TO]->(b)
            """
        elif rel_type == "USES_MODEL":
            query = """
            MATCH (a:ActionType {id: $rule_id})
            MATCH (m:OntologyBehavior {model_id: $node_id})
            MERGE (a)-[:USES_MODEL]->(m)
            """

        await self._neo4j.execute_write(query, {
            "rule_id": rule_id,
            "node_id": node_id,
        })


# ── Critical #2: 안전한 표현식 평가기 (eval() 대체) ──────────────

_SAFE_COMPARE_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne,
    ast.Lt: operator.lt, ast.Gt: operator.gt,
    ast.LtE: operator.le, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

_SAFE_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}


def safe_eval(expression: str, variables: dict[str, Any]) -> Any:
    """AST 기반 안전한 표현식 평가기 — eval() 완전 대체

    허용 노드:
    - Constant (숫자, 문자열, bool, None)
    - Name (변수 참조)
    - Compare (==, !=, >, <, >=, <=, in, not in)
    - BoolOp (and, or)
    - UnaryOp (not)
    - BinOp (+, -, *, /, %)
    - Attribute (state.xxx → dict key 접근으로 변환)
    - Subscript (state["xxx"])

    ❌ 금지: Call, Import, Lambda, FunctionDef, ClassDef, Exec, ...
    """
    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict) -> Any:
    """AST 노드 재귀 평가"""
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise ValueError(f"알 수 없는 변수: {node.id}")
        return variables[node.id]

    if isinstance(node, ast.Attribute):
        # state.xxx → state["xxx"]
        obj = _eval_node(node.value, variables)
        if isinstance(obj, dict):
            return obj.get(node.attr)
        raise ValueError(f"속성 접근 불가: {node.attr}")

    if isinstance(node, ast.Subscript):
        obj = _eval_node(node.value, variables)
        key = _eval_node(node.slice, variables)
        if isinstance(obj, dict):
            return obj.get(key)
        if isinstance(obj, (list, tuple)):
            return obj[key]
        raise ValueError(f"인덱스 접근 불가: {type(obj)}")

    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op_node, comparator in zip(node.ops, node.comparators):
            op_func = _SAFE_COMPARE_OPS.get(type(op_node))
            if op_func is None:
                raise ValueError(f"허용되지 않는 비교 연산자: {type(op_node).__name__}")
            right = _eval_node(comparator, variables)
            if not op_func(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, variables) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, variables) for v in node.values)

    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand, variables)
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand, variables)

    if isinstance(node, ast.BinOp):
        op_func = _SAFE_BIN_OPS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"허용되지 않는 이항 연산자: {type(node.op).__name__}")
        return op_func(_eval_node(node.left, variables), _eval_node(node.right, variables))

    raise ValueError(f"허용되지 않는 표현식 노드: {type(node).__name__}")
```

### 4.7 GWT 워커 (Redis Stream Consumer)

**파일**: `services/synapse/app/workers/gwt_consumer.py`

```python
"""
GWT Consumer Worker

Redis Stream에서 이벤트를 소비하여 GWT Engine으로 전달.
기존 Outbox Relay 패턴과 동일한 구조:
  axiom:core:events → GWT Engine → 결과 이벤트 → synapse.event_outbox
"""
import asyncio
import logging
from app.services.gwt_engine import GWTEngine

logger = logging.getLogger(__name__)

STREAMS = [
    "axiom:core:events",
    "axiom:synapse:events",
    "axiom:vision:events",
    "axiom:weaver:events",
]


class GWTConsumerWorker:
    """모든 서비스 이벤트를 소비하여 GWT 룰 매칭/실행"""

    def __init__(
        self,
        redis_client,
        gwt_engine: GWTEngine,
        consumer_group: str = "gwt-engine",
        consumer_name: str = "gwt-worker-1",
        poll_interval: float = 1.0,
    ):
        self._redis = redis_client
        self._engine = gwt_engine
        self._group = consumer_group
        self._consumer = consumer_name
        self._poll_interval = poll_interval
        self._running = False

    async def start(self):
        """워커 시작 — consumer group 생성 후 폴링 루프"""
        self._running = True

        # Consumer group 생성 (이미 존재하면 무시)
        for stream in STREAMS:
            try:
                await self._redis.xgroup_create(
                    stream, self._group, id="0", mkstream=True
                )
            except Exception:
                pass  # 이미 존재

        logger.info("GWT Consumer Worker 시작: streams=%s", STREAMS)

        while self._running:
            try:
                # 모든 스트림에서 새 메시지 읽기
                messages = await self._redis.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer,
                    streams={s: ">" for s in STREAMS},
                    count=50,
                    block=int(self._poll_interval * 1000),
                )

                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        await self._process_message(stream_name, msg_id, data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("GWT Consumer 오류: %s", e, exc_info=True)
                await asyncio.sleep(self._poll_interval)

    async def stop(self):
        """워커 중지"""
        self._running = False

    async def _process_message(self, stream: str, msg_id: str, data: dict):
        """단일 메시지 처리"""
        event_type = data.get("event_type", "")
        aggregate_id = data.get("aggregate_id", "")
        tenant_id = data.get("tenant_id", "")
        payload = data.get("payload", "{}")

        if isinstance(payload, str):
            import json
            payload = json.loads(payload)

        case_id = payload.get("case_id", "")
        if not case_id:
            # case_id 없는 이벤트는 GWT 대상이 아님
            await self._redis.xack(stream, self._group, msg_id)
            return

        try:
            results = await self._engine.handle_event(
                event_type=event_type,
                aggregate_id=aggregate_id,
                payload=payload,
                case_id=case_id,
                tenant_id=tenant_id,
            )

            for r in results:
                if r.matched:
                    logger.info(
                        "GWT 룰 실행: rule=%s, changes=%d, events=%d",
                        r.rule_name, len(r.state_changes), len(r.emitted_events),
                    )

            # ACK
            await self._redis.xack(stream, self._group, msg_id)

        except Exception as e:
            logger.error(
                "GWT 이벤트 처리 실패: event=%s, error=%s",
                event_type, e, exc_info=True,
            )
            # ACK하지 않으면 재시도됨 (pending list)
```

---

## 5. 설계 2: Graph Projector (이벤트→그래프 동기화)

### 5.1 개념

Graph Projector는 BusinessOS의 "Ontology Updater" 패턴:
- 이벤트가 발생할 때마다 Neo4j 온톨로지 그래프를 실시간 업데이트
- 온톨로지를 "살아있는 디지털 트윈"으로 만드는 핵심 컴포넌트
- CQRS Read-side Projection의 그래프 버전

### 5.2 워커 간 처리 순서 및 이벤트 소스 메타데이터

> **⚠️ Major #6 수정: GWTConsumer와 GraphProjector가 동일 스트림을 각각의 Consumer Group으로 소비.**

**처리 순서 원칙**:

1. **Graph Projector 먼저** → 온톨로지 그래프 상태를 최신화
2. **GWT Consumer 이후** → 최신 그래프 상태를 기반으로 Given 조건 평가

이를 보장하기 위해 GWT Consumer는 처리 전 약간의 지연(100ms)을 두거나,
Graph Projector가 완료 표시를 남기는 방식 대신, **멱등성으로 해결**한다:
- GWT Engine의 Given 평가는 매번 Neo4j에서 최신 상태를 조회하므로
  Graph Projector와의 순서에 관계없이 정확한 결과를 반환
- GWT Engine이 발행한 이벤트에는 `source: "gwt-engine"` 메타데이터를 포함하여
  GWT Consumer가 자신이 발행한 이벤트를 재소비하지 않도록 필터링

**Redis Stream 메시지에 추가할 메타데이터**:

```python
body = {
    "event_id": row["id"],
    "event_type": row["event_type"],
    "aggregate_type": row["aggregate_type"],
    "aggregate_id": row["aggregate_id"],
    "tenant_id": row["tenant_id"],
    "payload": row["payload"],
    "source_service": "synapse",          # 신규: 발행 서비스
    "source_worker": "gwt-engine",        # 신규: 발행 워커 (relay이면 "relay")
}
```

### 5.3 이벤트→Cypher 매핑 테이블

```python
"""
GraphProjector 이벤트→Cypher 매핑 정의

각 이벤트 타입에 대해 Neo4j에 어떤 변경을 적용할지 선언적으로 정의.
이 매핑은 Neo4j에 ProjectionRule 노드로 저장할 수도 있고,
코드에 정적으로 정의할 수도 있음.
"""

PROJECTION_RULES: dict[str, list[dict]] = {
    # === Core 서비스 이벤트 ===

    "PROCESS_INITIATED": [
        {
            "description": "프로세스 시작 → Process 노드 상태 업데이트",
            "cypher": """
                MATCH (p:Process {case_id: $case_id, node_id: $process_node_id})
                SET p.status = 'RUNNING',
                    p.started_at = datetime(),
                    p.updated_at = datetime()
            """,
            "params_map": {
                "process_node_id": "payload.process_node_id",
            },
        },
        {
            "description": "프로세스 이벤트 노드 생성 + 관계 연결",
            "cypher": """
                MATCH (p:Process {case_id: $case_id, node_id: $process_node_id})
                CREATE (e:Event {
                    id: $event_id,
                    type: 'PROCESS_INITIATED',
                    case_id: $case_id,
                    timestamp: datetime(),
                    payload: $payload_json
                })
                CREATE (p)-[:HAS_EVENT]->(e)
            """,
            "params_map": {
                "process_node_id": "payload.process_node_id",
                "payload_json": "$full_payload",
            },
        },
    ],

    "WORKITEM_COMPLETED": [
        {
            "description": "작업 완료 → Resource-Process 관계 가중치 업데이트",
            "cypher": """
                MATCH (r:Resource {case_id: $case_id, node_id: $resource_id})
                      -[rel:USES]->(p:Process {case_id: $case_id})
                SET rel.weight = CASE
                    WHEN rel.weight IS NULL THEN 0.5
                    ELSE min(1.0, rel.weight + 0.05)
                  END,
                    rel.last_activity = datetime(),
                    rel.updated_at = datetime()
            """,
            "params_map": {
                "resource_id": "payload.assignee_id",
            },
        },
    ],

    # === Vision 서비스 이벤트 ===

    "WHATIF_SIMULATION_COMPLETED": [
        {
            "description": "시뮬레이션 완료 → 결과 스냅샷 노드 생성",
            "cypher": """
                CREATE (s:SimulationSnapshot {
                    id: $snapshot_id,
                    case_id: $case_id,
                    scenario_name: $scenario_name,
                    simulation_id: $simulation_id,
                    converged: $converged,
                    propagation_waves: $waves,
                    created_at: datetime()
                })
            """,
            "params_map": {
                "snapshot_id": "$event_id",
                "scenario_name": "payload.scenario_name",
                "simulation_id": "payload.simulation_id",
                "converged": "payload.converged",
                "waves": "payload.propagation_waves",
            },
        },
    ],

    "CAUSAL_RELATION_DISCOVERED": [
        {
            "description": "인과 관계 발견 → Driver 노드 자동 생성 + CAUSES 관계",
            "cypher": """
                MERGE (d:Driver {case_id: $case_id, node_id: $driver_id})
                ON CREATE SET
                    d.name = $driver_name,
                    d.description = $description,
                    d.source = 'auto-discovered',
                    d.verified = false,
                    d.created_at = datetime()
                WITH d
                MATCH (target {case_id: $case_id, node_id: $target_node_id})
                MERGE (d)-[r:CAUSES]->(target)
                SET r.weight = $weight,
                    r.lag = $lag,
                    r.confidence = $confidence,
                    r.method = $method,
                    r.direction = $direction,
                    r.updated_at = datetime()
            """,
            "params_map": {
                "driver_id": "payload.driver_node_id",
                "driver_name": "payload.driver_name",
                "description": "payload.description",
                "target_node_id": "payload.target_node_id",
                "weight": "payload.weight",
                "lag": "payload.lag",
                "confidence": "payload.confidence",
                "method": "payload.method",
                "direction": "payload.direction",
            },
        },
    ],

    # === Weaver 서비스 이벤트 ===

    "INSIGHT_JOB_COMPLETED": [
        {
            "description": "인사이트 잡 완료 → KPI 노드 메트릭 업데이트",
            "cypher": """
                MATCH (k:Kpi {case_id: $case_id, node_id: $kpi_node_id})
                SET k.latest_value = $value,
                    k.latest_timestamp = datetime(),
                    k.trend = $trend,
                    k.updated_at = datetime()
            """,
            "params_map": {
                "kpi_node_id": "payload.kpi_node_id",
                "value": "payload.result_value",
                "trend": "payload.trend",
            },
        },
    ],

    "METADATA_TABLE_DISCOVERED": [
        {
            "description": "새 테이블 발견 → Table 노드 생성",
            "cypher": """
                MERGE (t:Table {name: $table_name, datasource_id: $datasource_id})
                ON CREATE SET
                    t.schema = $schema_name,
                    t.datasource_id = $datasource_id,
                    t.description = $description,
                    t.row_count = $row_count,
                    t.created_at = datetime()
                ON MATCH SET
                    t.row_count = $row_count,
                    t.updated_at = datetime()
            """,
            "params_map": {
                "table_name": "payload.table_name",
                "schema_name": "payload.schema_name",
                "datasource_id": "payload.datasource_id",
                "description": "payload.description",
                "row_count": "payload.row_count",
            },
        },
    ],
}
```

### 5.3 GraphProjector 워커

**파일**: `services/synapse/app/workers/graph_projector.py`

```python
"""
Graph Projector Worker

Redis Stream에서 모든 서비스 이벤트를 소비하여
PROJECTION_RULES에 따라 Neo4j 그래프를 실시간 업데이트.

BusinessOS의 "Ontology Updater" 패턴 구현.
온톨로지를 "살아있는 디지털 트윈"으로 만드는 핵심 워커.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STREAMS = [
    "axiom:core:events",
    "axiom:synapse:events",
    "axiom:vision:events",
    "axiom:weaver:events",
]


class GraphProjectorWorker:
    """이벤트→Neo4j 그래프 프로젝션 워커"""

    def __init__(
        self,
        redis_client,
        neo4j_client,
        projection_rules: dict,
        consumer_group: str = "graph-projector",
        consumer_name: str = "projector-1",
        poll_interval: float = 1.0,
    ):
        self._redis = redis_client
        self._neo4j = neo4j_client
        self._rules = projection_rules
        self._group = consumer_group
        self._consumer = consumer_name
        self._poll_interval = poll_interval
        self._running = False
        self._stats = {"projected": 0, "skipped": 0, "failed": 0}

    async def start(self):
        """워커 시작"""
        self._running = True

        for stream in STREAMS:
            try:
                await self._redis.xgroup_create(
                    stream, self._group, id="0", mkstream=True
                )
            except Exception:
                pass

        logger.info("Graph Projector 시작: rules=%d개 이벤트 타입 매핑", len(self._rules))

        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=self._group,
                    consumername=self._consumer,
                    streams={s: ">" for s in STREAMS},
                    count=100,
                    block=int(self._poll_interval * 1000),
                )

                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        await self._project(stream_name, msg_id, data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Graph Projector 오류: %s", e, exc_info=True)
                await asyncio.sleep(self._poll_interval)

        logger.info("Graph Projector 종료: stats=%s", self._stats)

    async def _project(self, stream: str, msg_id: str, data: dict):
        """단일 이벤트 프로젝션"""
        event_type = data.get("event_type", "")

        rules = self._rules.get(event_type)
        if not rules:
            self._stats["skipped"] += 1
            await self._redis.xack(stream, self._group, msg_id)
            return

        payload = data.get("payload", "{}")
        if isinstance(payload, str):
            payload = json.loads(payload)

        case_id = payload.get("case_id", "")
        event_id = data.get("event_id", str(uuid.uuid4()))

        for rule in rules:
            try:
                # 파라미터 해석
                params = self._resolve_params(
                    rule["params_map"],
                    payload=payload,
                    case_id=case_id,
                    event_id=event_id,
                    full_payload=json.dumps(payload, ensure_ascii=False),
                )

                # Cypher 실행
                await self._neo4j.execute_write(rule["cypher"], params)

                logger.debug(
                    "Graph Projection 완료: event=%s, rule=%s",
                    event_type, rule["description"],
                )
                self._stats["projected"] += 1

            except Exception as e:
                logger.error(
                    "Graph Projection 실패: event=%s, rule=%s, error=%s",
                    event_type, rule["description"], e,
                )
                self._stats["failed"] += 1

        await self._redis.xack(stream, self._group, msg_id)

    def _resolve_params(
        self, params_map: dict, *, payload: dict,
        case_id: str, event_id: str, full_payload: str,
    ) -> dict:
        """파라미터 매핑 해석"""
        resolved = {"case_id": case_id}
        for param_name, source in params_map.items():
            if source == "$event_id":
                resolved[param_name] = event_id
            elif source == "$full_payload":
                resolved[param_name] = full_payload
            elif source.startswith("payload."):
                key = source[len("payload."):]
                resolved[param_name] = payload.get(key)
            else:
                resolved[param_name] = source
        return resolved
```

---

## 6. 설계 3: Event Fork 기반 What-If 브랜칭

### 6.1 개념

BusinessOS의 핵심 통찰:
> "이벤트소싱 기반 저장 방식이므로 특정 시점의 상태를 항상 재구성할 수 있고,
>  현재 상태를 복제(Fork)하여 가상 이벤트를 적용하면 What-If 시뮬레이션이 자연스러움."

기존 Axiom의 DAG Propagation 방식(인메모리 모델 계산)은 유지하되,
**Event Fork 모드를 추가**하여 결정적 시뮬레이션을 지원.

### 6.2 데이터 모델

**PostgreSQL**: `vision.simulation_branches` 테이블

```sql
-- 시뮬레이션 브랜치: 특정 시점에서 포크된 이벤트 스트림
CREATE TABLE vision.simulation_branches (
    id              TEXT PRIMARY KEY,          -- sim_branch_{uuid}
    case_id         TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    name            TEXT NOT NULL,             -- "2026 원가 20% 절감 시나리오"
    description     TEXT,
    base_timestamp  TIMESTAMPTZ NOT NULL,      -- 포크 시점
    status          TEXT NOT NULL DEFAULT 'created',  -- created|running|completed|failed

    -- 시뮬레이션 설정
    interventions   JSONB NOT NULL DEFAULT '[]',      -- InterventionSpec 배열
    gwt_overrides   JSONB DEFAULT '{}',               -- 오버라이드할 GWT 룰 ID → 변경사항

    -- 결과
    result_summary  JSONB,                    -- KPI 델타, 영향도 요약
    event_count     INTEGER DEFAULT 0,        -- 시뮬레이션 이벤트 수

    -- 감사
    created_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,

    -- 인덱스
    CONSTRAINT idx_sim_branch_case UNIQUE (case_id, name)
);

CREATE INDEX idx_sim_branch_tenant ON vision.simulation_branches(tenant_id, created_at DESC);
CREATE INDEX idx_sim_branch_status ON vision.simulation_branches(status) WHERE status != 'completed';
```

**PostgreSQL**: `vision.simulation_events` 테이블

```sql
-- 시뮬레이션 이벤트 로그: 브랜치 내 가상 이벤트
CREATE TABLE vision.simulation_events (
    id              TEXT PRIMARY KEY,          -- sim_evt_{uuid}
    branch_id       TEXT NOT NULL REFERENCES vision.simulation_branches(id),
    sequence_number INTEGER NOT NULL,          -- 브랜치 내 순서

    -- 이벤트 데이터 (EventOutbox와 동일 구조)
    event_type      TEXT NOT NULL,
    aggregate_type  TEXT,
    aggregate_id    TEXT,
    payload         JSONB NOT NULL,

    -- 메타데이터
    source          TEXT NOT NULL DEFAULT 'intervention',  -- intervention|gwt_rule|cascade
    source_rule_id  TEXT,                     -- GWT 룰에 의해 생성된 경우

    -- 상태 스냅샷 (이 이벤트 적용 후의 상태)
    state_snapshot  JSONB,                    -- {node_id: {field: value, ...}, ...}

    created_at      TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_sim_event_seq UNIQUE (branch_id, sequence_number)
);

CREATE INDEX idx_sim_event_branch ON vision.simulation_events(branch_id, sequence_number);
```

### 6.3 Event Fork Engine

**파일**: `services/vision/app/engines/event_fork_engine.py`

```python
"""
Event Fork Engine — 이벤트소싱 기반 What-If 시뮬레이션

BusinessOS 패턴:
1. 특정 시점의 온톨로지 상태를 스냅샷 (base_timestamp)
2. 사용자 개입(intervention)을 초기 이벤트로 변환
3. GWT 룰 엔진을 시뮬레이션 모드로 실행 (실제 DB 변경 없음)
4. 결과 이벤트 체인을 simulation_events에 기록
5. base vs simulation 상태 비교 (KPI 델타)

기존 DAG Propagation과의 차이:
- DAG: 모델 기반 예측 (비결정적, ML 의존)
- Fork: 이벤트 기반 재생 (결정적, 룰 의존)
- 둘 다 유지하되 사용자가 모드 선택 가능
"""
from dataclasses import dataclass, field
from typing import Any
import json
import uuid
from datetime import datetime, timezone

from app.engines.whatif_models import InterventionSpec, SimulationResult, SimulationTrace


@dataclass
class ForkConfig:
    """Event Fork 시뮬레이션 설정"""
    branch_name: str
    case_id: str
    tenant_id: str
    base_timestamp: datetime
    interventions: list[InterventionSpec]
    max_cascade_depth: int = 20        # GWT 체이닝 최대 깊이
    gwt_overrides: dict = field(default_factory=dict)  # 룰 오버라이드


@dataclass
class ForkResult:
    """Event Fork 시뮬레이션 결과"""
    branch_id: str
    branch_name: str
    base_state: dict[str, dict[str, Any]]     # 포크 시점 상태
    final_state: dict[str, dict[str, Any]]    # 시뮬레이션 후 상태
    events: list[dict]                         # 발생한 이벤트 체인
    kpi_deltas: dict[str, float]              # KPI 변화량
    event_count: int
    cascade_depth: int                         # 실제 체이닝 깊이
    converged: bool


class EventForkEngine:
    """이벤트 포크 기반 What-If 시뮬레이션 엔진

    ⚠️ Major #5 수정: GWT Engine을 dry_run=True 모드로 사용하여
    시뮬레이션 중 실제 Neo4j 변경이나 이벤트 발행이 일어나지 않음.
    모든 상태 변경은 인메모리 sim_state에만 적용됨.
    """

    def __init__(self, neo4j_client, db_session_factory, gwt_engine_factory):
        """gwt_engine_factory: lambda dry_run: GWTEngine(..., dry_run=dry_run)"""
        self._neo4j = neo4j_client
        self._db = db_session_factory
        # 시뮬레이션 전용 GWT 엔진 (dry_run=True)
        self._gwt = gwt_engine_factory(dry_run=True)

    async def create_fork(self, config: ForkConfig) -> str:
        """시뮬레이션 브랜치 생성"""
        branch_id = f"sim_branch_{uuid.uuid4().hex[:12]}"

        async with self._db() as session:
            await session.execute(
                """INSERT INTO vision.simulation_branches
                   (id, case_id, tenant_id, name, base_timestamp, interventions, gwt_overrides, status)
                   VALUES (:id, :case_id, :tenant_id, :name, :ts, :interventions, :overrides, 'created')""",
                {
                    "id": branch_id,
                    "case_id": config.case_id,
                    "tenant_id": config.tenant_id,
                    "name": config.branch_name,
                    "ts": config.base_timestamp,
                    "interventions": json.dumps([i.to_dict() for i in config.interventions]),
                    "overrides": json.dumps(config.gwt_overrides),
                },
            )
            await session.commit()

        return branch_id

    async def run_simulation(self, branch_id: str) -> ForkResult:
        """
        시뮬레이션 실행

        1. base_timestamp 시점의 온톨로지 상태 스냅샷
        2. intervention → 초기 이벤트 변환
        3. GWT 룰 체인 실행 (시뮬레이션 모드)
        4. 결과 비교
        """
        # 브랜치 정보 로드
        branch = await self._load_branch(branch_id)

        # 1. 기준 상태 스냅샷
        base_state = await self._snapshot_ontology_state(
            branch["case_id"], branch["base_timestamp"]
        )

        # 2. 시뮬레이션 상태 = 기준 상태 복제
        sim_state = {k: dict(v) for k, v in base_state.items()}

        # 3. intervention을 초기 이벤트로 변환
        interventions = [
            InterventionSpec(**i) for i in json.loads(branch["interventions"])
        ]

        events = []
        seq = 0

        for intervention in interventions:
            # 상태 적용
            node_key = f"{intervention.node_id}::{intervention.field}"
            if intervention.node_id in sim_state:
                sim_state[intervention.node_id][intervention.field] = intervention.value

            # 이벤트 기록
            event = {
                "event_type": "INTERVENTION_APPLIED",
                "aggregate_id": intervention.node_id,
                "payload": intervention.to_dict(),
                "source": "intervention",
                "sequence": seq,
            }
            events.append(event)
            seq += 1

        # 4. GWT 룰 체인 실행 (시뮬레이션 모드)
        depth = 0
        pending_events = list(events)

        while pending_events and depth < branch.get("max_cascade_depth", 20):
            next_events = []

            for event in pending_events:
                # GWT 엔진으로 룰 매칭 (실제 DB 변경 없이 결과만 반환)
                gwt_results = await self._gwt.handle_event(
                    event_type=event["event_type"],
                    aggregate_id=event["aggregate_id"],
                    payload=event["payload"],
                    case_id=branch["case_id"],
                    tenant_id=branch["tenant_id"],
                )

                for result in gwt_results:
                    if result.matched:
                        # 상태 변경 적용 (시뮬레이션 상태에만)
                        for change in result.state_changes:
                            node_id = change["node_id"]
                            if node_id in sim_state:
                                sim_state[node_id][change["field"]] = change["new_value"]

                        # 발행된 이벤트를 다음 라운드로
                        for emitted in result.emitted_events:
                            cascade_event = {
                                "event_type": emitted["event_type"],
                                "aggregate_id": result.rule_id,
                                "payload": emitted["payload"],
                                "source": "gwt_rule",
                                "source_rule_id": result.rule_id,
                                "sequence": seq,
                            }
                            next_events.append(cascade_event)
                            events.append(cascade_event)
                            seq += 1

            pending_events = next_events
            depth += 1

        # 5. KPI 델타 계산
        kpi_deltas = {}
        for node_id, state in sim_state.items():
            if node_id in base_state:
                for field_name, new_val in state.items():
                    old_val = base_state[node_id].get(field_name)
                    if isinstance(new_val, (int, float)) and isinstance(old_val, (int, float)):
                        delta = new_val - old_val
                        if abs(delta) > 1e-6:
                            kpi_deltas[f"{node_id}::{field_name}"] = delta

        # 6. 결과 저장
        await self._save_simulation_events(branch_id, events)
        await self._update_branch_result(branch_id, kpi_deltas, len(events), depth)

        return ForkResult(
            branch_id=branch_id,
            branch_name=branch["name"],
            base_state=base_state,
            final_state=sim_state,
            events=events,
            kpi_deltas=kpi_deltas,
            event_count=len(events),
            cascade_depth=depth,
            converged=len(pending_events) == 0,
        )

    async def compare_scenarios(
        self, branch_ids: list[str]
    ) -> dict:
        """여러 시뮬레이션 브랜치 결과 비교"""
        results = {}
        for bid in branch_ids:
            async with self._db() as session:
                row = await session.execute(
                    "SELECT name, result_summary, event_count FROM vision.simulation_branches WHERE id = :id",
                    {"id": bid},
                )
                r = row.fetchone()
                if r:
                    results[bid] = {
                        "name": r[0],
                        "kpi_deltas": json.loads(r[1]) if r[1] else {},
                        "event_count": r[2],
                    }

        # KPI별 시나리오 비교 매트릭스 생성
        all_kpis = set()
        for r in results.values():
            all_kpis.update(r["kpi_deltas"].keys())

        comparison_matrix = {}
        for kpi in sorted(all_kpis):
            comparison_matrix[kpi] = {
                bid: r["kpi_deltas"].get(kpi, 0.0)
                for bid, r in results.items()
            }

        return {
            "scenarios": results,
            "comparison_matrix": comparison_matrix,
        }

    async def _snapshot_ontology_state(
        self, case_id: str, timestamp: datetime
    ) -> dict[str, dict[str, Any]]:
        """온톨로지 상태 스냅샷

        ⚠️ Major #11 수정: 시점 기반 스냅샷 전략
        1. OntologySnapshot 노드가 존재하면 base_timestamp 이전 가장 가까운 스냅샷 사용
        2. 스냅샷 없으면 현재 상태를 기준으로 사용 (known limitation)
        3. TODO Phase 2+: 이벤트 소싱 기반 상태 재구성 (EventOutbox replay)
        """
        # 1차: OntologySnapshot에서 가장 가까운 스냅샷 조회
        snapshot_query = """
        MATCH (s:OntologySnapshot {case_id: $case_id})
        WHERE s.created_at <= $timestamp
        RETURN s.data AS data, s.created_at AS ts
        ORDER BY s.created_at DESC
        LIMIT 1
        """
        snapshots = await self._neo4j.execute_read(snapshot_query, {
            "case_id": case_id,
            "timestamp": timestamp.isoformat(),
        })
        if snapshots and snapshots[0].get("data"):
            import json
            data = snapshots[0]["data"]
            if isinstance(data, str):
                data = json.loads(data)
            return data

        # 2차: 스냅샷 없으면 현재 그래프 상태 사용 (폴백)
        logger.warning(
            "OntologySnapshot 없음, 현재 상태를 기준으로 시뮬레이션: case=%s, ts=%s",
            case_id, timestamp,
        )
        query = """
        MATCH (n {case_id: $case_id})
        WHERE n:Kpi OR n:Driver OR n:Measure OR n:Process OR n:Resource
        RETURN n.node_id AS id, properties(n) AS props
        """
        records = await self._neo4j.execute_read(query, {"case_id": case_id})
        return {r["id"]: r["props"] for r in records}

    async def _load_branch(self, branch_id: str) -> dict:
        """브랜치 정보 로드"""
        async with self._db() as session:
            row = await session.execute(
                "SELECT * FROM vision.simulation_branches WHERE id = :id",
                {"id": branch_id},
            )
            return dict(row.fetchone()._mapping)

    async def _save_simulation_events(self, branch_id: str, events: list[dict]):
        """시뮬레이션 이벤트 배치 저장"""
        async with self._db() as session:
            for event in events:
                await session.execute(
                    """INSERT INTO vision.simulation_events
                       (id, branch_id, sequence_number, event_type, aggregate_id, payload, source, source_rule_id)
                       VALUES (:id, :bid, :seq, :type, :agg, :payload, :source, :rule_id)""",
                    {
                        "id": f"sim_evt_{uuid.uuid4().hex[:12]}",
                        "bid": branch_id,
                        "seq": event["sequence"],
                        "type": event["event_type"],
                        "agg": event.get("aggregate_id", ""),
                        "payload": json.dumps(event["payload"], ensure_ascii=False),
                        "source": event.get("source", "unknown"),
                        "rule_id": event.get("source_rule_id"),
                    },
                )
            await session.commit()

    async def _update_branch_result(
        self, branch_id: str, kpi_deltas: dict, event_count: int, depth: int
    ):
        """브랜치 결과 업데이트"""
        async with self._db() as session:
            await session.execute(
                """UPDATE vision.simulation_branches
                   SET status = 'completed',
                       result_summary = :summary,
                       event_count = :count,
                       completed_at = NOW()
                   WHERE id = :id""",
                {
                    "id": branch_id,
                    "summary": json.dumps(kpi_deltas),
                    "count": event_count,
                },
            )
            await session.commit()
```

---

## 7. 설계 4: 문서→온톨로지 자동 추출 파이프라인

### 7.1 개념

BusinessOS의 ontosys-main 프로젝트 핵심 기능:
- 문서(PDF/DOCX) 업로드 → 텍스트 추출 → LLM으로 DDD 개념 추출
- Aggregate, Command, Event, Policy를 자동 식별
- 각 추출 결과에 source_anchor (문서 위치) 트레이서빌리티
- 추출 결과를 Neo4j 온톨로지 노드로 자동 변환

### 7.2 Weaver 확장: 문서 업로드 API

**파일**: `services/weaver/app/api/document_ingestion.py`

```python
"""
문서→온톨로지 추출 파이프라인 API

BusinessOS ontosys-main 패턴을 Axiom에 적용:
1. 문서 업로드 → 텍스트 추출 + 청킹
2. LLM으로 DDD 개념 추출 (Aggregate/Command/Event/Policy)
3. 추출 결과 → Synapse 온톨로지 노드로 자동 변환
4. DocFrag 트레이서빌리티 (원본 문서 위치 ↔ 온톨로지 노드)
"""
from fastapi import APIRouter, UploadFile, File, BackgroundTasks
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v3/weaver/documents", tags=["document-ingestion"])


# --- 요청/응답 모델 ---

class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    file_type: str
    page_count: int
    fragment_count: int
    status: str  # uploaded | processing | processed | failed


class ExtractionJobResponse(BaseModel):
    job_id: str
    doc_id: str
    status: str  # queued | running | done | error
    progress: int  # 0-100


class DocFragment(BaseModel):
    """문서 조각 — 추출 결과의 소스 앵커"""
    id: str
    doc_id: str
    page: int
    span_start: int
    span_end: int
    text: str


class ExtractedEntity(BaseModel):
    """LLM이 추출한 DDD 개념"""
    name: str
    entity_type: str  # aggregate | command | event | policy
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_anchor: DocFragment | None = None
    properties: dict = {}
    # 온톨로지 매핑
    suggested_layer: str = ""     # kpi | measure | process | resource | driver
    suggested_relations: list[dict] = []  # [{source, target, type, weight}]


class ExtractionResult(BaseModel):
    """문서에서 추출된 전체 결과"""
    doc_id: str
    aggregates: list[ExtractedEntity]
    commands: list[ExtractedEntity]
    events: list[ExtractedEntity]
    policies: list[ExtractedEntity]
    total_entities: int
    avg_confidence: float


# --- API 엔드포인트 ---

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    case_id: str = "",
    background_tasks: BackgroundTasks = None,
):
    """
    문서 업로드 + 텍스트 추출 + 청킹

    지원 형식: PDF, DOCX, TXT, MD
    청킹 전략: 페이지 기반 + 의미 단위 (max 1200자)
    """
    pass  # 구현 시 DocumentService.extract_text() 호출


@router.post("/extract", response_model=ExtractionJobResponse)
async def start_extraction(
    doc_id: str,
    case_id: str,
    target_layers: list[str] = ["process", "resource", "measure"],
    background_tasks: BackgroundTasks = None,
):
    """
    DDD 개념 추출 시작 (비동기 잡)

    LLM 프롬프트:
    - 시스템: "DDD/이벤트스토밍 전문가. Aggregate, Command, Event, Policy 식별"
    - 사용자: 문서 청크 + 기존 온톨로지 컨텍스트
    - 출력: 구조화된 JSON (Pydantic 검증)
    """
    pass


@router.get("/extract/status", response_model=ExtractionJobResponse)
async def get_extraction_status(job_id: str):
    """추출 진행률 폴링"""
    pass


@router.get("/extract/result", response_model=ExtractionResult)
async def get_extraction_result(job_id: str):
    """추출 결과 조회"""
    pass


@router.post("/extract/apply")
async def apply_to_ontology(
    job_id: str,
    case_id: str,
    selected_entities: list[str] = [],  # 빈 리스트면 전체 적용
):
    """
    추출 결과를 Synapse 온톨로지에 적용

    1. 각 entity를 해당 layer의 노드로 변환
    2. suggested_relations를 관계로 생성
    3. DocFrag → DERIVED_FROM 관계로 트레이서빌리티 연결
    """
    pass
```

### 7.3 LLM 추출 서비스

**파일**: `services/weaver/app/services/ddd_extraction_service.py`

```python
"""
DDD 추출 서비스 — LLM 기반 문서→도메인 개념 추출

BusinessOS의 LLM Service 패턴:
- 시스템 프롬프트로 DDD 전문가 역할 부여
- Few-shot 예제로 추출 정확도 향상
- Pydantic 출력 파서로 구조화된 결과 보장
- confidence 점수로 신뢰도 표시
"""

DDD_EXTRACTION_SYSTEM_PROMPT = """
당신은 DDD(Domain-Driven Design)와 이벤트 스토밍 전문가입니다.
주어진 텍스트에서 다음 개념을 식별하세요:

1. **Aggregate (어그리거트)**: 비즈니스 엔티티, 명사, 단수형
   - 예: Order, Customer, Machine, Sensor
   - 온톨로지 계층: process, resource, measure 중 적절한 것

2. **Command (커맨드)**: 수행할 액션, 명령형
   - 예: CreateOrder, StartMaintenance, ApprovePayment
   - 형식: 동사 + 명사 (UpperCamelCase)

3. **Event (이벤트)**: 발생한 사실, 과거형
   - 예: OrderCreated, MaintenanceCompleted, PaymentApproved
   - 형식: 명사 + 과거분사 (UpperCamelCase)

4. **Policy (정책)**: 반응형 비즈니스 규칙
   - 예: "결제 확인되면 배송 시작", "온도 초과 시 정비 예약"
   - 형식: snake_case 또는 자연어 설명

각 개념에 대해:
- name: 정확한 이름
- description: 간결한 설명 (한국어)
- confidence: 0.0-1.0 (텍스트에서 명확히 언급되었으면 0.9+, 추론이면 0.5-0.7)
- source_text: 근거가 되는 원문 발췌

관계도 식별하세요:
- Command → Aggregate (TARGETS): 어떤 커맨드가 어떤 엔티티를 변경하는가
- Command → Event (EMITS): 어떤 커맨드가 어떤 이벤트를 발생시키는가
- Policy → Event (LISTENS): 어떤 정책이 어떤 이벤트에 반응하는가
- Policy → Command (ISSUES): 어떤 정책이 어떤 커맨드를 실행하는가

JSON 형식으로 출력하세요.
"""


class DDDExtractionService:
    """LLM 기반 DDD 개념 추출기"""

    def __init__(self, llm_client, neo4j_client=None):
        self._llm = llm_client
        self._neo4j = neo4j_client  # 기존 온톨로지 컨텍스트 조회용

    async def extract_from_fragments(
        self,
        fragments: list[dict],  # [{text, page, span_start, span_end}]
        case_id: str = "",
        existing_context: list[dict] | None = None,
    ) -> dict:
        """
        문서 프래그먼트에서 DDD 개념 추출

        1. 기존 온톨로지 컨텍스트 조회 (중복 방지)
        2. 각 프래그먼트에 대해 LLM 호출
        3. 결과 병합 + 퍼지 중복 제거
        4. confidence 기반 필터링
        """
        # 기존 온톨로지에서 이미 있는 노드 이름 조회 (중복 방지)
        if self._neo4j and case_id:
            existing_context = await self._get_existing_nodes(case_id)

        all_results = {
            "aggregates": [],
            "commands": [],
            "events": [],
            "policies": [],
        }

        for fragment in fragments:
            result = await self._extract_single(fragment, existing_context)
            for key in all_results:
                all_results[key].extend(result.get(key, []))

        # 퍼지 중복 제거 (이름 유사도 > 0.85이면 병합)
        for key in all_results:
            all_results[key] = self._deduplicate(all_results[key])

        return all_results

    async def _extract_single(self, fragment: dict, context: list | None) -> dict:
        """단일 프래그먼트 추출"""
        context_str = ""
        if context:
            context_str = f"\n\n기존 온톨로지 노드 (중복 생성 방지):\n{', '.join(n['name'] for n in context[:50])}"

        user_prompt = f"""
텍스트:
---
{fragment['text']}
---
페이지: {fragment.get('page', 'N/A')}
{context_str}
"""
        response = await self._llm.agenerate(
            system=DDD_EXTRACTION_SYSTEM_PROMPT,
            user=user_prompt,
            response_format="json",
            temperature=0.3,
        )

        # JSON 파싱 + 소스 앵커 연결
        result = self._parse_llm_response(response)
        for key in result:
            for entity in result[key]:
                entity["source_anchor"] = {
                    "page": fragment.get("page", 0),
                    "span_start": fragment.get("span_start", 0),
                    "span_end": fragment.get("span_end", 0),
                }

        return result

    def _deduplicate(self, entities: list[dict]) -> list[dict]:
        """이름 기반 퍼지 중복 제거"""
        seen = {}
        result = []
        for entity in entities:
            name_lower = entity["name"].lower().replace("_", "").replace("-", "")
            # 이미 유사한 이름이 있으면 confidence 높은 것 유지
            duplicate = False
            for existing_name, idx in seen.items():
                if self._name_similarity(name_lower, existing_name) > 0.85:
                    if entity.get("confidence", 0) > result[idx].get("confidence", 0):
                        result[idx] = entity
                    duplicate = True
                    break
            if not duplicate:
                seen[name_lower] = len(result)
                result.append(entity)
        return result

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """간단한 문자열 유사도 (Jaccard 기반)"""
        if a == b:
            return 1.0
        set_a = set(a)
        set_b = set(b)
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    async def _get_existing_nodes(self, case_id: str) -> list[dict]:
        """기존 온톨로지 노드 이름 목록 조회"""
        query = """
        MATCH (n {case_id: $case_id})
        WHERE n:Kpi OR n:Driver OR n:Measure OR n:Process OR n:Resource
        RETURN n.name AS name, n.node_id AS id, labels(n)[0] AS layer
        LIMIT 200
        """
        records = await self._neo4j.execute_read(query, {"case_id": case_id})
        return [dict(r) for r in records]

    def _parse_llm_response(self, response: str) -> dict:
        """LLM 응답 JSON 파싱 (에러 안전)"""
        import json
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # JSON 블록 추출 시도
            import re
            match = re.search(r'\{[\s\S]*\}', response)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return {"aggregates": [], "commands": [], "events": [], "policies": []}
```

---

## 8. 설계 5: Policy Orchestrator (사가/정책 자동 실행)

### 8.1 개념

BusinessOS의 Policy 패턴:
- 정책이 Neo4j에 LinkType으로 저장
- 이벤트 발생 → 매칭 정책 검색 → 타겟 서비스에 커맨드 자동 발행
- WatchRule(알림 전용)과 달리 **실제 커맨드를 실행**하는 오케스트레이션

### 8.2 Neo4j Policy 노드

```cypher
-- Policy: 이벤트 반응형 자동 오케스트레이션 룰
CREATE (p:Policy {
  id: "policy_auto_maintenance",
  case_id: "case-001",
  tenant_id: "tenant-001",

  name: "온도 초과 자동 정비 예약",
  description: "센서 온도가 임계치 초과 시 자동으로 정비 워크오더 생성",
  layer: "kinetic",
  enabled: true,

  -- 트리거
  trigger_event: "TemperatureReadingReceived",
  trigger_condition: '{"field": "temperature", "op": ">", "value": 85.0}',

  -- 발행할 커맨드
  target_service: "core",                    -- 대상 서비스
  target_command: "CreateWorkOrder",          -- 발행할 커맨드
  command_payload_template: '{
    "activity_name": "정비 점검",
    "activity_type": "humanTask",
    "agent_mode": "SUPERVISED",
    "priority": "HIGH",
    "context": {
      "sensor_id": "$trigger.payload.sensor_id",
      "temperature": "$trigger.payload.temperature",
      "threshold": 85.0
    }
  }',

  -- 실행 제어
  cooldown_seconds: 3600,                    -- 같은 정책 재실행 쿨다운 (1시간)
  max_executions_per_day: 10,               -- 일일 최대 실행 횟수

  created_at: datetime(),
  updated_at: datetime()
})

-- Policy → 소스 노드 (트리거 이벤트의 원천)
MATCH (s:Resource {node_id: "sensor-001"})
CREATE (s)-[:EMITS_TO]->(p)

-- Policy → 타겟 노드 (커맨드의 대상)
MATCH (t:Process {node_id: "maintenance-process"})
CREATE (p)-[:DISPATCHES_TO]->(t)
```

### 8.3 PolicyExecutor 워커

**파일**: `services/core/app/workers/policy_executor.py`

```python
"""
Policy Executor Worker

GWT Engine과 다른 점:
- GWT: 온톨로지 노드 상태를 직접 변경 (Neo4j SET)
- Policy: 다른 서비스에 커맨드를 발행 (서비스 간 오케스트레이션)

실행 흐름:
  Redis Stream 이벤트 → Policy 매칭 (Neo4j 조회) →
  커맨드 구성 (페이로드 템플릿 해석) → 대상 서비스 API 호출 or EventOutbox 기록
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class PolicyExecutorWorker:
    """서비스 간 이벤트 반응형 오케스트레이션 워커"""

    def __init__(
        self,
        redis_client,
        neo4j_client,
        event_publisher,
        http_client=None,
        consumer_group: str = "policy-executor",
    ):
        self._redis = redis_client
        self._neo4j = neo4j_client
        self._publisher = event_publisher
        self._http = http_client  # 서비스 간 동기 호출용 (옵션)
        self._group = consumer_group
        self._running = False
        # ⚠️ Minor 수정: 쿨다운을 Redis로 관리 (워커 재시작/수평 확장 대응)
        # 키: axiom:policy:cooldown:{policy_id}, 값: ISO timestamp, TTL: cooldown_seconds

    async def start(self):
        """워커 시작"""
        self._running = True
        streams = ["axiom:core:events", "axiom:synapse:events", "axiom:vision:events"]

        for stream in streams:
            try:
                await self._redis.xgroup_create(stream, self._group, id="0", mkstream=True)
            except Exception:
                pass

        logger.info("Policy Executor 시작")

        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    groupname=self._group,
                    consumername="policy-1",
                    streams={s: ">" for s in streams},
                    count=50,
                    block=1000,
                )
                for stream_name, entries in messages:
                    for msg_id, data in entries:
                        await self._process(stream_name, msg_id, data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Policy Executor 오류: %s", e, exc_info=True)
                await asyncio.sleep(1)

    async def _process(self, stream: str, msg_id: str, data: dict):
        """이벤트 → 정책 매칭 → 커맨드 발행"""
        event_type = data.get("event_type", "")
        payload = json.loads(data.get("payload", "{}")) if isinstance(data.get("payload"), str) else data.get("payload", {})
        case_id = payload.get("case_id", "")
        tenant_id = data.get("tenant_id", "")

        if not case_id:
            await self._redis.xack(stream, self._group, msg_id)
            return

        # 매칭 정책 조회
        policies = await self._find_matching_policies(case_id, event_type)

        for policy in policies:
            policy_id = policy["id"]

            # 쿨다운 확인 (Redis 기반)
            if not await self._check_cooldown(policy_id, policy.get("cooldown_seconds", 0)):
                logger.debug("Policy %s 쿨다운 중, 건너뜀", policy_id)
                continue

            # 트리거 조건 평가
            condition = json.loads(policy.get("trigger_condition", "{}"))
            if condition and not self._eval_condition(condition, payload):
                continue

            # 커맨드 페이로드 구성
            template = json.loads(policy.get("command_payload_template", "{}"))
            command_payload = self._resolve_template(template, payload, case_id, tenant_id)

            # 커맨드 발행
            target_service = policy.get("target_service", "core")
            target_command = policy.get("target_command", "")

            await self._publisher.publish(
                event_type=f"POLICY_COMMAND_{target_command.upper()}",
                aggregate_type="Policy",
                aggregate_id=policy_id,
                payload={
                    "case_id": case_id,
                    "command": target_command,
                    "target_service": target_service,
                    "command_payload": command_payload,
                    "triggered_by_event": event_type,
                    "triggered_by_policy": policy_id,
                },
                tenant_id=tenant_id,
            )

            await self._set_cooldown(policy_id, policy.get("cooldown_seconds", 3600))
            logger.info(
                "Policy 실행: %s → %s.%s",
                policy.get("name"), target_service, target_command,
            )

        await self._redis.xack(stream, self._group, msg_id)

    async def _find_matching_policies(self, case_id: str, event_type: str) -> list[dict]:
        """Neo4j에서 매칭되는 활성 Policy 조회"""
        query = """
        MATCH (p:Policy {case_id: $case_id, enabled: true})
        WHERE p.trigger_event = $event_type
        RETURN p
        ORDER BY p.name
        """
        records = await self._neo4j.execute_read(query, {
            "case_id": case_id,
            "event_type": event_type,
        })
        return [dict(r["p"]) for r in records]

    def _eval_condition(self, condition: dict, payload: dict) -> bool:
        """트리거 조건 평가"""
        field = condition.get("field", "")
        op = condition.get("op", "==")
        expected = condition.get("value")
        actual = payload.get(field)

        if actual is None:
            return False
        if op == "==": return actual == expected
        if op == "!=": return actual != expected
        if op == ">":  return float(actual) > float(expected)
        if op == "<":  return float(actual) < float(expected)
        if op == ">=": return float(actual) >= float(expected)
        if op == "<=": return float(actual) <= float(expected)
        return False

    async def _check_cooldown(self, policy_id: str, cooldown_seconds: int) -> bool:
        """쿨다운 확인 — Redis 기반 (워커 재시작/수평 확장 안전)"""
        if cooldown_seconds <= 0:
            return True
        cooldown_key = f"axiom:policy:cooldown:{policy_id}"
        last_raw = await self._redis.get(cooldown_key)
        if not last_raw:
            return True
        last = datetime.fromisoformat(last_raw.decode())
        elapsed = (datetime.now(timezone.utc) - last).total_seconds()
        return elapsed >= cooldown_seconds

    async def _set_cooldown(self, policy_id: str, cooldown_seconds: int) -> None:
        """쿨다운 설정 — Redis SETEX"""
        cooldown_key = f"axiom:policy:cooldown:{policy_id}"
        await self._redis.setex(
            cooldown_key, cooldown_seconds,
            datetime.now(timezone.utc).isoformat(),
        )

    def _resolve_template(
        self, template: dict, payload: dict, case_id: str, tenant_id: str
    ) -> dict:
        """커맨드 페이로드 템플릿의 $trigger 변수 해석"""
        resolved = {}
        for k, v in template.items():
            if isinstance(v, str) and v.startswith("$trigger.payload."):
                key = v[len("$trigger.payload."):]
                resolved[k] = payload.get(key, v)
            elif isinstance(v, dict):
                resolved[k] = self._resolve_template(v, payload, case_id, tenant_id)
            else:
                resolved[k] = v
        resolved.setdefault("case_id", case_id)
        resolved.setdefault("tenant_id", tenant_id)
        return resolved
```

---

## 9. 설계 6: 프론트엔드

### 9.1 도메인 모델러 (ObjectType Modeler)

KAIR의 `ObjectTypeModeler.vue` + BusinessOS의 개념을 React로 구현.

**Feature Slice**: `canvas/src/features/domain-modeler/`

```
features/domain-modeler/
├── api/
│   ├── actionTypeApi.ts              -- ActionType CRUD API
│   ├── policyApi.ts                  -- Policy CRUD API
│   └── documentExtractionApi.ts      -- 문서→온톨로지 추출 API
├── components/
│   ├── DomainModelerLayout.tsx       -- 3패널 레이아웃 (트리 | 캔버스 | 속성)
│   ├── ObjectTypeTree.tsx            -- 좌측: 계층적 ObjectType 트리
│   ├── KineticCanvas.tsx             -- 중앙: ReactFlow 기반 GWT 시각화
│   ├── ActionTypeEditor.tsx          -- 우측: ActionType GWT 편집기
│   ├── PolicyEditor.tsx              -- 우측: Policy 편집기
│   ├── GWTRuleBuilder.tsx            -- GWT Given-When-Then 빌더
│   ├── ConditionRow.tsx              -- Given 조건 행 편집
│   ├── ActionRow.tsx                 -- Then 액션 행 편집
│   ├── DocumentUploadDialog.tsx      -- 문서 업로드 다이얼로그
│   └── ExtractionProgressModal.tsx   -- 추출 진행률 모달
├── hooks/
│   ├── useActionTypes.ts             -- ActionType CRUD + 캐시
│   ├── usePolicies.ts                -- Policy CRUD + 캐시
│   ├── useDocumentExtraction.ts      -- 문서 추출 상태 관리
│   └── useKineticGraph.ts            -- Kinetic Layer 그래프 데이터
├── store/
│   └── useDomainModelerStore.ts      -- Zustand 상태
├── types/
│   └── domainModeler.types.ts        -- TypeScript 타입 정의
└── utils/
    └── gwtValidator.ts               -- GWT 룰 유효성 검사
```

### 9.2 TypeScript 타입 정의

**파일**: `canvas/src/features/domain-modeler/types/domainModeler.types.ts`

```typescript
// === Kinetic Layer 타입 ===

/** GWT Given 조건 */
export interface GWTCondition {
  type: 'state' | 'relation' | 'expression';
  nodeLayer?: string;           // kpi | measure | process | resource
  field?: string;
  op: '==' | '!=' | '>' | '<' | '>=' | '<=' | 'in' | 'not_in' | 'contains';
  value: string | number | boolean | string[];
  // relation 전용
  sourceLayer?: string;
  relType?: string;
  targetLayer?: string;
}

/** GWT Then 액션 */
export interface GWTAction {
  op: 'SET' | 'EMIT' | 'EXECUTE' | 'CREATE_RELATION' | 'DELETE_RELATION';
  targetNode?: string;          // 노드 ID 또는 "$trigger.source_node_id"
  field?: string;               // SET: 변경할 필드
  value?: unknown;              // SET: 새 값
  eventType?: string;           // EMIT: 이벤트 타입
  payload?: Record<string, unknown>;  // EMIT: 페이로드
  actionId?: string;            // EXECUTE: 호출할 ActionType ID
  params?: Record<string, unknown>;   // EXECUTE: 파라미터
}

/** ActionType (GWT 룰) */
export interface ActionType {
  id: string;
  caseId: string;
  tenantId: string;
  name: string;
  description: string;
  layer: 'kinetic';
  enabled: boolean;
  priority: number;
  version: number;
  given: GWTCondition[];
  whenEvent: string;
  then: GWTAction[];
  createdAt: string;
  updatedAt: string;
  // UI 전용
  linkedNodes?: string[];       // 연결된 온톨로지 노드 ID 목록
}

/** Policy (서비스 간 오케스트레이션 룰) */
export interface Policy {
  id: string;
  caseId: string;
  tenantId: string;
  name: string;
  description: string;
  layer: 'kinetic';
  enabled: boolean;
  triggerEvent: string;
  triggerCondition: Record<string, unknown>;
  targetService: string;        // core | synapse | vision | weaver | oracle
  targetCommand: string;
  commandPayloadTemplate: Record<string, unknown>;
  cooldownSeconds: number;
  maxExecutionsPerDay: number;
  createdAt: string;
  updatedAt: string;
}

/** 문서 추출 결과 */
export interface ExtractedEntity {
  name: string;
  entityType: 'aggregate' | 'command' | 'event' | 'policy';
  description: string;
  confidence: number;
  sourceAnchor?: {
    page: number;
    spanStart: number;
    spanEnd: number;
  };
  suggestedLayer: string;
  suggestedRelations: Array<{
    source: string;
    target: string;
    type: string;
    weight: number;
  }>;
}

export interface ExtractionResult {
  docId: string;
  aggregates: ExtractedEntity[];
  commands: ExtractedEntity[];
  events: ExtractedEntity[];
  policies: ExtractedEntity[];
  totalEntities: number;
  avgConfidence: number;
}

/** Event Fork 시뮬레이션 */
export interface SimulationBranch {
  id: string;
  caseId: string;
  name: string;
  description: string;
  baseTimestamp: string;
  status: 'created' | 'running' | 'completed' | 'failed';
  interventions: InterventionSpec[];
  gwtOverrides: Record<string, unknown>;
  resultSummary: Record<string, number> | null;
  eventCount: number;
  createdAt: string;
  completedAt: string | null;
}

export interface InterventionSpec {
  nodeId: string;
  field: string;
  value: number;
  description: string;
}

export interface ScenarioComparison {
  scenarios: Record<string, {
    name: string;
    kpiDeltas: Record<string, number>;
    eventCount: number;
  }>;
  comparisonMatrix: Record<string, Record<string, number>>;
}

// === 3-Layer 필터 ===

export type OntologyLayer = 'semantic' | 'kinetic' | 'dynamic';

export interface LayerFilter {
  semantic: boolean;   // 기존 5계층 노드 표시
  kinetic: boolean;    // ActionType + Policy 표시
  dynamic: boolean;    // SimulationSnapshot 표시
}
```

### 9.3 What-If 5단계 위자드

KAIR의 `WhatIfSimulator.vue` 5단계 패턴을 React로 구현.

**Feature Slice**: `canvas/src/features/whatif-wizard/`

```
features/whatif-wizard/
├── components/
│   ├── WhatIfWizard.tsx              -- 5단계 위자드 컨테이너
│   ├── Step1ScenarioDefine.tsx       -- ① 시나리오 정의 (이름, 설명, 모드 선택)
│   ├── Step2DataSelect.tsx           -- ② 데이터/노드 선택 (온톨로지 브라우저)
│   ├── Step3CausalDiscovery.tsx      -- ③ 인과 관계 발견 (Granger/VAR 실행)
│   ├── Step4Intervention.tsx         -- ④ 개입값 설정 (슬라이더 + 수치 입력)
│   ├── Step5ResultCompare.tsx        -- ⑤ 결과 비교 (base vs simulation)
│   ├── SimulationModeToggle.tsx      -- DAG 모드 vs Event Fork 모드 전환
│   ├── ScenarioTimeline.tsx          -- 이벤트 포크 타임라인 시각화
│   ├── KPIDeltaChart.tsx             -- KPI 변화량 차트
│   └── ScenarioComparisonTable.tsx   -- 시나리오 비교 테이블
├── hooks/
│   ├── useWhatIfWizard.ts            -- 위자드 상태 + 스텝 관리
│   ├── useEventFork.ts               -- Event Fork API 연동
│   └── useScenarioComparison.ts      -- 시나리오 비교 로직
├── store/
│   └── useWhatIfWizardStore.ts       -- Zustand 상태
└── types/
    └── whatifWizard.types.ts         -- TypeScript 타입
```

### 9.4 워크플로 에디터 (Watch Agent 고도화)

KAIR의 `WatchAgent.vue` (Vue Flow) 패턴을 React Flow로 구현.
기존 WatchRule 목록 UI를 시각적 워크플로 에디터로 대체.

**Feature Slice**: `canvas/src/features/workflow-editor/`

```
features/workflow-editor/
├── components/
│   ├── WorkflowEditorLayout.tsx      -- 2패널: 캔버스 | 속성
│   ├── WorkflowCanvas.tsx            -- ReactFlow 기반 워크플로 캔버스
│   ├── WorkflowToolbar.tsx           -- 노드 유형 팔레트 (트리거/조건/액션)
│   ├── nodes/
│   │   ├── TriggerNode.tsx           -- 이벤트 트리거 노드 (이벤트 타입 선택)
│   │   ├── ConditionNode.tsx         -- 조건 노드 (GWT Given 빌더)
│   │   ├── ActionNode.tsx            -- 액션 노드 (SET/EMIT/EXECUTE)
│   │   ├── PolicyNode.tsx            -- 정책 노드 (서비스 간 커맨드)
│   │   └── GatewayNode.tsx           -- 분기 게이트웨이 (AND/OR/XOR)
│   ├── WorkflowPropertyPanel.tsx     -- 선택된 노드/엣지 속성 편집
│   └── WorkflowTestRunner.tsx        -- 드라이런 실행 + 결과 시각화
├── hooks/
│   ├── useWorkflowEditor.ts          -- 워크플로 CRUD
│   └── useWorkflowTestRun.ts         -- 드라이런 실행
├── store/
│   └── useWorkflowEditorStore.ts
└── types/
    └── workflowEditor.types.ts
```

---

## 10. Neo4j 스키마 확장

### 10.1 신규 노드 레이블

```cypher
-- Kinetic Layer 노드
(:ActionType)           -- GWT 룰 정의
(:Policy)               -- 서비스 간 오케스트레이션 정책

-- Dynamic Layer 노드
(:SimulationSnapshot)   -- What-If 시뮬레이션 결과 스냅샷
(:Event)                -- 프로젝션된 이벤트 노드

-- Source Traceability
(:DocFragment)          -- 문서 조각 (소스 앵커)
```

### 10.2 신규 관계 타입

```cypher
-- Kinetic Layer 관계
(:OntologyNode)-[:TRIGGERS]->(:ActionType)      -- 노드가 룰을 트리거
(:ActionType)-[:MODIFIES]->(:OntologyNode)       -- 룰이 노드를 수정
(:ActionType)-[:CHAINS_TO]->(:ActionType)        -- 룰 체이닝
(:ActionType)-[:USES_MODEL]->(:OntologyBehavior:Model)  -- ML 모델 사용

-- Policy 관계
(:OntologyNode)-[:EMITS_TO]->(:Policy)          -- 노드가 정책 트리거
(:Policy)-[:DISPATCHES_TO]->(:OntologyNode)      -- 정책이 커맨드 전달

-- Dynamic Layer 관계
(:OntologyNode)-[:HAS_EVENT]->(:Event)           -- 이벤트 프로젝션
(:SimulationSnapshot)-[:FORKED_FROM]->(:OntologySnapshot)  -- 포크 원점

-- Source Traceability
(:OntologyNode)-[:DERIVED_FROM]->(:DocFragment)  -- 기존 관계 재활용
```

### 10.3 부트스트랩 추가 (neo4j_bootstrap.py 확장)

```python
KINETIC_CONSTRAINTS = [
    # ⚠️ Major #10 수정: Driver 라벨에도 제약조건 추가 (기존 bootstrap에서 누락)
    "CREATE CONSTRAINT driver_id_unique IF NOT EXISTS FOR (d:Driver) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT driver_case_id IF NOT EXISTS FOR (d:Driver) REQUIRE d.case_id IS NOT NULL",
    "CREATE INDEX driver_case_type IF NOT EXISTS FOR (d:Driver) ON (d.case_id, d.type)",

    # ActionType
    "CREATE CONSTRAINT action_type_id_unique IF NOT EXISTS FOR (a:ActionType) REQUIRE a.id IS UNIQUE",
    "CREATE INDEX action_type_case IF NOT EXISTS FOR (a:ActionType) ON (a.case_id)",
    "CREATE INDEX action_type_event IF NOT EXISTS FOR (a:ActionType) ON (a.when_event)",

    # Policy
    "CREATE CONSTRAINT policy_id_unique IF NOT EXISTS FOR (p:Policy) REQUIRE p.id IS UNIQUE",
    "CREATE INDEX policy_case IF NOT EXISTS FOR (p:Policy) ON (p.case_id)",
    "CREATE INDEX policy_trigger IF NOT EXISTS FOR (p:Policy) ON (p.trigger_event)",

    # SimulationSnapshot
    "CREATE CONSTRAINT sim_snapshot_id IF NOT EXISTS FOR (s:SimulationSnapshot) REQUIRE s.id IS UNIQUE",
    "CREATE INDEX sim_snapshot_case IF NOT EXISTS FOR (s:SimulationSnapshot) ON (s.case_id)",

    # Event (프로젝션)
    "CREATE INDEX event_case_type IF NOT EXISTS FOR (e:Event) ON (e.case_id, e.type)",

    # DocFragment
    "CREATE CONSTRAINT docfrag_id IF NOT EXISTS FOR (d:DocFragment) REQUIRE d.id IS UNIQUE",
    "CREATE INDEX docfrag_doc_page IF NOT EXISTS FOR (d:DocFragment) ON (d.doc_id, d.page)",
]

# ALLOWED_LABELS 확장
ALLOWED_LABELS = {
    "Kpi", "Measure", "Process", "Resource", "Driver", "Entity",
    "ActionType", "Policy", "SimulationSnapshot", "Event", "DocFragment",  # 신규
}

# ALLOWED_REL_TYPES 확장
ALLOWED_REL_TYPES = {
    # ... 기존 유지 ...
    "TRIGGERS", "MODIFIES", "CHAINS_TO", "USES_MODEL",                   # Kinetic
    "EMITS_TO", "DISPATCHES_TO",                                          # Policy
    "HAS_EVENT", "FORKED_FROM",                                           # Dynamic
}
```

---

## 11. PostgreSQL 스키마 확장

### 11.1 Vision 스키마

```sql
-- 시뮬레이션 브랜치 (Event Fork)
CREATE TABLE IF NOT EXISTS vision.simulation_branches (
    id              TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    tenant_id       TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    base_timestamp  TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'created',
    interventions   JSONB NOT NULL DEFAULT '[]',
    gwt_overrides   JSONB DEFAULT '{}',
    result_summary  JSONB,
    event_count     INTEGER DEFAULT 0,
    created_by      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    CONSTRAINT uq_sim_branch_name UNIQUE (case_id, name)
);

CREATE INDEX idx_sim_branch_tenant ON vision.simulation_branches(tenant_id, created_at DESC);

-- 시뮬레이션 이벤트 로그
CREATE TABLE IF NOT EXISTS vision.simulation_events (
    id              TEXT PRIMARY KEY,
    branch_id       TEXT NOT NULL REFERENCES vision.simulation_branches(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    aggregate_type  TEXT,
    aggregate_id    TEXT,
    payload         JSONB NOT NULL,
    source          TEXT NOT NULL DEFAULT 'intervention',
    source_rule_id  TEXT,
    state_snapshot  JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_sim_event_seq UNIQUE (branch_id, sequence_number)
);

CREATE INDEX idx_sim_event_branch ON vision.simulation_events(branch_id, sequence_number);
```

### 11.2 Weaver 스키마

```sql
-- 업로드된 문서
CREATE TABLE IF NOT EXISTS weaver.documents (
    id              TEXT PRIMARY KEY,
    case_id         TEXT,                   -- Minor 수정: 온톨로지 연결에 필요
    tenant_id       TEXT NOT NULL,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_size       INTEGER,
    page_count      INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'uploaded',
    storage_path    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_doc_tenant ON weaver.documents(tenant_id, created_at DESC);

-- 문서 프래그먼트
CREATE TABLE IF NOT EXISTS weaver.doc_fragments (
    id              TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES weaver.documents(id) ON DELETE CASCADE,
    page            INTEGER NOT NULL,
    span_start      INTEGER NOT NULL,
    span_end        INTEGER NOT NULL,
    text            TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_frag_doc ON weaver.doc_fragments(doc_id, page);

-- DDD 추출 잡
CREATE TABLE IF NOT EXISTS weaver.extraction_jobs (
    id              TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES weaver.documents(id),
    case_id         TEXT,
    tenant_id       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    progress        INTEGER DEFAULT 0,
    result          JSONB,
    error           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX idx_extraction_doc ON weaver.extraction_jobs(doc_id);
```

---

## 12. API 명세

### 12.1 Synapse API 확장

```
# GWT ActionType CRUD
POST   /api/v3/synapse/kinetic/actions                    -- ActionType 생성
GET    /api/v3/synapse/kinetic/actions?case_id=&enabled=   -- ActionType 목록
GET    /api/v3/synapse/kinetic/actions/{id}                -- ActionType 상세
PUT    /api/v3/synapse/kinetic/actions/{id}                -- ActionType 수정
DELETE /api/v3/synapse/kinetic/actions/{id}                -- ActionType 삭제
POST   /api/v3/synapse/kinetic/actions/{id}/link           -- 온톨로지 노드 연결
POST   /api/v3/synapse/kinetic/actions/{id}/test           -- 드라이런 (시뮬레이션)

# Policy CRUD
POST   /api/v3/synapse/kinetic/policies                   -- Policy 생성
GET    /api/v3/synapse/kinetic/policies?case_id=           -- Policy 목록
PUT    /api/v3/synapse/kinetic/policies/{id}               -- Policy 수정
DELETE /api/v3/synapse/kinetic/policies/{id}               -- Policy 삭제

# 3-Layer 통합 조회
GET    /api/v3/synapse/ontology/cases/{case_id}/layers     -- 3레이어 필터 지원
```

### 12.2 Vision API 확장

```
# Event Fork What-If
POST   /api/v3/vision/whatif-fork/branches                 -- 브랜치 생성
POST   /api/v3/vision/whatif-fork/branches/{id}/simulate   -- 시뮬레이션 실행
GET    /api/v3/vision/whatif-fork/branches/{id}             -- 브랜치 상세 + 결과
GET    /api/v3/vision/whatif-fork/branches/{id}/events      -- 시뮬레이션 이벤트 로그
POST   /api/v3/vision/whatif-fork/compare                   -- 시나리오 비교
DELETE /api/v3/vision/whatif-fork/branches/{id}             -- 브랜치 삭제
```

### 12.3 Weaver API 확장

```
# 문서→온톨로지 추출
POST   /api/v3/weaver/documents/upload                     -- 문서 업로드
POST   /api/v3/weaver/documents/extract                    -- DDD 추출 시작
GET    /api/v3/weaver/documents/extract/status?job_id=     -- 추출 진행률
GET    /api/v3/weaver/documents/extract/result?job_id=     -- 추출 결과
POST   /api/v3/weaver/documents/extract/apply              -- 온톨로지에 적용
```

---

## 13. Phase별 구현 계획 (코드 레벨)

### Phase 1: Kinetic Foundation (2주)

| 일 | 작업 | 파일 | LOC |
|----|------|------|-----|
| D1 | Neo4j 스키마 확장 (ActionType, Policy 제약조건) | `synapse/app/graph/neo4j_bootstrap.py` | ~60 |
| D1 | GWTCondition, GWTAction, GWTRule 데이터클래스 | `synapse/app/services/gwt_engine.py` | ~120 |
| D2 | GWTEngine.load_rules, evaluate_given | `synapse/app/services/gwt_engine.py` | ~200 |
| D3 | GWTEngine.execute_then, handle_event | `synapse/app/services/gwt_engine.py` | ~200 |
| D3 | GWTRuleManager CRUD | `synapse/app/services/gwt_engine.py` | ~150 |
| D4 | GWTConsumerWorker (Redis Stream 소비) | `synapse/app/workers/gwt_consumer.py` | ~120 |
| D5 | Graph Projector 매핑 정의 | `synapse/app/workers/projection_rules.py` | ~200 |
| D6 | GraphProjectorWorker | `synapse/app/workers/graph_projector.py` | ~150 |
| D7 | Synapse Kinetic API 라우터 | `synapse/app/api/kinetic.py` | ~250 |
| D8 | 단위 테스트: GWT Engine + Projector | `synapse/tests/unit/test_gwt_engine.py` | ~300 |
| D9 | 통합 테스트: 이벤트→GWT→프로젝션 E2E | `synapse/tests/integration/test_kinetic_e2e.py` | ~200 |
| D10 | Policy 노드 CRUD + PolicyExecutor 워커 | `core/app/workers/policy_executor.py` | ~250 |

**Phase 1 합계: ~3,000 LOC (백엔드)** *(리뷰 반영: safe_eval, 화이트리스트 검증, 헬스체크 등 추가)*

### Phase 2: Event Fork + Document Pipeline (2주)

| 일 | 작업 | 파일 | LOC |
|----|------|------|-----|
| D1 | PostgreSQL 마이그레이션 (simulation_branches, simulation_events) | `vision/migrations/` | ~50 |
| D2 | EventForkEngine.create_fork, _snapshot_ontology_state | `vision/app/engines/event_fork_engine.py` | ~200 |
| D3 | EventForkEngine.run_simulation (GWT 체인 실행) | `vision/app/engines/event_fork_engine.py` | ~250 |
| D4 | EventForkEngine.compare_scenarios | `vision/app/engines/event_fork_engine.py` | ~100 |
| D5 | Vision Event Fork API 라우터 | `vision/app/api/whatif_fork.py` | ~200 |
| D6 | PostgreSQL 마이그레이션 (documents, doc_fragments, extraction_jobs) | `weaver/migrations/` | ~50 |
| D7 | DocumentService (텍스트 추출 + 청킹) | `weaver/app/services/document_service.py` | ~250 |
| D8 | DDDExtractionService (LLM 추출) | `weaver/app/services/ddd_extraction_service.py` | ~300 |
| D9 | Document Ingestion API 라우터 | `weaver/app/api/document_ingestion.py` | ~200 |
| D10 | 단위/통합 테스트 | `vision/tests/`, `weaver/tests/` | ~400 |

**Phase 2 합계: ~2,500 LOC (백엔드)** *(리뷰 반영: OntologySnapshot 연동, dry-run 로직 등 추가)*

### Phase 3: Frontend (3주)

| 일 | 작업 | 파일 | LOC |
|----|------|------|-----|
| D1-2 | TypeScript 타입 + API 클라이언트 | `features/domain-modeler/types/`, `api/` | ~400 |
| D3-4 | DomainModelerLayout + ObjectTypeTree | `features/domain-modeler/components/` | ~600 |
| D5-6 | GWTRuleBuilder + ConditionRow + ActionRow | `features/domain-modeler/components/` | ~800 |
| D7-8 | ActionTypeEditor + PolicyEditor | `features/domain-modeler/components/` | ~600 |
| D9 | KineticCanvas (ReactFlow) | `features/domain-modeler/components/` | ~400 |
| D10-11 | WhatIfWizard 5단계 (Step1~Step5) | `features/whatif-wizard/components/` | ~1,500 |
| D12-13 | ScenarioTimeline + KPIDeltaChart + ComparisonTable | `features/whatif-wizard/components/` | ~800 |
| D14 | WorkflowCanvas + 노드 컴포넌트 (Trigger/Condition/Action) | `features/workflow-editor/components/` | ~1,000 |
| D15 | 라우트 등록 + 사이드바 메뉴 추가 + i18n | `lib/routes/`, `shared/` | ~200 |

**Phase 3 합계: ~7,000 LOC (프론트엔드)** *(리뷰 반영: 에러 처리, 모드 전환 UI 등 추가)*

### 전체 합계

| Phase | 기간 | 백엔드 LOC | 프론트엔드 LOC | 합계 |
|-------|------|----------|-------------|------|
| Phase 1 | 2주 | ~3,000 | - | ~3,000 |
| Phase 2 | 2주 | ~2,500 | - | ~2,500 |
| Phase 3 | 3주 | - | ~7,000 | ~7,000 |
| **합계** | **7주** | **~5,500** | **~7,000** | **~12,500** |

> **Suggestion 반영**: 초기 추정(10,500 LOC) 대비 ~19% 증가. safe_eval 구현,
> 화이트리스트 검증 로직, OntologySnapshot 연동, Redis 쿨다운, 헬스체크/메트릭
> 엔드포인트, 에러 처리 강화 등이 주요 증가 요인.

---

## 14. 위험 요소 및 완화 전략

### 14.1 기술적 위험

| 위험 | 영향도 | 완화 전략 |
|------|--------|---------|
| GWT Engine eval() 보안 | 높음 | 제한된 표현식 파서 사용 (ast.literal_eval 기반 샌드박스) |
| GWT 무한 루프 (순환 체이닝) | 높음 | MAX_CHAIN_DEPTH=10 + 이미 실행된 룰 추적 (executed_rules set) |
| Graph Projector 지연 | 중간 | Redis Consumer Group으로 수평 확장 (projector-1, projector-2, ...) |
| Neo4j 트랜잭션 충돌 | 중간 | MERGE 패턴 + 재시도 로직 (3회) |
| LLM 추출 정확도 | 중간 | confidence 필터링 (≥0.6) + HITL 검증 UI + 기존 노드 중복 방지 |

### 14.2 아키텍처적 위험

| 위험 | 영향도 | 완화 전략 |
|------|--------|---------|
| 기존 5계층 온톨로지와 충돌 | 높음 | layer 속성으로 구분, 기존 API 100% 호환 유지 |
| Event Fork이 DAG Propagation과 혼동 | 중간 | UI에서 모드 전환 토글 + 각 모드의 장단점 안내 |
| 워커 증가에 따른 운영 복잡도 | 중간 | docker-compose에 통합, 헬스체크 엔드포인트 추가 |

---

## 부록 0: 리뷰 이력 및 수정 사항 (v1.0.0 → v1.2.0)

### 전체 리뷰 이력

| 차수 | 단계 | 리뷰어 | Critical | Major | Minor | 결과 |
|------|------|--------|----------|-------|-------|------|
| 1차 | 설계 문서 v1.0.0 | code-reviewer | 4 | 7 | 6 | 설계 문서 v1.1.0으로 수정 |
| 2차 | Phase 1 코드 테스트 | code-inspector-tester | 1 (field 충돌) | 0 | 0 | gwt_engine.py 즉시 수정 |
| 3차 | Phase 1 코드 종합 | code-reviewer | 3 | 3 | 4 | 코드 6건 즉시 수정 → v1.2.0 |
| 4차 | Phase 1 최종 | pytest 103 tests | 0 | 0 | 0 | All Pass (0.21s) |
| 5차 | Phase 2 코드 종합 | code-reviewer | 3 | 5 | 4 | 코드 8건 즉시 수정 → v1.3.0 |
| 6차 | Phase 3 코드 종합 | code-reviewer | 1 | 4 | 6 | 코드 5건 즉시 수정 → v1.4.0 |
| 7차 | 미반영 8건 구현 | backend+frontend | 0 | 0 | 0 | 8건 전부 구현 |
| **8차** | **전체 종합 재검증** | **code-reviewer** | **0** | **0** | **4 suggestion** | **APPROVED → v2.0.0** |

---

### 1차 리뷰: 설계 문서 (v1.0.0 → v1.1.0)

- **리뷰어**: code-reviewer agent
- **리뷰 일시**: 2026-03-20
- **평가**: Request Changes (Critical 4건, Major 7건, Minor 6건, Suggestion 6건)

### 반영된 Critical 수정 (4건)

| ID | 이슈 | 수정 내용 |
|----|------|---------|
| C1 | Cypher 인젝션 (f-string) | `ALLOWED_LABELS` + `_ALNUM_UNDERSCORE` 화이트리스트 검증 추가. `GWTCondition.validate()`, `GWTAction.validate()` 메서드 도입. `_load_context_states`에도 라벨 검증 적용 |
| C2 | `eval()` 보안 취약점 | `safe_eval()` 함수 도입 — `ast.parse` + `_eval_node` AST 워킹 방식. 허용 노드 화이트리스트(Constant, Name, Compare, BoolOp, UnaryOp, BinOp, Attribute, Subscript)만 처리 |
| C3 | Neo4jClient API 불일치 | `Neo4jClient`에 `execute_read`/`execute_write` 편의 메서드 추가 설계 (기존 `session()` 래핑) |
| C4 | EventPublisher 인터페이스 불일치 | `AsyncEventPublisher` 래퍼 클래스 설계 (Synapse psycopg2 → `asyncio.to_thread()` 래핑). Core EventPublisher는 기존 `session` 기반 시그니처 유지 |

### 반영된 Major 수정 (7건)

| ID | 이슈 | 수정 내용 |
|----|------|---------|
| M5 | Event Fork 시뮬레이션 부작용 | `GWTEngine(dry_run=True)` 모드 도입. dry_run 시 Neo4j SET/이벤트 발행 건너뜀. `EventForkEngine`이 `gwt_engine_factory(dry_run=True)` 사용 |
| M6 | Consumer Group 경합 | 처리 순서 원칙(Projector 먼저 → GWT 이후) 명세. `source_service`/`source_worker` 메타데이터 추가로 자기 소비 방지 |
| M7 | tenant_id 필터 누락 | `load_rules` 쿼리에 `tenant_id` 파라미터 추가. `handle_event` → `load_rules(case_id, tenant_id, event_type)` |
| M8 | update_rule Cypher 인젝션 | `ALLOWED_UPDATE_FIELDS` 화이트리스트 검증 추가 |
| M9 | link_to_ontology 미검증 | `ALLOWED_LINK_REL_TYPES` 화이트리스트 + 라벨 제한 쿼리 (`n:Kpi OR n:Driver OR ...`) |
| M10 | Driver 제약조건 누락 | `KINETIC_CONSTRAINTS`에 Driver 고유성 제약 + case_id NOT NULL + 복합 인덱스 추가 |
| M11 | 시점 스냅샷 미구현 | `_snapshot_ontology_state`가 `OntologySnapshot` 노드를 우선 조회. 없으면 현재 상태 폴백 + 경고 로그 |

### 반영된 Minor/Suggestion (6건)

| ID | 이슈 | 수정 내용 |
|----|------|---------|
| m12 | METADATA_TABLE_DISCOVERED 테넌트 미격리 | `MERGE (t:Table {name: $table_name, datasource_id: $datasource_id})` |
| m14 | PolicyExecutor 쿨다운 인메모리 | Redis SETEX 기반으로 변경 (`axiom:policy:cooldown:{policy_id}`) |
| m16 | weaver.documents에 case_id 없음 | `case_id TEXT` 컬럼 추가 |
| s21 | LOC 과소 추정 | 전체 ~10,500 → ~12,500 LOC로 재추정 (19% 증가) |
| s17 | Graph Projector 실패 시 ACK 문제 | 향후 구현 시 dead-letter 메커니즘 추가 예정 (코드 수준 TODO) |
| s22 | 헬스체크/메트릭 미명세 | 위험 요소 섹션에서 운영 복잡도 완화 전략으로 언급 |

---

### 2차 리뷰: 구현 코드 테스트 (v1.1.0 구현 후)

- **리뷰어**: code-inspector-tester agent
- **리뷰 일시**: 2026-03-20
- **단위 테스트**: 103개 작성, 103개 통과 (0.21s)
- **평가**: Critical 1건 발견 → 즉시 수정

| ID | 이슈 | 수정 내용 |
|----|------|---------|
| T1 | `GWTAction` dataclass에서 `field: str = ""` 속성이 `dataclasses.field` 함수를 섀도잉하여 `TypeError: 'str' object is not callable` 발생 | `from dataclasses import field as dataclass_field`로 import 이름 변경, 모든 `dataclass_field(default_factory=...)` 호출 7곳 수정 |

---

### 3차 리뷰: 구현 코드 종합 리뷰

- **리뷰어**: code-reviewer agent
- **리뷰 일시**: 2026-03-20
- **대상**: 10개 파일 (4,532 LOC)
- **평가**: Request Changes (Critical 3건, Major 3건, Minor 4건, Suggestion 3건, Praise 5건)

#### 반영된 Critical 수정 (3건)

| ID | 이슈 | 수정 파일 | 수정 내용 |
|----|------|---------|---------|
| RC1 | PolicyExecutor `_find_matching_policies`에 `tenant_id` 필터 누락 → 크로스 테넌트 정책 실행 위험 | `core/workers/policy_executor.py` | MATCH 절에 `tenant_id: $tenant_id` 추가, 빈 tenant_id 시 조기 반환 |
| RC2 | `_resolve_ref`의 `getattr(ctx, parts[1])` → 임의 속성 접근으로 정보 유출 위험 | `synapse/services/gwt_engine.py` | `_ALLOWED_TRIGGER_ATTRS` 화이트리스트 (`source_node_id`, `aggregate_id`, `event_type`, `case_id`, `tenant_id`) 추가, 미허용 속성 접근 시 ValueError |
| RC3 | `_eval_state_condition`에서 `$`로 시작하는 `cond.value`가 node_id 해석에만 사용되고 비교값은 리터럴 문자열로 남는 로직 버그 | `synapse/services/gwt_engine.py` | 비교 전 `_resolve_ref(cond.value, ctx)`로 값 해석 추가 |

#### 반영된 Major 수정 (3건)

| ID | 이슈 | 수정 파일 | 수정 내용 |
|----|------|---------|---------|
| RM1 | `_build_event`에 `source_worker` 메타데이터 누락 → GWT Consumer 무한 루프 위험 | `synapse/services/gwt_engine.py` | 이벤트 페이로드에 `"source_worker": "gwt-engine"` 추가 |
| RM2 | `GET /actions/{action_id}` 엔드포인트에 `tenant_id` 검증 없음 → 크로스 테넌트 읽기 | `synapse/api/kinetic.py` | `request: Request` 파라미터 + `_tenant(request)` + MATCH 절 tenant_id 추가 |
| RM3 | `list_action_types`, `list_policies`에서 `tenant_id` 쿼리 파라미터로 다른 테넌트 데이터 조회 가능 | `synapse/api/kinetic.py` | `tenant_id` 쿼리 파라미터 제거, `_tenant(request)`만 사용 |

#### 미반영 (향후 Phase에서 처리)

| ID | 이슈 | 사유 |
|----|------|------|
| RM-defer1 | `execute_read` timeout 미적용 | Neo4j 드라이버 버전별 호환성 확인 후 적용 예정 |
| RM-defer2 | EXECUTE 액션이 실제 체이닝 미수행 (action_id 기록만) | Phase 2에서 체이닝 로직 구현 예정 (TODO 주석 추가됨) |
| RM-defer3 | `_load_context_states`가 전체 레이어 노드 로딩 (성능) | 대규모 케이스 최적화 시 `WHERE n.node_id IN $ids` 스코핑 적용 예정 |
| RM-defer4 | PolicyExecutor `max_executions_per_day` 미구현 | Phase 2에서 Redis 일별 카운터로 구현 예정 |

#### 최종 검증

```
$ python3 -m pytest tests/unit/test_gwt_engine.py --tb=short
============================= 103 passed in 0.21s ==============================
```

모든 Critical/Major 수정 후 기존 103개 테스트 전부 통과 확인.

---

### 5차 리뷰: Phase 2 구현 코드 종합 (v1.2.0 → v1.3.0)

- **리뷰어**: code-reviewer agent
- **리뷰 일시**: 2026-03-20
- **대상**: Phase 2 파일 7개 (2,893 LOC)
- **평가**: Request Changes (Critical 3건, Major 5건, Minor 4건, Suggestion 3건, Praise 4건)

#### 반영된 Critical 수정 (3건)

| ID | 이슈 | 수정 파일 | 수정 내용 |
|----|------|---------|---------|
| RC4 | `_snapshot_ontology_state`에 `tenant_id` 필터 누락 → 크로스 테넌트 온톨로지 유출 | `vision/engines/event_fork_engine.py` | 두 Cypher 쿼리 모두에 `tenant_id` 파라미터 추가 |
| RC5 | Weaver `get_document`/`get_fragments`/`get_job`에 `tenant_id` 필터 누락 → IDOR | `weaver/services/document_service.py` + API 호출부 | 모든 쿼리에 `AND tenant_id = $2` 추가, API에서 `get_effective_tenant_id` 전달 |
| RC6 | 업로드 파일명 경로 순회(Path Traversal) 취약점 | `weaver/services/document_service.py` | `os.path.basename` + regex 정규화 + `os.path.realpath` 검증 |

#### 반영된 Major 수정 (5건)

| ID | 이슈 | 수정 내용 |
|----|------|---------|
| RM4 | `compare_scenarios` tenant 미격리 | `tenant_id` 파라미터 추가 (방어적 심층 방어) |
| RM5 | 파일 업로드 확장자 미검증 | `ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md", "csv"}` 화이트리스트 |
| RM6 | 매 DB 호출마다 `psycopg2.connect()` → 커넥션 풀 고갈 | TODO 주석 추가 (Phase 3에서 `ThreadedConnectionPool` 도입 예정) |
| RM7 | 추출 잡 status/result 엔드포인트 tenant 미검증 | `get_effective_tenant_id` Depends 추가 |
| RM8 | `_LightweightGWTEvaluator` 룰 캐시 무한 유지 | TTL 300초 기반 캐시 만료 추가 (`time.monotonic()`) |

#### 미반영 (향후 처리)

| ID | 이슈 | 사유 |
|----|------|------|
| RM6-full | 커넥션 풀 도입 | Phase 3에서 `psycopg2.pool.ThreadedConnectionPool` 적용 예정 |
| m10 | `_import_psycopg2` 코드 중복 (DRY) | 리팩토링 단계에서 `app.db.pg_utils`로 추출 예정 |
| m11 | `sim_state` shallow copy → `copy.deepcopy` 필요 | 성능 영향 분석 후 적용 예정 |

---

### 6차 리뷰: Phase 3 프론트엔드 종합 (v1.3.0 → v1.4.0)

- **리뷰어**: code-reviewer agent
- **리뷰 일시**: 2026-03-20
- **대상**: Phase 3 파일 36개 (~3,500 LOC)
- **평가**: Request Changes (Critical 1건, Major 4건, Minor 6건, Suggestion 4건, Praise 5건)

#### 반영된 Critical 수정 (1건)

| ID | 이슈 | 수정 내용 |
|----|------|---------|
| FC1 | `WorkflowEditorLayout.tsx`에서 `React.FC` 사용하나 `React` import 누락 → 빌드 실패 | `React.FC` → `export function` 패턴으로 변경 (프로젝트 컨벤션 준수) |

#### 반영된 Major 수정 (4건)

| ID | 이슈 | 수정 내용 |
|----|------|---------|
| FM1 | `useWhatIfWizard`의 `useCallback` deps에 전체 store 객체 → stale closure | `useCallback` 제거, `getState()` 패턴으로 전환 |
| FM2 | `useDomainModelerStore`의 `error` 공유 → `useActionTypes`/`usePolicies` 간 토스트 레이스 | `actionTypeError`/`policyError`로 분리 |
| FM3 | `WorkflowCanvas`의 Cytoscape가 nodes/edges 변경마다 전체 재생성 | 초기화 1회 + diff 기반 add/remove/update 분리 |
| FM4 | `WorkflowCanvas`의 `setSelectedNode` deps 누락 | ref 패턴으로 변경 (`setSelectedNodeRef.current`) |

#### 미반영 (후속 작업)

| ID | 이슈 | 사유 |
|----|------|------|
| m-i18n | domain-modeler, workflow-editor i18n 미적용 | **해결됨** (7차에서 ~70키 추가) |
| m-test | 프론트엔드 단위 테스트 없음 | Vitest + React Testing Library로 후속 작성 예정 |
| m-demo | Step3/Step5에 하드코딩된 `demo_manufacturing` caseId | **해결됨** (7차에서 store 기반으로 변경) |

---

### 7차: 미반영 8건 구현 (v1.4.0 → v2.0.0)

- **구현 일시**: 2026-03-20
- **대상**: 이전 리뷰에서 "향후 처리"로 분류된 8건 전부

| # | 미반영 항목 | 구현 내용 | 파일 |
|---|-----------|---------|------|
| 1 | i18n 일괄 적용 | domain-modeler 8개 + workflow-editor 3개 파일에 `t()` 적용, ko/en JSON ~70키 추가 | 11개 컴포넌트 + 2 JSON |
| 2 | psycopg2 커넥션 풀 | `pg_utils.py` 신규 — `ThreadedConnectionPool` (minconn=2, maxconn=10), double-check locking | `vision/db/pg_utils.py` |
| 3 | EXECUTE 체이닝 | 재귀 `execute_then` + `executed_rule_ids` 순환 방지 + `MAX_CHAIN_DEPTH` 준수 | `gwt_engine.py` |
| 4 | _load_context_states 최적화 | `WHERE n.node_id IN $node_ids` 스코핑, 조건/액션에서 참조 노드 ID 수집 | `gwt_engine.py` |
| 5 | max_executions_per_day | Redis INCR + EXPIRE 86400 패턴, 일별 키 `axiom:policy:daily:{id}:{YYYY-MM-DD}` | `policy_executor.py` |
| 6 | sim_state deepcopy | `copy.deepcopy(base_state)` 적용 | `event_fork_engine.py` |
| 7 | _import_psycopg2 DRY | `pg_utils.py`로 추출, simulation_schema/event_fork_engine/whatif_fork에서 import | 4개 파일 |
| 8 | caseId 파라미터화 | store에 `caseId` 추가, WhatIfWizardPage2에서 URL→store 연동, Step3/Step5에서 store 참조 | 4개 파일 |

---

### 8차 리뷰: 최종 종합 재검증 (v2.0.0)

- **리뷰어**: code-reviewer agent
- **리뷰 일시**: 2026-03-20
- **대상**: Phase 1+2+3 + 미반영 8건 전체
- **평가**: **APPROVED** (Critical 0건, Major 0건, Suggestion 4건)

#### 보안 체크리스트 (전체 통과)

| 항목 | 상태 |
|------|------|
| eval() 제거 → safe_eval만 사용 | PASS |
| f-string Cypher → ALLOWED_LABELS 검증 | PASS |
| 전 API 엔드포인트 tenant_id 격리 | PASS |
| 파일 업로드 경로 순회 방지 | PASS |
| SQL 파라미터화 (인젝션 방지) | PASS |
| _resolve_ref 속성 화이트리스트 | PASS |

#### 아키텍처 체크리스트 (전체 통과)

| 항목 | 상태 |
|------|------|
| Neo4jClient execute_read/execute_write | PASS |
| 서비스별 EventPublisher 패턴 준수 | PASS |
| Vision 커넥션 풀링 (ThreadedConnectionPool) | PASS |
| EXECUTE 액션 재귀 체이닝 + 순환 방지 | PASS |
| max_executions_per_day 일별 제한 | PASS |
| _load_context_states 노드 ID 스코핑 | PASS |
| sim_state deepcopy | PASS |

#### 남은 Suggestion (비차단, 4건)

1. `_eval_state_condition`/`_eval_relation_condition` Cypher에 `tenant_id` 추가 (방어적 심층 방어)
2. Step3/Step5에 일부 한국어 하드코딩 잔존 (~25개 문자열)
3. `pg_utils.py`에 `close_pool()` shutdown 훅 추가
4. `_load_chained_rule`에 `case_id` 필터 추가

---

## 부록 A: BusinessOS 프로젝트별 참조 매핑

| BusinessOS 프로젝트 | 핵심 개념 | Axiom 적용 위치 |
|-------------------|---------|--------------|
| **business-os** | 3-Layer 온톨로지, GWT Rule Engine, Ontology Builder | Synapse Kinetic Layer |
| **ontosys-main** | 문서→DDD 추출, DocFrag 트레이서빌리티, VueFlow 시각화 | Weaver 문서 파이프라인 + Canvas 도메인 모델러 |
| **Businessosdevelopmentplan** | Event Sourcing, What-If 브랜칭, GWT Interpreter | Vision Event Fork Engine |
| **팔란티어 PDF** | Semantic/Kinetic/Dynamic 개념 정의, Cypher DSL 패턴 | 전체 아키텍처 프레임워크 |

---

## 부록 B: 기존 Axiom 코드와의 호환성 매트릭스

| 기존 코드 | 변경 필요 여부 | 변경 내용 |
|---------|-----------|---------|
| `neo4j_bootstrap.py` | 추가 | KINETIC_CONSTRAINTS 배열 + ALLOWED_LABELS/REL_TYPES 확장 |
| `ontology_service.py` | 수정 없음 | 기존 CRUD 100% 호환 |
| `base_models.py` (Core) | 수정 없음 | EventOutbox 구조 그대로 유지 |
| `sync.py` (Core) | 수정 없음 | Relay Worker 변경 없음 |
| `whatif_dag_engine.py` | 수정 없음 | 기존 DAG 모드 유지, Fork 모드는 별도 엔진 |
| `routeConfig.tsx` | 추가 | 도메인 모델러, What-If 위자드 라우트 추가 |
| `routes.ts` | 추가 | ROUTES.DOMAIN_MODELER, ROUTES.WHATIF_WIZARD |
