# 비정형 문서 추출 API

> 구현 상태 태그: `Implemented`
> 기준일: 2026-02-21

## 이 문서가 답하는 질문

- 비정형 문서에서 온톨로지를 추출하는 API 호출 흐름은?
- 비동기 추출 작업의 상태를 어떻게 조회하는가?
- HITL 검토 API는 어떻게 사용하는가?
- 추출 결과의 신뢰도 필터링은 어떻게 동작하는가?

<!-- affects: frontend, llm, backend -->
<!-- requires-update: 01_architecture/extraction-pipeline.md, 05_llm/entity-extraction.md -->

---

## 1. 기본 정보

| 항목 | 값 |
|------|---|
| Base URL | `/api/v3/synapse/extraction` |
| 인증 | JWT Bearer Token (Core 경유) |
| 비동기 작업 | task_id 기반, 폴링 또는 SSE로 상태 확인 |

---

## 2. 엔드포인트 목록

| Method | Path | 설명 | 상태 | 근거(구현/티켓) |
|--------|------|------|------|------------------|
| POST | `/documents/{doc_id}/extract-ontology` | 비동기 추출 작업 시작 | Implemented | `services/synapse/app/api/extraction.py` |
| GET | `/documents/{doc_id}/ontology-status` | 추출 진행 상태 | Implemented | `services/synapse/app/api/extraction.py` |
| GET | `/documents/{doc_id}/ontology-result` | 추출 결과 조회 | Implemented | `services/synapse/app/api/extraction.py` |
| PUT | `/ontology/{entity_id}/confirm` | HITL: 개별 개체 확인/수정 | Implemented | `services/synapse/app/api/extraction.py` |
| POST | `/cases/{case_id}/ontology/review` | HITL: 일괄 검토 | Implemented | `services/synapse/app/api/extraction.py` |
| GET | `/cases/{case_id}/review-queue` | HITL: 검토 대기열 | Implemented | `services/synapse/app/api/extraction.py` |
| POST | `/documents/{doc_id}/retry` | 실패한 추출 재시도 | Implemented | `services/synapse/app/api/extraction.py` |
| POST | `/documents/{doc_id}/revert-extraction` | Saga 보상: 추출 결과 되돌리기 | Implemented | `services/synapse/app/api/extraction.py` |

---

## 3. 엔드포인트 상세

### 3.1 POST /documents/{doc_id}/extract-ontology

비정형 문서에서 온톨로지 추출을 시작한다. 비동기 작업이며, 즉시 task_id를 반환한다.

#### Request

```json
POST /api/v3/synapse/extraction/documents/doc-uuid-001/extract-ontology
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "options": {
    "extract_entities": true,
    "extract_relations": true,
    "auto_map_ontology": true,
    "auto_commit_threshold": 0.75,
    "chunk_size": 800,
    "chunk_overlap": 100,
    "max_entities_per_chunk": 50,
    "target_entity_types": [
      "COMPANY", "PERSON", "DEPARTMENT", "AMOUNT", "DATE",
      "ASSET_TYPE", "PROCESS_STEP", "METRIC", "CONTRACT",
      "FINANCIAL_METRIC", "REFERENCE"
    ]
  }
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|-------|------|
| `case_id` | uuid | Y | - | 프로젝트 ID |
| `options.extract_entities` | bool | N | true | NER 수행 여부 |
| `options.extract_relations` | bool | N | true | 관계 추출 수행 여부 |
| `options.auto_map_ontology` | bool | N | true | 온톨로지 자동 매핑 여부 |
| `options.auto_commit_threshold` | float | N | 0.75 | 자동 반영 임계값 |
| `options.chunk_size` | int | N | 800 | 청킹 크기 (토큰) |
| `options.chunk_overlap` | int | N | 100 | 청킹 오버랩 (토큰) |
| `options.max_entities_per_chunk` | int | N | 50 | 청크당 최대 개체 수 |
| `options.target_entity_types` | array | N | all | 추출 대상 개체 유형 |

**지원 개체 유형 (SSOT)**: `COMPANY`, `PERSON`, `DEPARTMENT`, `AMOUNT`, `DATE`, `ASSET_TYPE`, `PROCESS_STEP`, `METRIC`, `CONTRACT`, `FINANCIAL_METRIC`, `REFERENCE`. 총 11종. 이 목록의 정규 정의는 [extraction-pipeline.md](../01_architecture/extraction-pipeline.md) §3 JSON Schema enum이다. 각 유형의 정의와 추출 난이도는 [entity-extraction.md](../05_llm/entity-extraction.md) §1을 참조한다.

#### Response (202 Accepted)

```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid-001",
    "doc_id": "doc-uuid-001",
    "case_id": "550e8400-e29b-41d4-a716-446655440001",
    "status": "queued",
    "created_at": "2024-06-16T10:00:00Z",
    "estimated_duration_seconds": 120
  }
}
```

---

### 3.2 GET /documents/{doc_id}/ontology-status

추출 작업의 진행 상태를 조회한다.

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid-001",
    "doc_id": "doc-uuid-001",
    "status": "processing",
    "progress": {
      "current_step": "ner_extraction",
      "steps": [
        {"name": "text_extraction", "status": "completed", "duration_ms": 2500},
        {"name": "chunking", "status": "completed", "duration_ms": 150, "chunk_count": 12},
        {"name": "ner_extraction", "status": "in_progress", "progress": "8/12 chunks"},
        {"name": "relation_extraction", "status": "pending"},
        {"name": "ontology_mapping", "status": "pending"},
        {"name": "neo4j_commit", "status": "pending"},
        {"name": "hitl_queue", "status": "pending"}
      ]
    },
    "started_at": "2024-06-16T10:00:05Z",
    "updated_at": "2024-06-16T10:01:30Z"
  }
}
```

