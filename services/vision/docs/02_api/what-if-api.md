# What-if 시뮬레이션 API

> **최종 수정일**: 2026-02-21
> **상태**: Active
> **구현 상태 태그**: `Implemented`
> **Phase**: 3.2
> **근거**: 01_architecture/what-if-engine.md

---

## 이 문서가 답하는 질문

- What-if 시나리오를 생성/수정/삭제하는 API는?
- 시나리오 계산을 실행하고 결과를 조회하는 방법은?
- 다중 시나리오를 비교하는 API는?
- 민감도 분석과 전환점 분석 API는?
- 각 필드의 nullable 여부와 제약조건은?
- 프로세스 시간축 시뮬레이션 API는 어떻게 호출하는가?

---

## 기본 정보

| 항목 | 값 |
|------|-----|
| **Base URL** | `/api/v3/cases/{case_id}/what-if` |
| **인증** | Bearer JWT (Authorization 헤더) |
| **권한** | 케이스 담당자 이상 (ADMIN, TRUSTEE) |
| **Content-Type** | `application/json` |

### 외부 의존성

§10 프로세스 시간축 시뮬레이션은 Synapse 프로세스 마이닝 서비스에 의존한다.

| Synapse 엔드포인트 | 용도 | 호출 시점 |
|-------------------|------|----------|
| `POST /api/v3/synapse/process-mining/performance` | 활동별 소요시간/빈도 통계 | 시뮬레이션 기저 데이터 조회 |
| `GET /api/v3/synapse/process-mining/bottlenecks` | 현재 병목 활동 식별 | bottleneck_shift 계산 |
| `GET /api/v3/synapse/process-mining/variants` | 프로세스 경로 확률 분포 | routing 변경 시뮬레이션 |

- **Synapse 불가 시**: 502 `SYNAPSE_UNAVAILABLE` 반환. 프로세스 시뮬레이션 외 재무 What-if 시나리오(§1~§9)는 Synapse 독립적으로 정상 동작한다.
- **API 스펙**: Synapse [process-mining-api.md](../../../synapse/docs/02_api/process-mining-api.md) 참조.

---

## 엔드포인트 목록

