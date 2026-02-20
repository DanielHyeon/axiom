# 온톨로지 데이터 모델 상세

## 이 문서가 답하는 질문

- 온톨로지 데이터의 의미론적 정의는?
- 데이터의 생명주기(생성 -> 사용 -> 폐기)는?
- 데이터 품질 기준은 무엇인가?
- PostgreSQL과 Neo4j 간 데이터 분배 전략은?

<!-- affects: backend, api, llm -->
<!-- requires-update: 06_data/neo4j-schema.md -->

---

## 1. 데이터 의미론

### 1.1 온톨로지 노드의 의미

| 계층 | 의미론적 정의 | 현실 세계 대응 |
|------|-------------|--------------|
| **Resource** | "프로젝트에 존재하는 것" | 사람, 회사, 자산, 계약 - 물리적/조직적으로 존재하는 실체 |
| **Process** | "프로젝트에서 일어나는 것" | 비즈니스 프로세스, 활동, 의사결정 - 시간 축 위의 사건 |
| **Measure** | "프로세스에서 측정되는 것" | 금액, 건수, 비율 - 프로세스 실행의 정량적 결과 |
| **KPI** | "프로젝트의 성과를 나타내는 것" | 효율성, 비용 절감률, ROI - 전략적 의사결정 기준 |

### 1.2 관계의 의미

| 관계 | 의미론적 정의 | 해석 |
|------|-------------|------|
| `PARTICIPATES_IN` | "X가 Y에 참여한다" | 조직이 프로세스에 참여 |
| `PRODUCES` | "X가 Y를 산출한다" | 프로세스 분석 단계가 매출 지표를 산출 |
| `CONTRIBUTES_TO` | "X가 Y에 기여한다" | 매출이 프로세스 효율성에 기여 |
| `DEPENDS_ON` | "X가 Y에 의존한다" | 프로세스 효율성이 비용 지표에 의존 |
| `INFLUENCES` | "X가 Y에 영향을 미친다" | 최적화 프로세스가 비용 절감률에 영향 |

---

## 2. 데이터 생명주기

### 2.1 노드 생명주기

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  생성     │────▶│  활성     │────▶│  갱신     │────▶│  보관     │
│ (Create)  │     │ (Active)  │     │ (Update)  │     │ (Archive) │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

| 단계 | 트리거 | 설명 |
|------|-------|------|
| **생성** | 수동 입력, 자동 인제스트, 문서 추출 | `source` 필드로 생성 경로 추적 |
| **활성** | 생성 완료 | 검색/조회에 포함됨 |
| **갱신** | 케이스 데이터 변경, HITL 수정, 재추출 | `updated_at` 갱신, 이전 값 이력 없음 |
| **보관** | 프로젝트 종결 | 검색에서 제외, 통계용 보존 |

### 2.2 생성 경로별 특성

| source | 생성자 | confidence | verified | 사용 시나리오 |
|--------|-------|-----------|---------|-------------|
| `manual` | 사람 (UI) | 1.0 | true | 프로세스 분석가가 직접 입력 |
| `ingested` | 자동 인제스트 | 1.0 | true | 케이스 데이터 자동 변환 |
| `extracted` | LLM 추출 | 0.0-1.0 | false (HITL 후 true) | 비정형 문서에서 추출 |
| `calculated` | 시스템 계산 | 1.0 | true | KPI 자동 계산 |

### 2.3 HITL 검토 생명주기

```
extracted (LLM 추출)
    │
    ├─ confidence >= 0.75 → auto_committed → verified=false (자동 반영)
    │                           │
    │                           └─ 관리자 확인 → verified=true
    │
    └─ confidence < 0.75 → pending_review (HITL 대기열)
                               │
                               ├─ APPROVE → committed → verified=true
                               ├─ MODIFY  → committed (수정) → verified=true
                               └─ REJECT  → deleted (삭제)
```

---

## 3. PostgreSQL vs Neo4j 데이터 분배

### 3.1 분배 원칙

| 저장소 | 저장 대상 | 이유 |
|--------|----------|------|
| **Neo4j** | 온톨로지 노드, 관계, 벡터 임베딩 | 그래프 탐색 성능, 경로 분석 |
| **PostgreSQL** | 추출 작업 상태, HITL 큐, 프롬프트 버전 | 트랜잭션 일관성, CRUD 성능 |

### 3.2 PostgreSQL 테이블 (Synapse 전용)

