# 온톨로지 CRUD API

## 이 문서가 답하는 질문

- 4계층 온톨로지 노드를 생성/조회/수정/삭제하는 API는?
- 계층 간 관계를 어떻게 관리하는가?
- 특정 케이스의 전체 온톨로지를 어떻게 조회하는가?
- 각 API의 권한 요구사항은?

<!-- affects: frontend, backend, llm -->
<!-- requires-update: 04_frontend/, 07_security/data-access.md -->

---

## 1. 기본 정보

| 항목 | 값 |
|------|---|
| Base URL | `/api/v3/synapse/ontology` |
| 인증 | JWT Bearer Token (Core 경유) |
| Content-Type | `application/json` |
| 에러 형식 | `{"error": {"code": "string", "message": "string", "details": {}}}` |

---

## 2. 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| GET | `/cases/{case_id}/ontology` | 케이스 전체 온톨로지 조회 |
| GET | `/cases/{case_id}/ontology/summary` | 케이스 온톨로지 요약 통계 |
| GET | `/cases/{case_id}/ontology/{layer}` | 특정 계층 노드 목록 |
| POST | `/nodes` | 온톨로지 노드 생성 |
| GET | `/nodes/{node_id}` | 노드 상세 조회 |
| PUT | `/nodes/{node_id}` | 노드 수정 |
| DELETE | `/nodes/{node_id}` | 노드 삭제 |
| POST | `/relations` | 관계 생성 |
| DELETE | `/relations/{relation_id}` | 관계 삭제 |
| GET | `/nodes/{node_id}/neighbors` | 인접 노드 조회 |
| GET | `/nodes/{node_id}/path-to/{target_id}` | 두 노드 간 경로 |

---

## 3. 엔드포인트 상세

### 3.1 GET /cases/{case_id}/ontology

케이스의 전체 온톨로지 그래프를 반환한다.

#### Request

```
GET /api/v3/synapse/ontology/cases/550e8400-e29b-41d4-a716-446655440001/ontology
Authorization: Bearer <jwt_token>
```

Query Parameters:

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `layer` | string | N | all | 필터: resource, process, measure, kpi, all |
| `include_relations` | bool | N | true | 관계 포함 여부 |
| `verified_only` | bool | N | false | 검증된 노드만 |
| `limit` | int | N | 500 | 최대 노드 수 |
| `offset` | int | N | 0 | 페이지네이션 오프셋 |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "case_id": "550e8400-e29b-41d4-a716-446655440001",
    "summary": {
      "total_nodes": 47,
      "total_relations": 62,
      "by_layer": {
        "resource": 18,
        "process": 12,
        "measure": 10,
        "kpi": 7
      }
    },
    "nodes": [
      {
        "id": "node-uuid-001",
        "labels": ["Company", "Resource"],
        "layer": "resource",
        "properties": {
          "name": "ABC 제조",
          "type": "Company",
          "registration_no": "123-45-67890",
          "representative": "홍길동",
          "industry": "제조업",
          "source": "ingested",
          "confidence": 1.0,
          "verified": true,
          "created_at": "2024-06-01T09:00:00Z",
          "updated_at": "2024-06-01T09:00:00Z"
        }
      }
    ],
    "relations": [
      {
        "id": "rel-uuid-001",
        "type": "PARTICIPATES_IN",
        "source_id": "node-uuid-001",
        "target_id": "node-uuid-020",
        "properties": {
          "role": "subject_organization",
          "since": "2024-01-15"
        }
      }
    ]
  },
  "pagination": {
    "total": 47,
    "limit": 500,
    "offset": 0,
    "has_more": false
  }
}
```

---

### 3.2 GET /cases/{case_id}/ontology/summary

케이스 온톨로지의 요약 통계를 반환한다. 전체 그래프를 다운로드하지 않고 현황을 파악할 때 사용한다.

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "case_id": "550e8400-e29b-41d4-a716-446655440001",
    "node_counts": {
      "resource": {
        "total": 18,
        "by_type": {
          "Company": 3,
          "Asset": 5,
          "Employee": 3,
          "Financial": 2,
          "CashReserve": 2,
          "Inventory": 1,
          "Contract": 2
        }
      },
      "process": {
        "total": 12,
        "by_type": {
          "DataCollection": 1,
          "ProcessAnalysis": 2,
          "Optimization": 2,
          "Execution": 3,
          "Review": 1,
          "Activity": 3
        }
      },
      "measure": {
        "total": 10,
        "by_type": {
          "Revenue": 2,
          "Cost": 2,
          "OperatingProfit": 1,
          "Throughput": 2,
          "CycleTime": 3
        }
      },
      "kpi": {
        "total": 7,
        "by_type": {
          "ProcessEfficiency": 1,
          "CostReduction": 1,
          "ROI": 1,
          "CustomerSatisfaction": 1,
          "KPITarget": 2,
          "KPIHistory": 1
        }
      }
    },
    "relation_counts": {
      "PARTICIPATES_IN": 15,
      "PRODUCES": 10,
      "CONTRIBUTES_TO": 12,
      "DEPENDS_ON": 7,
      "INFLUENCES": 5,
      "OWNS": 5,
      "HAS_CONTRACT_WITH": 3,
      "other": 5
    },
    "verification_status": {
      "verified": 35,
      "unverified": 8,
      "pending_review": 4
    },
    "last_updated": "2024-06-15T14:30:00Z"
  }
}
```

