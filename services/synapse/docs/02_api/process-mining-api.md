# Process Mining API

> 구현 상태 태그: `Partial (Conformance Stub 포함)`
> 기준일: 2026-02-22
> 최신 근거: `docs/full-spec-gap-analysis-2026-02-22.md`

## 이 문서가 답하는 질문

- 이벤트 로그에서 프로세스 모델을 발견하는 API는?
- 설계 모델과 실행 로그의 적합성을 검사하는 API는?
- 프로세스 변종과 병목을 분석하는 API는?
- 각 API의 요청/응답 형식과 비동기 처리 방식은?

<!-- affects: frontend, backend -->
<!-- requires-update: 01_architecture/process-mining-engine.md, 03_backend/process-discovery.md -->

---

## 1. 기본 정보

| 항목 | 값 |
|------|---|
| Base URL (Synapse 내부) | `/api/v3/synapse/process-mining` |
| Base URL (Core 게이트웨이 경유) | `/api/v1/process-mining` |
| 인증 | JWT Bearer Token (Core 경유) |
| Content-Type | `application/json` |
| 비동기 작업 | task_id 기반, 폴링으로 상태 확인 |

> **라우팅 참고**: 외부 클라이언트는 Core 게이트웨이(`/api/v1/process-mining`)를 통해 접근한다. Core가 Synapse 내부 URL로 프록시한다. 게이트웨이 라우팅 상세는 Core [gateway-api.md](../../../core/docs/02_api/gateway-api.md) §1을 참조한다.

---

## 2. 엔드포인트 목록

| Method | Path | 설명 | 동기/비동기 |
|--------|------|------|-----------|
| POST | `/discover` | 프로세스 모델 발견 | 비동기 |
| POST | `/conformance` | 적합성 검사 | 비동기 |
| GET | `/variants` | 프로세스 변종 조회 | 동기 |
| GET | `/bottlenecks` | 병목 분석 결과 조회 | 동기 |
| GET | `/tasks/{task_id}` | 비동기 작업 상태 조회 | 동기 |
| GET | `/tasks/{task_id}/result` | 비동기 작업 결과 조회 | 동기 |
| POST | `/performance` | 성능 분석 (시간축 병목 탐지) | 비동기 |
| POST | `/import-model` | 외부 BPMN/Petri Net 모델 임포트 (적합성 검사용) | 동기 |
| GET | `/results/{task_id}` | 비동기 작업 결과 조회 (별칭: `/tasks/{task_id}/result`) | 동기 |
| POST | `/bpmn/export` | BPMN XML 내보내기 | 동기 |
| GET | `/statistics/{log_id}` | 이벤트 로그 통계 | 동기 |

> 참고: `/conformance` 경로의 내부 checker는 현재 stub 구현이 포함되어 있어 full-spec 기준 `Partial`로 관리한다.

---

## 3. 엔드포인트 상세

### 3.1 POST /discover

이벤트 로그에서 프로세스 모델을 자동으로 발견한다. pm4py의 Alpha/Heuristic/Inductive Miner 중 선택하여 실행한다.

#### Request