#### 상태 값

| status | 의미 |
|--------|------|
| `queued` | 대기열에 추가됨 |
| `processing` | 처리 중 |
| `completed` | 추출 완료 (HITL 대기 항목 있을 수 있음) |
| `failed` | 실패 |
| `partially_completed` | 일부 단계 실패 (부분 결과 있음) |

#### Task 상태 vs Entity 상태

추출 API에는 두 가지 독립적인 상태 체계가 존재한다. **Task 상태**는 추출 작업 전체의 진행을, **Entity 상태**는 개별 추출 결과의 반영 여부를 나타낸다.

| Task 상태 (§3.2) | 의미 | 연관 Entity 상태 (§3.3) |
|:----------------:|------|:----------------------:|
| `queued` | 대기열 진입 | — (아직 Entity 없음) |
| `processing` | NER/관계추출 진행 중 | — (아직 Entity 없음) |
| `completed` | 추출 완료 | `committed` (≥ threshold), `pending_review` (< threshold) |
| `failed` | 전체 실패 | — (Entity 미생성) |
| `partially_completed` | 일부 단계 실패 | `committed`, `pending_review` (성공 청크만) |

| Entity 상태 (§3.3 status 필터) | 의미 | 전이 조건 |
|:-----------------------------:|------|----------|
| `committed` | Neo4j에 반영됨 | confidence ≥ `auto_commit_threshold` |
| `pending_review` | HITL 검토 대기 | confidence < `auto_commit_threshold` |
| `rejected` | HITL 거부 | §3.4 `action: "reject"` |
| `reverted` | Saga 보상으로 되돌림 | §3.7 revert-extraction |

---

### 3.3 GET /documents/{doc_id}/ontology-result

추출 결과를 조회한다.