---

### 3.3 POST /nodes

새 온톨로지 노드를 생성한다.

#### Request

```json
POST /api/v3/synapse/ontology/nodes
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "layer": "resource",
  "type": "Asset",
  "properties": {
    "name": "강남 사옥",
    "type": "RealEstate",
    "market_value": 5000000000,
    "book_value": 4000000000,
    "appraised_date": "2024-03-15",
    "description": "서울 강남구 소재 7층 건물"
  },
  "source": "manual",
  "confidence": 1.0
}
```

| 필드 | 타입 | 필수 | nullable | 설명 |
|------|------|------|----------|------|
| `case_id` | uuid | Y | N | 프로젝트 ID |
| `layer` | string | Y | N | resource, process, measure, kpi |
| `type` | string | Y | N | 노드 유형 (Company, Asset 등) |
| `properties` | object | Y | N | 노드 속성 (유형별 스키마 다름) |
| `source` | string | N | N | manual, extracted, ingested (기본: manual) |
| `confidence` | float | N | N | 0.0-1.0 (기본: 1.0 for manual) |

#### Response (201 Created)

```json
{
  "success": true,
  "data": {
    "id": "node-uuid-new",
    "labels": ["Asset", "Resource"],
    "layer": "resource",
    "properties": {
      "name": "강남 사옥",
      "type": "RealEstate",
      "market_value": 5000000000,
      "book_value": 4000000000,
      "appraised_date": "2024-03-15",
      "description": "서울 강남구 소재 7층 건물",
      "source": "manual",
      "confidence": 1.0,
      "verified": true,
      "created_at": "2024-06-16T10:00:00Z"
    }
  }
}
```

---

### 3.4 PUT /nodes/{node_id}

기존 노드의 속성을 수정한다. 부분 업데이트를 지원한다 (PATCH 시맨틱).

#### Request

```json
PUT /api/v3/synapse/ontology/nodes/node-uuid-001
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "properties": {
    "market_value": 4500000000,
    "description": "서울 강남구 소재 7층 건물 (재평가)"
  }
}
```

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "id": "node-uuid-001",
    "labels": ["Asset", "Resource"],
    "properties": {
      "name": "강남 사옥",
      "market_value": 4500000000,
      "description": "서울 강남구 소재 7층 건물 (재평가)",
      "updated_at": "2024-06-16T10:30:00Z"
    }
  }
}
```

---

### 3.5 POST /relations

두 노드 간 관계를 생성한다.

#### Request

```json
POST /api/v3/synapse/ontology/relations
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "source_id": "node-uuid-001",
  "target_id": "node-uuid-020",
  "type": "PARTICIPATES_IN",
  "properties": {
    "role": "subject_organization",
    "since": "2024-01-15"
  }
}
```

| 필드 | 타입 | 필수 | nullable | 설명 |
|------|------|------|----------|------|
| `source_id` | uuid | Y | N | 시작 노드 ID |
| `target_id` | uuid | Y | N | 대상 노드 ID |
| `type` | string | Y | N | 관계 유형 (PARTICIPATES_IN 등) |
| `properties` | object | N | Y | 관계 속성 |

#### 관계 유형별 유효성 검증

| 관계 유형 | 허용 방향 |
|----------|----------|
| PARTICIPATES_IN | Resource → Process |
| PRODUCES | Process → Measure |
| CONTRIBUTES_TO | Resource → Measure, Measure → KPI |
| DEPENDS_ON | KPI → Measure |
| INFLUENCES | Process → KPI |
| OWNS | Company → Asset |
| HAS_CONTRACT_WITH | Company → Contract |

잘못된 방향으로 관계 생성을 시도하면 400 에러를 반환한다.

#### Response (201 Created)

```json
{
  "success": true,
  "data": {
    "id": "rel-uuid-new",
    "type": "PARTICIPATES_IN",
    "source_id": "node-uuid-001",
    "target_id": "node-uuid-020",
    "properties": {
      "role": "subject_organization",
      "since": "2024-01-15"
    }
  }
}
```

---

### 3.6 GET /nodes/{node_id}/neighbors

특정 노드의 인접 노드를 조회한다.

#### Query Parameters

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `direction` | string | N | both | in, out, both |
| `relation_type` | string | N | all | 특정 관계 유형만 필터 |
| `max_depth` | int | N | 1 | 최대 탐색 깊이 (1-3) |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "center_node": {
      "id": "node-uuid-001",
      "labels": ["Company", "Resource"],
      "name": "ABC 제조"
    },
    "neighbors": [
      {
        "node": {
          "id": "node-uuid-002",
          "labels": ["Asset", "Resource"],
          "name": "강남 사옥"
        },
        "relation": {
          "type": "OWNS",
          "direction": "outgoing"
        },
        "depth": 1
      },
      {
        "node": {
          "id": "node-uuid-020",
          "labels": ["DataCollection", "Process"],
          "name": "데이터 수집"
        },
        "relation": {
          "type": "PARTICIPATES_IN",
          "direction": "outgoing"
        },
        "depth": 1
      }
    ],
    "total_neighbors": 8
  }
}
```