| Method | Path | 설명 | 상태 | 근거(구현/티켓) |
|--------|------|------|------|------------------|
| POST | `/what-if` | 시나리오 생성 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/what-if` | 시나리오 목록 조회 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/what-if/{scenario_id}` | 시나리오 상세 조회 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| PUT | `/what-if/{scenario_id}` | 시나리오 수정 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| DELETE | `/what-if/{scenario_id}` | 시나리오 삭제 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/what-if/{scenario_id}/compute` | 시나리오 계산 실행 (비동기) | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/what-if/{scenario_id}/status` | 계산 상태 조회 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/what-if/{scenario_id}/result` | 계산 결과 조회 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| GET | `/what-if/compare` | 다중 시나리오 비교 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/what-if/{scenario_id}/sensitivity` | 민감도 분석 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/what-if/{scenario_id}/breakeven` | 전환점 분석 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |
| POST | `/what-if/process-simulation` | 프로세스 시간축 시뮬레이션 | Implemented | `docs/implementation-plans/vision/92_sprint5-ticket-board.md` |

---

## 1. 시나리오 생성

### POST `/api/v3/cases/{case_id}/what-if`

새로운 비즈니스 시나리오를 생성한다.

#### Request

```json
{
  "scenario_name": "10년 실행 낙관 시나리오",
  "scenario_type": "OPTIMISTIC",
  "base_scenario_id": null,
  "description": "EBITDA 10% 성장, 금리 3.5% 가정",
  "parameters": {
    "execution_period_years": 10,
    "interest_rate": 3.5,
    "ebitda_growth_rate": 10.0,
    "asset_disposal_plan": [
      {
        "asset_id": "550e8400-e29b-41d4-a716-446655440001",
        "disposal_year": 2,
        "estimated_value": 500000000,
        "disposal_cost_ratio": 5.0
      }
    ],
    "operating_cost_ratio": 65.0,
    "discount_rate": 8.0,
    "priority_allocation_rate": 100.0,
    "secured_allocation_rate": 80.0,
    "general_allocation_rate": 35.0,
    "custom_overrides": null
  },
  "constraints": [
    {
      "constraint_type": "legal_minimum",
      "parameter_path": "allocation.general_rate",
      "operator": ">=",
      "value": 15.0,
      "description": "일반 배분율 >= 최소 성과 기준 15%",
      "is_hard": true
    },
    {
      "constraint_type": "operating_fund",
      "parameter_path": "cash_balance.minimum",
      "operator": ">=",
      "value": 100000000,
      "description": "최소 운영자금 1억원 확보",
      "is_hard": true
    },
    {
      "constraint_type": "dscr",
      "parameter_path": "dscr.annual",
      "operator": ">=",
      "value": 1.0,
      "description": "연간 DSCR >= 1.0",
      "is_hard": false
    }
  ]
}
```

#### 필드 명세

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|:----:|:--------:|------|
| `scenario_name` | string | Y | N | 시나리오 이름 (최대 200자) |
| `scenario_type` | enum | Y | N | BASELINE, OPTIMISTIC, PESSIMISTIC, STRESS, CUSTOM |
| `base_scenario_id` | UUID | N | Y | 복사 원본 시나리오 ID. null이면 케이스 현재값 기반 |
| `description` | string | N | Y | 설명 (최대 1000자) |
| `parameters` | object | Y | N | 시나리오 파라미터 |
| `parameters.execution_period_years` | integer | Y | N | 실행 기간 (1~30년) |
| `parameters.interest_rate` | decimal | Y | N | 적용 금리 (0.0~100.0%) |
| `parameters.ebitda_growth_rate` | decimal | Y | N | EBITDA 성장률 (-100.0~1000.0%) |
| `parameters.asset_disposal_plan` | array | N | Y | 자산 매각 계획 |
| `parameters.operating_cost_ratio` | decimal | Y | N | 운영비 비율 (0.0~100.0%) |
| `parameters.discount_rate` | decimal | Y | N | 할인율/WACC (0.0~100.0%) |
| `parameters.priority_allocation_rate` | decimal | Y | N | 우선 배분율 (0.0~100.0%) |
| `parameters.secured_allocation_rate` | decimal | Y | N | 담보 배분율 (0.0~100.0%) |
| `parameters.general_allocation_rate` | decimal | Y | N | 일반 배분율 (0.0~100.0%) |
| `parameters.custom_overrides` | object | N | Y | 사용자 정의 파라미터 오버라이드 |
| `constraints` | array | N | Y | 제약조건 목록 (없으면 기본 법적 제약만 적용) |

#### Response (201 Created)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440010",
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "scenario_name": "10년 실행 낙관 시나리오",
  "scenario_type": "OPTIMISTIC",
  "status": "DRAFT",
  "parameters": { },
  "constraints": [ ],
  "created_at": "2026-02-19T10:30:00Z",
  "updated_at": "2026-02-19T10:30:00Z",
  "created_by": "550e8400-e29b-41d4-a716-446655440099"
}
```

---

## 2. 시나리오 수정

### PUT `/api/v3/cases/{case_id}/what-if/{scenario_id}`

시나리오 파라미터를 수정한다. **DRAFT/READY 상태에서만 가능**.
파라미터 변경 시 이전 결과가 있으면 상태가 DRAFT로 리셋된다.

#### Request

```json
{
  "scenario_name": "10년 실행 낙관 시나리오 (수정)",
  "parameters": {
    "interest_rate": 4.0,
    "ebitda_growth_rate": 8.0
  }
}
```

모든 필드는 선택적이다. 전달된 필드만 업데이트된다 (Partial Update).