#### Query Parameters

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|-------|------|
| `min_confidence` | float | 0.0 | 최소 신뢰도 필터 |
| `include_rejected` | bool | false | HITL에서 거부된 항목 포함 |
| `status` | string | all | committed, pending_review, rejected |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "task_id": "task-uuid-001",
    "doc_id": "doc-uuid-001",
    "extraction_summary": {
      "total_entities": 35,
      "total_relations": 28,
      "auto_committed": 22,
      "pending_review": 10,
      "rejected": 3,
      "average_confidence": 0.82
    },
    "entities": [
      {
        "id": "entity-uuid-001",
        "text": "XYZ 주식회사",
        "entity_type": "COMPANY",
        "normalized_value": "XYZ 주식회사",
        "confidence": 0.98,
        "ontology_mapping": {
          "layer": "resource",
          "label": "Company:Resource",
          "neo4j_node_id": "node-uuid-mapped"
        },
        "status": "committed",
        "source_chunk": 1,
        "context": "대상 조직 XYZ 주식회사는 2024년 1월..."
      },
      {
        "id": "entity-uuid-015",
        "text": "분석가 김모",
        "entity_type": "PERSON",
        "normalized_value": "김모",
        "confidence": 0.65,
        "ontology_mapping": null,
        "status": "pending_review",
        "source_chunk": 5,
        "context": "프로세스 분석가 김모는 분석 보고서에서..."
      }
    ],
    "relations": [
      {
        "id": "rel-uuid-001",
        "subject": "entity-uuid-001",
        "predicate": "INITIATED_PROCESS",
        "object": "entity-uuid-003",
        "confidence": 0.97,
        "ontology_mapping": {
          "relation_type": "PARTICIPATES_IN",
          "source_layer": "resource",
          "target_layer": "process"
        },
        "status": "committed",
        "evidence": "대상 조직 XYZ 주식회사는 2024년 1월 15일 프로세스 분석을 개시하였다."
      }
    ]
  }
}
```

---

### 3.4 PUT /ontology/{entity_id}/confirm

HITL 검토자가 개별 추출 개체를 확인/수정/거부한다.

#### Request: 승인

```json
PUT /api/v3/synapse/extraction/ontology/entity-uuid-015/confirm
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "action": "approve",
  "reviewer_id": "user-uuid-reviewer"
}
```

#### Request: 수정 후 승인

```json
{
  "action": "modify",
  "modifications": {
    "entity_type": "PERSON",
    "normalized_value": "김철수",
    "ontology_mapping": {
      "layer": "resource",
      "label": "Employee:Resource",
      "properties": {
        "position": "프로세스 분석가"
      }
    }
  },
  "reviewer_id": "user-uuid-reviewer"
}
```

#### Request: 거부

```json
{
  "action": "reject",
  "reason": "해당 인물은 이 프로젝트와 무관한 참고인입니다",
  "reviewer_id": "user-uuid-reviewer"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `action` | string | Y | approve, modify, reject |
| `modifications` | object | modify 시 Y | 수정 내용 |
| `reason` | string | reject 시 Y | 거부 사유 |
| `reviewer_id` | uuid | Y | 검토자 ID |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "entity_id": "entity-uuid-015",
    "action": "modify",
    "status": "committed",
    "neo4j_node_id": "node-uuid-new",
    "reviewed_at": "2024-06-16T14:00:00Z",
    "reviewer_id": "user-uuid-reviewer"
  }
}
```

---

### 3.5 POST /cases/{case_id}/ontology/review

여러 개체를 일괄 검토한다.

#### Request

```json
POST /api/v3/synapse/extraction/cases/550e8400-e29b-41d4-a716-446655440001/ontology/review
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "reviews": [
    {"entity_id": "entity-uuid-015", "action": "approve"},
    {"entity_id": "entity-uuid-016", "action": "reject", "reason": "오인식"},
    {"entity_id": "entity-uuid-017", "action": "modify", "modifications": {"normalized_value": "수정값"}}
  ],
  "reviewer_id": "user-uuid-reviewer"
}
```

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "total_reviewed": 3,
    "approved": 1,
    "rejected": 1,
    "modified": 1,
    "remaining_pending": 7
  }
}
```

---

### 3.6 GET /cases/{case_id}/review-queue

HITL 검토가 필요한 항목의 대기열을 조회한다.

#### Query Parameters

| 파라미터 | 타입 | 기본값 | 설명 |
|---------|------|-------|------|
| `sort_by` | string | confidence_asc | confidence_asc, confidence_desc, created_at |
| `entity_type` | string | all | 특정 개체 유형만 필터 |
| `limit` | int | 20 | 페이지 크기 |
| `offset` | int | 0 | 오프셋 |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "case_id": "550e8400-e29b-41d4-a716-446655440001",
    "total_pending": 10,
    "items": [
      {
        "entity_id": "entity-uuid-015",
        "doc_id": "doc-uuid-001",
        "text": "분석가 김모",
        "entity_type": "PERSON",
        "confidence": 0.65,
        "context": "프로세스 분석가 김모는 분석 보고서에서...",
        "suggested_mapping": {
          "layer": "resource",
          "label": "Employee:Resource"
        },
        "created_at": "2024-06-16T10:02:00Z"
      }
    ],
    "confidence_distribution": {
      "0.0-0.25": 1,
      "0.25-0.50": 2,
      "0.50-0.75": 7
    }
  }
}
```

---

### 3.7 POST /documents/{doc_id}/revert-extraction

Saga 보상 전용 API. Core의 DocumentExtractionSaga에서 상위 단계 실패 시 호출되며, 지정된 엔티티/관계의 Neo4j 노드를 삭제하고 추출 결과를 `reverted` 상태로 변경한다.

#### Request

```json
POST /api/v3/synapse/extraction/documents/doc-uuid-001/revert-extraction
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "entity_ids": ["entity-uuid-001", "entity-uuid-002"],
  "relation_ids": ["rel-uuid-001"],
  "reason": "Saga compensation - upstream failure at Step 7",
  "saga_context_id": "saga-uuid-001"
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `entity_ids` | array[uuid] | N | 되돌릴 엔티티 ID 목록 (ontology-result의 entities[].id) |
| `relation_ids` | array[uuid] | N | 되돌릴 관계 ID 목록 (ontology-result의 relations[].id) |
| `reason` | string | Y | 보상 사유 |
| `saga_context_id` | uuid | N | Saga 추적 ID (감사 로그 연결) |