```sql
-- Extraction task tracking
CREATE TABLE extraction_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id UUID NOT NULL,
    case_id UUID NOT NULL,
    org_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    -- queued, processing, completed, failed, partially_completed
    options JSONB,              -- extraction options
    progress JSONB,             -- step-by-step progress
    result_summary JSONB,       -- entity/relation counts
    error_message TEXT,
    prompt_versions JSONB,      -- {"ner": "1.0.0", "relation": "1.0.0"}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Extracted entities (staging before Neo4j commit)
CREATE TABLE extracted_entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES extraction_tasks(id),
    case_id UUID NOT NULL,
    entity_text TEXT NOT NULL,
    entity_type VARCHAR(30) NOT NULL,
    normalized_value TEXT,
    confidence FLOAT NOT NULL,
    context TEXT,
    source_chunk INTEGER,
    ontology_mapping JSONB,     -- {"layer": "resource", "label": "Company:Resource"}
    neo4j_node_id VARCHAR(50),  -- NULL until committed
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, committed, pending_review, rejected
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Extracted relations (staging)
CREATE TABLE extracted_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES extraction_tasks(id),
    case_id UUID NOT NULL,
    subject_entity_id UUID REFERENCES extracted_entities(id),
    predicate VARCHAR(30) NOT NULL,
    object_entity_id UUID REFERENCES extracted_entities(id),
    confidence FLOAT NOT NULL,
    evidence TEXT,
    ontology_mapping JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HITL review queue
CREATE TABLE hitl_review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES extracted_entities(id),
    case_id UUID NOT NULL,
    priority INTEGER DEFAULT 0,  -- higher = more urgent
    assigned_to UUID,            -- reviewer user ID
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending, in_review, completed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
```

### 3.3 데이터 동기화

```
PostgreSQL (extracted_entities)           Neo4j (ontology nodes)
    status=committed          ───▶      MERGE node
    status=pending_review     ───▶      (not in Neo4j yet)
    status=rejected           ───▶      (not in Neo4j)

PostgreSQL은 "진실의 원천(source of truth)"이 아니라 "스테이징 영역"이다.
Neo4j가 온톨로지의 최종 저장소이다.
```

---

## 4. 데이터 품질 기준

### 4.1 노드 품질

| 기준 | 측정 | 목표 |
|------|------|------|
| **완전성** | 필수 속성 (name, type, case_id) 존재 비율 | 100% |
| **정확성** | verified=true 노드 비율 | > 90% |
| **신뢰도** | 전체 노드 평균 confidence | > 0.85 |
| **고아 노드** | 관계가 하나도 없는 노드 비율 | < 10% |

### 4.2 관계 품질

| 기준 | 측정 | 목표 |
|------|------|------|
| **방향 정확성** | 계층 규칙 준수 비율 | 100% |
| **연결 밀도** | 노드당 평균 관계 수 | > 2.0 |
| **순환 없음** | 계층 간 순환 관계 | 0건 |

### 4.3 품질 모니터링 쿼리

```cypher
// Orphan nodes (no relations)
MATCH (n {case_id: $case_id})
WHERE (n:Resource OR n:Process OR n:Measure OR n:KPI)
AND NOT (n)-[]-()
RETURN labels(n) AS type, n.name AS name, n.id AS id

// Low confidence nodes
MATCH (n {case_id: $case_id})
WHERE n.confidence < 0.75 AND n.verified = false
RETURN labels(n) AS type, n.name AS name, n.confidence AS confidence
ORDER BY n.confidence ASC

// Layer direction violations
MATCH (r:Resource)-[rel]->(k:KPI)
WHERE type(rel) NOT IN ['CONTRIBUTES_TO']
RETURN r.name, type(rel), k.name
```

---

## 5. 데이터 보존 정책

| 데이터 유형 | 보존 기간 | 삭제 조건 |
|-----------|----------|----------|
| 활성 프로젝트 온톨로지 | 무기한 | 프로젝트 종결 + 보관 전환 |
| 종결 프로젝트 온톨로지 | 10년 | 보존 기간 만료 |
| 추출 작업 상태 | 1년 | 작업 완료 후 1년 |
| HITL 검토 이력 | 프로젝트 보존 기간과 동일 | 감사 추적 목적 |
| 프롬프트 버전 | 무기한 | 결과 재현 가능성 보장 |

---

---

## 6. EventStorming → 온톨로지 자동 변환 규칙

### 6.1 변환 개요

EventStorming 캔버스에서 설계된 프로세스 모델을 4계층 온톨로지 노드로 자동 변환한다. 이 변환은 Canvas에서 EventStorming 모델을 저장할 때 자동으로 실행된다.