---

### 3.7 GET /nodes/{node_id}/path-to/{target_id}

두 노드 간 최단 경로를 반환한다. KPI 역추적 분석에 핵심적으로 사용된다.

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "path": [
      {
        "node": {"id": "node-uuid-001", "labels": ["Company", "Resource"], "name": "ABC 제조"},
        "relation_to_next": {"type": "PARTICIPATES_IN", "properties": {"role": "subject_organization"}}
      },
      {
        "node": {"id": "node-uuid-020", "labels": ["ProcessAnalysis", "Process"], "name": "프로세스 분석"},
        "relation_to_next": {"type": "PRODUCES", "properties": {}}
      },
      {
        "node": {"id": "node-uuid-030", "labels": ["Revenue", "Measure"], "name": "매출"},
        "relation_to_next": {"type": "CONTRIBUTES_TO", "properties": {"weight": 1.0}}
      },
      {
        "node": {"id": "node-uuid-040", "labels": ["ProcessEfficiency", "KPI"], "name": "프로세스 효율성"},
        "relation_to_next": null
      }
    ],
    "total_hops": 3,
    "path_type": "resource_to_kpi"
  }
}
```

---

## 4. 에러 코드

| HTTP Status | Code | 의미 | 사용자 표시 |
|------------|------|------|-----------|
| 400 | `INVALID_LAYER` | 유효하지 않은 계층 지정 | 올바른 계층을 선택하세요 |
| 400 | `INVALID_RELATION_DIRECTION` | 관계 방향 규칙 위반 | 이 관계는 허용되지 않는 방향입니다 |
| 400 | `MISSING_REQUIRED_FIELD` | 필수 필드 누락 | 필수 항목을 입력하세요 |
| 404 | `NODE_NOT_FOUND` | 노드 없음 | 노드를 찾을 수 없습니다 |
| 404 | `CASE_NOT_FOUND` | 케이스 없음 | 프로젝트를 찾을 수 없습니다 |
| 404 | `PATH_NOT_FOUND` | 경로 없음 | 두 노드 간 경로가 없습니다 |
| 409 | `DUPLICATE_NODE` | 동일 노드 존재 | 이미 동일한 항목이 존재합니다 |
| 403 | `ACCESS_DENIED` | 케이스 접근 권한 없음 | 이 프로젝트에 접근 권한이 없습니다 |

---

## 5. 권한

| 엔드포인트 | 필요 역할 | 케이스 범위 |
|----------|---------|-----------|
| GET (조회) | case_viewer, case_editor, admin | 본인 소속 케이스만 |
| POST, PUT (생성/수정) | case_editor, admin | 본인 소속 케이스만 |
| DELETE (삭제) | admin | 본인 소속 케이스만 |

---

## 근거 문서

- `01_architecture/ontology-4layer.md` (4계층 온톨로지 구조)
- `07_security/data-access.md` (접근 제어)
- `06_data/ontology-model.md` (데이터 모델)