> `entity_ids`와 `relation_ids` 모두 비어 있으면 400 에러를 반환한다.

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "doc_id": "doc-uuid-001",
    "reverted_entities": 2,
    "reverted_relations": 1,
    "neo4j_nodes_deleted": 3,
    "audit_log_id": "audit-uuid-001"
  }
}
```

#### 처리 로직

```
1. entity_ids로 지정된 엔티티의 neo4j_node_id를 조회한다.
2. Neo4j에서 해당 노드 및 연결된 관계를 삭제한다.
   - relation_ids로 지정된 관계도 Neo4j에서 삭제한다.
3. 추출 결과 DB에서 해당 엔티티/관계의 status를 "reverted"로 변경한다.
4. 감사 로그를 기록한다 (saga_context_id, 삭제된 노드 목록, 사유).
```

#### 에러

| HTTP Status | Code | 조건 |
|------------|------|------|
| 400 | `EMPTY_REVERT_REQUEST` | entity_ids와 relation_ids 모두 비어 있음 |
| 404 | `ENTITY_NOT_FOUND` | 지정된 엔티티 ID가 존재하지 않음 |
| 409 | `ALREADY_REVERTED` | 이미 reverted 상태인 항목 |

#### 멱등성

동일한 `saga_context_id`로 재호출 시, 이미 reverted된 항목은 건너뛰고 나머지만 처리한다. 모든 항목이 이미 reverted되면 200을 반환한다 (409가 아님). 이는 Saga 보상의 재시도 안전성을 보장한다.

> **Saga 연동**: 이 API는 Core DocumentExtractionSaga의 Step 6 보상에서 호출된다. 상세한 Saga 흐름은 Core [transaction-boundaries.md](../../../core/docs/03_backend/transaction-boundaries.md) §2.3을 참조한다.

---

## 4. 에러 코드

| HTTP Status | Code | 의미 |
|------------|------|------|
| 400 | `DOCUMENT_NOT_FOUND` | 문서 없음 |
| 400 | `EXTRACTION_ALREADY_RUNNING` | 이미 추출 진행 중 |
| 400 | `INVALID_ACTION` | 잘못된 검토 액션 |
| 404 | `ENTITY_NOT_FOUND` | 추출 개체 없음 |
| 404 | `TASK_NOT_FOUND` | 작업 없음 |
| 409 | `ALREADY_REVIEWED` | 이미 검토된 항목 |
| 422 | `EXTRACTION_FAILED` | 추출 실패 (상세 원인 포함) |
| 429 | `RATE_LIMIT_EXCEEDED` | LLM API 호출 한도 초과 |
| 400 | `EMPTY_REVERT_REQUEST` | revert 요청에 entity_ids/relation_ids 모두 비어 있음 |
| 409 | `ALREADY_REVERTED` | 이미 되돌린 추출 항목 |

---

## 5. 권한

| 엔드포인트 | 필요 역할 |
|----------|---------|
| POST /extract-ontology | case_editor, admin |
| GET /ontology-status, /ontology-result | case_viewer, case_editor, admin |
| PUT /confirm, POST /review | hitl_reviewer, admin |
| GET /review-queue | hitl_reviewer, admin |
| POST /revert-extraction | saga_compensation (시스템 내부 전용) |

---

## 6. 비동기 작업 흐름

```
Client                    Synapse                      GPT-4o
  │                          │                            │
  │ POST /extract-ontology   │                            │
  │────────────────────────▶│                            │
  │ 202 {task_id}            │                            │
  │◀────────────────────────│                            │
  │                          │ extract text               │
  │                          │──────────┐                 │
  │                          │◀─────────┘                 │
  │                          │                            │
  │ GET /ontology-status     │ NER request                │
  │────────────────────────▶│──────────────────────────▶│
  │ 200 {processing, 3/12}   │ NER response               │
  │◀────────────────────────│◀────────────────────────│
  │                          │                            │
  │ ... (polling) ...        │ Relation request            │
  │                          │──────────────────────────▶│
  │                          │ Relation response           │
  │                          │◀────────────────────────│
  │                          │                            │
  │                          │ Map to ontology             │
  │                          │──────────┐                 │
  │                          │◀─────────┘                 │
  │                          │                            │
  │                          │ Commit to Neo4j             │
  │                          │──────────┐                 │
  │                          │◀─────────┘                 │
  │                          │                            │
  │ GET /ontology-status     │                            │
  │────────────────────────▶│                            │
  │ 200 {completed}          │                            │
  │◀────────────────────────│                            │
  │                          │                            │
  │ GET /ontology-result     │                            │
  │────────────────────────▶│                            │
  │ 200 {entities, relations}│                            │
  │◀────────────────────────│                            │
```

---

## 근거 문서

- `01_architecture/extraction-pipeline.md` (파이프라인 아키텍처)
- `05_llm/structured-output.md` (GPT-4o Structured Output)
- ADR-004: HITL 신뢰도 임계값 (`99_decisions/ADR-004-hitl-threshold.md`)