```json
POST /api/v1/process-mining/discover
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "log_id": "log-uuid-001",
  "algorithm": "inductive",
  "parameters": {
    "noise_threshold": 0.2,
    "dependency_threshold": 0.5
  },
  "options": {
    "generate_bpmn": true,
    "calculate_statistics": true,
    "store_in_neo4j": true
  }
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|-------|------|
| `case_id` | uuid | Y | - | Axiom 프로젝트 ID |
| `log_id` | uuid | Y | - | 이벤트 로그 ID |
| `algorithm` | string | N | inductive | alpha, heuristic, inductive |
| `parameters.noise_threshold` | float | N | 0.2 | Inductive Miner 노이즈 임계값 (0.0-1.0) |
| `parameters.dependency_threshold` | float | N | 0.5 | Heuristic Miner 의존도 임계값 |
| `options.generate_bpmn` | bool | N | true | BPMN XML 생성 여부 |
| `options.calculate_statistics` | bool | N | true | 활동별 빈도/시간 통계 |
| `options.store_in_neo4j` | bool | N | true | 발견된 모델을 Neo4j에 저장 |

#### Response (202 Accepted)

```json
{
  "success": true,
  "data": {
    "task_id": "task-pm-uuid-001",
    "log_id": "log-uuid-001",
    "algorithm": "inductive",
    "status": "queued",
    "created_at": "2024-06-16T10:00:00Z",
    "estimated_duration_seconds": 30
  }
}
```

#### 작업 완료 후 결과 (GET /tasks/{task_id}/result)

```json
{
  "success": true,
  "data": {
    "task_id": "task-pm-uuid-001",
    "status": "completed",
    "result": {
      "algorithm": "inductive",
      "parameters": {"noise_threshold": 0.2},
      "model": {
        "type": "petri_net",
        "places": 8,
        "transitions": 6,
        "arcs": 14
      },
      "bpmn_xml": "<?xml version=\"1.0\"?><definitions ...>...</definitions>",
      "statistics": {
        "total_cases": 1250,
        "total_events": 8750,
        "unique_activities": 6,
        "avg_case_duration_seconds": 172800,
        "median_case_duration_seconds": 145200,
        "activities": [
          {
            "name": "주문 접수",
            "frequency": 1250,
            "avg_duration_seconds": 300,
            "min_duration_seconds": 60,
            "max_duration_seconds": 1800
          },
          {
            "name": "출하 지시",
            "frequency": 1230,
            "avg_duration_seconds": 7200,
            "min_duration_seconds": 3600,
            "max_duration_seconds": 28800
          }
        ]
      },
      "neo4j_nodes_created": 14,
      "completed_at": "2024-06-16T10:00:28Z"
    }
  }
}
```

---

### 3.2 POST /conformance

EventStorming으로 설계된 모델(참조 모델)과 이벤트 로그 간의 적합성을 검사한다.

#### Request

```json
POST /api/v1/process-mining/conformance
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "log_id": "log-uuid-001",
  "reference_model": {
    "type": "eventstorming",
    "model_id": "es-model-uuid-001"
  },
  "options": {
    "method": "token_replay",
    "calculate_precision": true,
    "calculate_generalization": true,
    "include_case_diagnostics": true,
    "max_diagnostics_cases": 100
  }
}
```

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|-------|------|
| `case_id` | uuid | Y | - | Axiom 프로젝트 ID |
| `log_id` | uuid | Y | - | 이벤트 로그 ID |
| `reference_model.type` | string | Y | - | eventstorming, petri_net, discovered |
| `reference_model.model_id` | uuid | Y | - | 참조 모델 ID |
| `options.method` | string | N | token_replay | token_replay (현재 유일) |
| `options.calculate_precision` | bool | N | true | precision 메트릭 계산 |
| `options.calculate_generalization` | bool | N | true | generalization 메트릭 계산 |
| `options.include_case_diagnostics` | bool | N | true | 케이스별 진단 결과 포함 |
| `options.max_diagnostics_cases` | int | N | 100 | 진단 결과에 포함할 최대 케이스 수 |

#### Response (202 Accepted)

```json
{
  "success": true,
  "data": {
    "task_id": "task-conf-uuid-001",
    "status": "queued",
    "created_at": "2024-06-16T10:05:00Z"
  }
}
```

#### 작업 완료 후 결과

```json
{
  "success": true,
  "data": {
    "task_id": "task-conf-uuid-001",
    "status": "completed",
    "result": {
      "reference_model": {
        "type": "eventstorming",
        "model_id": "es-model-uuid-001",
        "name": "주문-배송 프로세스"
      },
      "metrics": {
        "fitness": 0.85,
        "precision": 0.92,
        "generalization": 0.88,
        "simplicity": 0.75
      },
      "summary": {
        "total_cases": 1250,
        "conformant_cases": 1062,
        "non_conformant_cases": 188,
        "conformance_rate": 0.85
      },
      "case_diagnostics": [
        {
          "instance_case_id": "order-001",
          "is_fit": false,
          "trace_fitness": 0.67,
          "trace": ["주문 접수", "결제 확인", "출하 지시", "배송 완료"],
          "deviations": [
            {
              "position": 2,
              "expected": "재고 확인",
              "actual": "출하 지시",
              "type": "skipped_activity",
              "description": "'재고 확인' 활동이 누락됨"
            }
          ]
        },
        {
          "instance_case_id": "order-042",
          "is_fit": false,
          "trace_fitness": 0.50,
          "trace": ["주문 접수", "결제 확인", "반품 처리", "환불"],
          "deviations": [
            {
              "position": 2,
              "expected": "재고 확인",
              "actual": "반품 처리",
              "type": "unexpected_activity",
              "description": "설계에 없는 '반품 처리' 활동이 발생"
            }
          ]
        }
      ],
      "deviation_statistics": {
        "skipped_activities": {
          "재고 확인": 120,
          "품질 검사": 45
        },
        "unexpected_activities": {
          "반품 처리": 23,
          "긴급 출하": 15
        }
      },
      "completed_at": "2024-06-16T10:05:45Z"
    }
  }
}
```

---

### 3.3 GET /variants

프로세스 변종(Variant)을 조회한다. 변종은 동일 프로세스의 서로 다른 실행 경로이다.

#### Request

```
GET /api/v1/process-mining/variants?case_id=550e8400&log_id=log-uuid-001&sort_by=frequency_desc&limit=20
Authorization: Bearer <jwt_token>
```

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `case_id` | uuid | Y | - | Axiom 프로젝트 ID |
| `log_id` | uuid | Y | - | 이벤트 로그 ID |
| `sort_by` | string | N | frequency_desc | frequency_desc, frequency_asc, duration_desc, duration_asc |
| `limit` | int | N | 20 | 최대 변종 수 |
| `min_cases` | int | N | 1 | 최소 케이스 수 필터 |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "log_id": "log-uuid-001",
    "total_variants": 15,
    "total_cases": 1250,
    "variants": [
      {
        "variant_id": "var-001",
        "rank": 1,
        "activity_sequence": ["주문 접수", "결제 확인", "재고 확인", "출하 지시", "배송 완료"],
        "case_count": 850,
        "case_percentage": 68.0,
        "avg_duration_seconds": 172800,
        "median_duration_seconds": 158400,
        "is_designed_path": true
      },
      {
        "variant_id": "var-002",
        "rank": 2,
        "activity_sequence": ["주문 접수", "결제 확인", "출하 지시", "배송 완료"],
        "case_count": 200,
        "case_percentage": 16.0,
        "avg_duration_seconds": 129600,
        "median_duration_seconds": 115200,
        "is_designed_path": false,
        "deviation_from_designed": "'재고 확인' 단계 누락"
      },
      {
        "variant_id": "var-003",
        "rank": 3,
        "activity_sequence": ["주문 접수", "결제 확인", "재고 확인", "출하 지시", "품질 검사", "배송 완료"],
        "case_count": 120,
        "case_percentage": 9.6,
        "avg_duration_seconds": 259200,
        "median_duration_seconds": 230400,
        "is_designed_path": false,
        "deviation_from_designed": "'품질 검사' 단계 추가됨"
      }
    ]
  }
}
```