```
EventStorming Canvas (JSON)
    │
    ▼ 파싱 + 매핑
    │
    ├─ Actor/Aggregate → Resource 계층
    ├─ Command → BusinessAction:Process
    ├─ Event → BusinessEvent:Process (+ 시간축 속성)
    ├─ Policy → BusinessRule:Process
    ├─ Event Chain → Measure 자동 산출
    └─ Measure 집계 → KPI 연결
```

### 6.2 노드 변환 규칙

| # | EventStorming 개념 | 변환 조건 | 온톨로지 노드 | 속성 매핑 |
|---|-------------------|----------|------------|----------|
| 0 | ContextBox | 항상 | 그래프 내 라벨/그룹 태그 | name → domain_name, nodes WITHIN this domain get domain_id tag |
| 1 | Actor | 항상 | `:Employee:Resource` 또는 `:Company:Resource` | name → name, role → position |
| 2 | Aggregate | 항상 | `:Asset:Resource` 또는 `:Inventory:Resource` | name → name, state → description |
| 3 | Command | 항상 | `:BusinessAction:Process` | name → name, actor → actor_id |
| 4 | Domain Event | 항상 | `:BusinessEvent:Process` | name → name, timestamp → timestamp, duration → duration |
| 5 | Policy | 항상 | `:BusinessRule:Process` | name → name, condition → condition, is_automated=true |
| 6 | External System | 항상 | `:Resource` | name → name, type="ExternalSystem" |
| 7 | Read Model | Measure 바인딩 시 | `:Measure` (하위 유형) | name → name, value → amount |

### 6.3 관계 변환 규칙

| # | EventStorming 관계 | 변환 결과 | 속성 매핑 |
|---|-------------------|----------|----------|
| 1 | Actor → Command | `(:Resource)-[:TRIGGERS]->(:BusinessAction)` | role="initiator" |
| 2 | Command → Event | `(:BusinessAction)-[:PRODUCES]->(:BusinessEvent)` | - |
| 3 | Event → Policy | `(:BusinessEvent)-[:ACTIVATES]->(:BusinessRule)` | - |
| 4 | Policy → Command | `(:BusinessRule)-[:TRIGGERS]->(:BusinessAction)` | - |
| 5 | Event → Event (순서) | `(:BusinessEvent)-[:FOLLOWED_BY]->(:BusinessEvent)` | avg_duration, case_count |
| 6 | Event → Read Model | `(:BusinessEvent)-[:PRODUCES]->(:Measure)` | calculation |
| 7 | Aggregate → Command | `(:Resource)-[:PARTICIPATES_IN]->(:BusinessAction)` | role="aggregate" |

### 6.4 Measure 자동 산출 규칙

Event 체인이 완료되면, 해당 체인에서 Measure 노드가 자동 생성된다.

| Event 패턴 | 산출 Measure | 산출 공식 |
|-----------|------------|----------|
| 시작 Event → 종료 Event | CycleTime | end_time - start_time |
| 이벤트 발생 건수 | Throughput | COUNT(event) / period |
| SLA 위반 건수 / 전체 건수 | SLA 준수율 | 1 - (violation_count / total_count) |
| 특정 Event 발생율 | 완료율 | completed_count / total_count |

### 6.5 시간축 속성 자동 바인딩

EventStorming 모델의 각 Event에 이벤트 로그를 바인딩하면, 시간축 속성이 자동으로 계산된다.

```python
# Pseudo-code: temporal property auto-calculation
async def bind_event_log_to_event(
    event_id: str,
    log_id: str,
    source_table: str,
    source_event: str,
    timestamp_column: str,
    case_id_column: str
):
    # 1. Create BINDS_TO relationship
    # 2. Query event log for matching events
    # 3. Calculate temporal properties
    actual_avg_duration = calculate_avg_duration(log_entries)
    violation_rate = calculate_sla_violations(log_entries, sla_threshold)

    # 4. Update BusinessEvent node
    update_temporal_properties(event_id, actual_avg_duration, violation_rate)
```

### 6.6 변환 신뢰도

| 변환 유형 | 기본 신뢰도 | 근거 |
|----------|----------|------|
| 수동 입력 (Canvas) | 1.0 | 사용자가 직접 설계 |
| 자동 Measure 산출 | 0.9 | 규칙 기반 자동 생성 |
| 이벤트 로그 기반 시간축 | 1.0 | 실제 데이터에서 계산 |
| LLM 추출 EventStorming | 0.0-1.0 | LLM 신뢰도에 따름 |

---

## 근거 문서

- `06_data/neo4j-schema.md` (Neo4j 스키마)
- `01_architecture/ontology-4layer.md` (4계층 구조)
- `01_architecture/process-mining-engine.md` (Process Mining Engine)
- `07_security/data-access.md` (접근 제어)
- ADR-005: pm4py Process Mining 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