#### Response (200 OK)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440010",
  "status": "DRAFT",
  "parameters": {
    "interest_rate": 4.0,
    "ebitda_growth_rate": 8.0
  },
  "updated_at": "2026-02-19T10:35:00Z"
}
```

---

## 3. 시나리오 계산 실행

### POST `/api/v3/cases/{case_id}/what-if/{scenario_id}/compute`

scipy 솔버를 비동기로 실행한다.

#### Request

```json
{
  "force_recompute": false
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|:----:|------|
| `force_recompute` | boolean | N | true면 이미 COMPLETED인 시나리오도 재계산 |

#### Response (202 Accepted)

```json
{
  "scenario_id": "550e8400-e29b-41d4-a716-446655440010",
  "status": "COMPUTING",
  "estimated_duration_seconds": 15,
  "poll_url": "/api/v3/cases/{case_id}/what-if/{scenario_id}/status"
}
```

---

## 4. 계산 상태 조회

### GET `/api/v3/cases/{case_id}/what-if/{scenario_id}/status`

#### Response (200 OK)

```json
{
  "scenario_id": "550e8400-e29b-41d4-a716-446655440010",
  "status": "COMPUTING",
  "progress_pct": 45,
  "started_at": "2026-02-19T10:36:00Z",
  "elapsed_seconds": 7
}
```

가능한 status 값: `DRAFT`, `READY`, `COMPUTING`, `COMPLETED`, `FAILED`, `ARCHIVED`

---

## 5. 계산 결과 조회

### GET `/api/v3/cases/{case_id}/what-if/{scenario_id}/result`

**COMPLETED 상태에서만 조회 가능**.

#### Response (200 OK)

```json
{
  "scenario_id": "550e8400-e29b-41d4-a716-446655440010",
  "scenario_name": "10년 실행 낙관 시나리오",
  "status": "COMPLETED",
  "computed_at": "2026-02-19T10:36:15Z",
  "solver_iterations": 247,
  "is_feasible": true,
  "feasibility_score": 0.85,
  "summary": {
    "total_allocation": 5200000000,
    "total_obligations": 10000000000,
    "overall_allocation_rate": 0.52,
    "execution_period_years": 10,
    "npv_at_wacc": 3800000000
  },
  "by_year": [
    {
      "year": 1,
      "revenue": 3000000000,
      "ebitda": 600000000,
      "interest_expense": 200000000,
      "operating_cost": 1950000000,
      "net_cashflow": 400000000,
      "allocation_amount": 320000000,
      "cumulative_allocation": 320000000,
      "cash_balance": 180000000,
      "dscr": 1.6
    }
  ],
  "by_stakeholder_class": [
    {
      "class": "priority",
      "total_obligation": 250000000,
      "allocation_amount": 250000000,
      "allocation_rate": 1.00
    },
    {
      "class": "secured",
      "total_obligation": 3000000000,
      "allocation_amount": 2400000000,
      "allocation_rate": 0.80
    },
    {
      "class": "unsecured",
      "total_obligation": 6000000000,
      "allocation_amount": 2100000000,
      "allocation_rate": 0.35
    }
  ],
  "constraints_met": [
    {
      "constraint_type": "legal_minimum",
      "description": "일반 배분율 >= 최소 성과 기준 15%",
      "actual_value": 35.0,
      "threshold": 15.0,
      "satisfied": true
    }
  ],
  "warnings": []
}
```

---

## 6. 다중 시나리오 비교

### GET `/api/v3/cases/{case_id}/what-if/compare`

#### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|:----:|------|
| `ids` | string | Y | 비교할 시나리오 ID (쉼표 구분, 최대 5개) |

#### Request 예시

```
GET /api/v3/cases/{case_id}/what-if/compare?ids=uuid1,uuid2,uuid3
```

#### Response (200 OK)

```json
{
  "scenarios": [
    {
      "id": "uuid1",
      "name": "8년 낙관",
      "feasibility_score": 0.85,
      "total_allocation": 5200000000,
      "overall_rate": 0.52,
      "period_years": 8
    },
    {
      "id": "uuid2",
      "name": "12년 보수",
      "feasibility_score": 0.92,
      "total_allocation": 6100000000,
      "overall_rate": 0.61,
      "period_years": 12
    }
  ],
  "comparison_matrix": {
    "by_year": [
      {"year": 1, "uuid1": 650000000, "uuid2": 450000000},
      {"year": 2, "uuid1": 690000000, "uuid2": 480000000}
    ],
    "by_stakeholder_class": [
      {"class": "unsecured", "uuid1": 0.35, "uuid2": 0.45}
    ]
  },
  "recommendation": {
    "best_scenario_id": "uuid2",
    "reason": "실현가능성 92%로 가장 높으며, 일반 배분율 45%로 이해관계자 동의 가능성 높음"
  }
}
```

---

## 7. 민감도 분석

### POST `/api/v3/cases/{case_id}/what-if/{scenario_id}/sensitivity`

#### Request

```json
{
  "parameters_to_vary": [
    "interest_rate",
    "ebitda_growth_rate",
    "operating_cost_ratio",
    "discount_rate"
  ],
  "variation_pct": 10.0
}
```

#### Response (200 OK)

```json
{
  "scenario_id": "550e8400-e29b-41d4-a716-446655440010",
  "baseline_total_performance": 5200000000,
  "tornado_chart_data": [
    {
      "parameter": "ebitda_growth_rate",
      "parameter_label": "EBITDA 성장률",
      "base_value": 10.0,
      "high_value": 5800000000,
      "low_value": 4500000000,
      "impact": 1300000000,
      "high_pct_change": 11.5,
      "low_pct_change": -13.5
    },
    {
      "parameter": "interest_rate",
      "parameter_label": "적용 금리",
      "base_value": 4.0,
      "high_value": 4900000000,
      "low_value": 5500000000,
      "impact": 600000000,
      "high_pct_change": -5.8,
      "low_pct_change": 5.8
    }
  ]
}
```

---

## 8. 전환점 분석

### POST `/api/v3/cases/{case_id}/what-if/{scenario_id}/breakeven`

#### Request

```json
{
  "parameter": "ebitda_growth_rate",
  "threshold_metric": "is_feasible",
  "search_range": [-50.0, 50.0]
}
```

#### Response (200 OK)

```json
{
  "scenario_id": "550e8400-e29b-41d4-a716-446655440010",
  "parameter": "ebitda_growth_rate",
  "breakeven_value": -2.3,
  "description": "EBITDA 성장률이 -2.3%일 때 실행 계획이 실현 불가능해짐",
  "current_value": 10.0,
  "margin": 12.3,
  "margin_description": "현재 가정 대비 12.3%p의 안전 마진"
}
```

---

## 9. 시나리오 삭제

### DELETE `/api/v3/cases/{case_id}/what-if/{scenario_id}`

**COMPUTING 상태에서는 삭제 불가** (먼저 취소해야 함).

#### Response (204 No Content)

---

## 10. 프로세스 시간축 시뮬레이션

### POST `/api/v3/cases/{case_id}/what-if/process-simulation`

Synapse 프로세스 마이닝 데이터 기반으로 활동 소요시간/자원 배분 변경 시 전체 주기 시간 영향을 시뮬레이션한다.

#### Request

```json
{
  "process_model_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "scenario_name": "승인 시간 단축 시나리오",
  "description": "승인 프로세스를 4시간→2시간으로 단축",
  "parameter_changes": [
    {
      "activity": "승인",
      "change_type": "duration",
      "duration_change": -7200
    }
  ],
  "sla_threshold_seconds": null
}
```

#### 필드 명세

| 필드 | 타입 | 필수 | Nullable | 설명 |
|------|------|:----:|:--------:|------|
| `process_model_id` | UUID | Y | N | Synapse 프로세스 모델 ID |
| `scenario_name` | string | Y | N | 시나리오 이름 (최대 200자) |
| `description` | string | N | Y | 설명 (최대 1000자) |
| `parameter_changes` | array | Y | N | 파라미터 변경 목록 (최소 1개) |
| `parameter_changes[].activity` | string | Y | N | 변경 대상 활동명 |
| `parameter_changes[].change_type` | enum | Y | N | `duration`, `resource`, `routing` |
| `parameter_changes[].duration_change` | integer | N* | Y | 소요시간 변경 (초). change_type=duration일 때 필수. 음수=단축 |
| `parameter_changes[].resource_change` | decimal | N* | Y | 자원 배율. change_type=resource일 때 필수. 2.0=2배 |
| `parameter_changes[].routing_probability` | decimal | N* | Y | 라우팅 확률 (0.0~1.0). change_type=routing일 때 필수 |
| `sla_threshold_seconds` | integer | N | Y | SLA 기준 변경 (초). null이면 기존 SLA 기준 사용 |

#### Response (200 OK)

```json
{
  "simulation_id": "550e8400-e29b-41d4-a716-446655440050",
  "process_model_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "scenario_name": "승인 시간 단축 시나리오",
  "computed_at": "2026-02-20T10:00:00Z",
  "original_cycle_time": 259200,
  "simulated_cycle_time": 252000,
  "cycle_time_change": -7200,
  "cycle_time_change_pct": -2.8,
  "cycle_time_change_label": "전체 주기 시간 2시간 단축 (3일 → 2일 22시간)",
  "bottleneck_shift": null,
  "affected_kpis": [
    {
      "kpi": "avg_cycle_time",
      "kpi_label": "평균 주기 시간",
      "original": 259200,
      "simulated": 252000,
      "change_pct": -2.8
    },
    {
      "kpi": "sla_violation_rate",
      "kpi_label": "SLA 위반율",
      "original": 0.15,
      "simulated": 0.12,
      "change_pct": -20.0
    }
  ],
  "by_activity": [
    {
      "activity": "승인",
      "original_duration": 14400,
      "simulated_duration": 7200,
      "change": -7200,
      "is_on_critical_path": true
    },
    {
      "activity": "검토",
      "original_duration": 28800,
      "simulated_duration": 28800,
      "change": 0,
      "is_on_critical_path": true
    },
    {
      "activity": "배송",
      "original_duration": 86400,
      "simulated_duration": 86400,
      "change": 0,
      "is_on_critical_path": true
    }
  ],
  "critical_path": {
    "original": ["접수", "승인", "재고확인", "배송"],
    "simulated": ["접수", "승인", "재고확인", "배송"]
  }
}
```

#### 응답 필드 상세

| 필드 | 타입 | Nullable | 설명 |
|------|------|:--------:|------|
| `original_cycle_time` | integer | N | 현재 전체 주기 시간 (초) |
| `simulated_cycle_time` | integer | N | 시뮬레이션 후 전체 주기 시간 (초) |
| `cycle_time_change` | integer | N | 주기 시간 변화량 (초). 음수=단축 |
| `cycle_time_change_pct` | decimal | N | 주기 시간 변화율 (%) |
| `bottleneck_shift` | object | Y | 병목 이동 정보. 병목 변화 없으면 null |
| `bottleneck_shift.original` | string | N | 기존 병목 활동명 |
| `bottleneck_shift.new` | string | N | 새 병목 활동명 |
| `bottleneck_shift.description` | string | N | 병목 이동 설명 |
| `affected_kpis` | array | N | 영향받는 KPI 목록 |
| `by_activity` | array | N | 활동별 시간 변화 상세 |
| `critical_path` | object | N | 임계 경로 변경 전/후 |

#### 병목 이동 응답 예시

자원 변경으로 병목이 이동하는 경우:

```json
{
  "parameter_changes": [
    {"activity": "승인", "change_type": "resource", "resource_change": 3.0}
  ]
}
```

```json
{
  "bottleneck_shift": {
    "original": "승인",
    "new": "검수",
    "description": "병목이 '승인'에서 '검수'(으)로 이동. 승인 자원 3배 증가로 승인 대기시간 해소되었으나, 검수 단계가 새로운 병목으로 부상."
  }
}
```

---

## 에러 코드

| HTTP | 코드 | 의미 | 사용자 표시 |
|:----:|------|------|-----------|
| 400 | `INVALID_PARAMETERS` | 파라미터 유효성 검증 실패 | "실행 기간은 1~30년이어야 합니다" |
| 400 | `SCENARIO_NOT_READY` | DRAFT 상태에서 compute 시도 | "필수 파라미터를 모두 입력해 주세요" |
| 404 | `SCENARIO_NOT_FOUND` | 존재하지 않는 시나리오 | "시나리오를 찾을 수 없습니다" |
| 409 | `SCENARIO_COMPUTING` | 이미 계산 중인 시나리오에 재요청 | "이미 계산 진행 중입니다" |
| 409 | `SCENARIO_COMPUTING_DELETE` | 계산 중 삭제 시도 | "계산 중인 시나리오는 삭제할 수 없습니다" |
| 422 | `SOLVER_INFEASIBLE` | 제약조건 충족 불가 | "현재 제약조건으로는 실현 가능한 실행 계획을 찾을 수 없습니다" |
| 504 | `SOLVER_TIMEOUT` | 솔버 타임아웃 (60초 초과) | "계산 시간이 초과되었습니다. 제약조건을 완화해 보세요" |
| 400 | `INVALID_ACTIVITY` | 존재하지 않는 활동명 지정 | "활동 'X'이(가) 프로세스 모델에 존재하지 않습니다" |
| 400 | `NEGATIVE_DURATION` | 변경 후 소요시간이 음수 | "변경 후 활동 소요시간이 음수가 됩니다" |
| 404 | `PROCESS_MODEL_NOT_FOUND` | Synapse 프로세스 모델 없음 | "프로세스 모델을 찾을 수 없습니다" |
| 502 | `SYNAPSE_UNAVAILABLE` | Synapse 서비스 연결 실패 | "프로세스 마이닝 서비스에 연결할 수 없습니다" |

---

## 권한 (Permissions)

| 작업 | 필요 역할 | 프로젝트 범위 |
|------|----------|-------------|
| 시나리오 조회 | VIEWER 이상 | 해당 케이스 접근 권한 |
| 시나리오 생성/수정 | TRUSTEE 이상 | 해당 케이스 관리 권한 |
| 시나리오 삭제 | ADMIN | 해당 케이스 관리 권한 |
| 계산 실행 | TRUSTEE 이상 | 해당 케이스 관리 권한 |

<!-- affects: 04_frontend, 03_backend/scenario-solver.md, 00_overview/system-overview.md -->
<!-- requires-update: 01_architecture/what-if-engine.md, 04_frontend/what-if-ui.md -->