---

### 3.4 GET /bottlenecks

프로세스 병목을 분석한다. 활동별 소요시간, 대기시간, SLA 위반 현황을 반환한다.

#### Request

```
GET /api/v1/process-mining/bottlenecks?case_id=550e8400&log_id=log-uuid-001
Authorization: Bearer <jwt_token>
```

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|---------|------|------|-------|------|
| `case_id` | uuid | Y | - | Axiom 프로젝트 ID |
| `log_id` | uuid | Y | - | 이벤트 로그 ID |
| `sort_by` | string | N | bottleneck_score_desc | bottleneck_score_desc, avg_duration_desc, violation_rate_desc |
| `sla_source` | string | N | eventstorming | eventstorming, manual, none |

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "log_id": "log-uuid-001",
    "analysis_period": {
      "start": "2024-01-01T00:00:00Z",
      "end": "2024-06-30T23:59:59Z"
    },
    "bottlenecks": [
      {
        "activity": "출하 지시",
        "bottleneck_score": 0.89,
        "bottleneck_rank": 1,
        "duration_stats": {
          "avg_seconds": 7200,
          "median_seconds": 5400,
          "p95_seconds": 21600,
          "min_seconds": 3600,
          "max_seconds": 28800
        },
        "waiting_time": {
          "avg_seconds": 3600,
          "median_seconds": 2700
        },
        "sla": {
          "threshold_seconds": 7200,
          "violation_count": 312,
          "total_cases": 1230,
          "violation_rate": 0.254
        },
        "trend": {
          "direction": "worsening",
          "change_rate_per_month": 0.05,
          "description": "최근 6개월간 평균 소요시간이 월 5%씩 증가 추세"
        }
      },
      {
        "activity": "재고 확인",
        "bottleneck_score": 0.62,
        "bottleneck_rank": 2,
        "duration_stats": {
          "avg_seconds": 3600,
          "median_seconds": 2400,
          "p95_seconds": 10800,
          "min_seconds": 600,
          "max_seconds": 14400
        },
        "waiting_time": {
          "avg_seconds": 1800,
          "median_seconds": 1200
        },
        "sla": {
          "threshold_seconds": 3600,
          "violation_count": 178,
          "total_cases": 1050,
          "violation_rate": 0.170
        },
        "trend": {
          "direction": "stable",
          "change_rate_per_month": 0.01,
          "description": "안정적"
        }
      }
    ],
    "overall_process": {
      "avg_duration_seconds": 172800,
      "median_duration_seconds": 145200,
      "total_sla_violations": 490,
      "overall_compliance_rate": 0.608
    }
  }
}
```

---

### 3.5 POST /bpmn/export

프로세스 모델을 BPMN 2.0 XML로 내보낸다.

#### Request

```json
POST /api/v1/process-mining/bpmn/export
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "case_id": "550e8400-e29b-41d4-a716-446655440001",
  "source": {
    "type": "discovered",
    "task_id": "task-pm-uuid-001"
  },
  "options": {
    "include_statistics": true,
    "include_bottleneck_colors": true
  }
}
```

#### Response (200 OK)

```json
{
  "success": true,
  "data": {
    "format": "bpmn_2.0_xml",
    "xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<definitions xmlns=\"http://www.omg.org/spec/BPMN/20100524/MODEL\" ...>\n  <process id=\"discovered_process\" name=\"주문-배송 프로세스\">\n    ...\n  </process>\n</definitions>",
    "statistics_overlay": {
      "activities": {
        "주문 접수": {"frequency": 1250, "avg_duration": 300, "bottleneck_score": 0.15},
        "출하 지시": {"frequency": 1230, "avg_duration": 7200, "bottleneck_score": 0.89}
      }
    }
  }
}
```

---

## 4. 에러 코드

| HTTP Status | Code | 의미 | 사용자 표시 |
|------------|------|------|-----------|
| 400 | `INVALID_ALGORITHM` | 지원하지 않는 알고리즘 | 올바른 알고리즘을 선택하세요 (alpha, heuristic, inductive) |
| 400 | `INVALID_LOG_FORMAT` | 이벤트 로그 형식 오류 | 이벤트 로그 형식을 확인하세요 |
| 400 | `EMPTY_EVENT_LOG` | 이벤트가 없는 로그 | 이벤트 로그에 데이터가 없습니다 |
| 400 | `MISSING_COLUMN_MAPPING` | 필수 컬럼 매핑 누락 | case_id, activity, timestamp 매핑이 필요합니다 |
| 404 | `LOG_NOT_FOUND` | 이벤트 로그 없음 | 이벤트 로그를 찾을 수 없습니다 |
| 404 | `MODEL_NOT_FOUND` | 참조 모델 없음 | 참조 모델을 찾을 수 없습니다 |
| 404 | `TASK_NOT_FOUND` | 작업 없음 | 작업을 찾을 수 없습니다 |
| 422 | `DISCOVERY_FAILED` | 프로세스 발견 실패 | 프로세스 발견에 실패했습니다 |
| 422 | `CONFORMANCE_FAILED` | 적합성 검사 실패 | 적합성 검사에 실패했습니다 |
| 429 | `MINING_RATE_LIMIT` | 동시 작업 제한 초과 | 진행 중인 분석이 너무 많습니다 |

---

## 5. 권한

| 엔드포인트 | 필요 역할 | 케이스 범위 |
|----------|---------|-----------|
| POST /discover, /conformance, /performance | case_editor, admin | 본인 소속 케이스만 |
| POST /import-model | case_editor, admin | 본인 소속 케이스만 |
| GET /variants, /bottlenecks, /statistics | case_viewer, case_editor, admin | 본인 소속 케이스만 |
| GET /tasks/*, /results/* | case_viewer, case_editor, admin | 본인이 생성한 작업만 |
| POST /bpmn/export | case_viewer, case_editor, admin | 본인 소속 케이스만 |

---

## 6. 비동기 작업 흐름

```
Client                    Synapse                      pm4py
  │                          │                            │
  │ POST /discover           │                            │
  │────────────────────────▶│                            │
  │ 202 {task_id}            │                            │
  │◀────────────────────────│                            │
  │                          │ Load event log             │
  │                          │──────────┐                 │
  │                          │◀─────────┘                 │
  │                          │                            │
  │ GET /tasks/{id}          │ discover_petri_net_*()     │
  │────────────────────────▶│──────────────────────────▶│
  │ 200 {processing}         │ Petri Net                  │
  │◀────────────────────────│◀────────────────────────│
  │                          │                            │
  │ ... (polling) ...        │ Convert to BPMN            │
  │                          │──────────────────────────▶│
  │                          │ BPMN XML                   │
  │                          │◀────────────────────────│
  │                          │                            │
  │                          │ Store in Neo4j + PG        │
  │                          │──────────┐                 │
  │                          │◀─────────┘                 │
  │                          │                            │
  │ GET /tasks/{id}          │                            │
  │────────────────────────▶│                            │
  │ 200 {completed}          │                            │
  │◀────────────────────────│                            │
  │                          │                            │
  │ GET /tasks/{id}/result   │                            │
  │────────────────────────▶│                            │
  │ 200 {model, bpmn, stats} │                            │
  │◀────────────────────────│                            │
```

---

## 근거 문서

- `01_architecture/process-mining-engine.md` (엔진 아키텍처)
- `03_backend/process-discovery.md` (Process Discovery 구현)
- `03_backend/conformance-checker.md` (Conformance Checker 구현)
- `03_backend/temporal-analysis.md` (시간축 분석 구현)
- ADR-005: pm4py 선택 (`99_decisions/ADR-005-pm4py-process-mining.md`)
