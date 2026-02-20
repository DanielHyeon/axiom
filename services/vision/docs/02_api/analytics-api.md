# 통계 대시보드 API

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 3.6
> **근거**: 00_overview/system-overview.md

---

## 이 문서가 답하는 질문

- 통계 대시보드에서 조회할 수 있는 집계 데이터는?
- KPI 요약 정보를 조회하는 API는?
- 시계열 추이 데이터를 조회하는 방법은?
- 대시보드 위젯별 데이터 소스 API는?

---

## 기본 정보

| 항목 | 값 |
|------|-----|
| **Base URL** | `/api/v3/analytics` |
| **인증** | Bearer JWT |
| **권한** | VIEWER 이상 |

---

## 엔드포인트 목록

| Method | Path | 설명 |
|--------|------|------|
| GET | `/analytics/summary` | 전체 KPI 요약 |
| GET | `/analytics/cases/trend` | 사건 추이 (시계열) |
| GET | `/analytics/stakeholders/distribution` | 이해관계자 분포 |
| GET | `/analytics/performance/trend` | 성과율 추이 |
| GET | `/analytics/cases/{case_id}/financial-summary` | 개별 케이스 재무 요약 |
| GET | `/analytics/dashboards` | 대시보드 위젯 구성 |

---

## 1. 전체 KPI 요약

### GET `/api/v3/analytics/summary`

#### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|:----:|------|
| `period` | string | N | `YTD` (기본), `MTD`, `QTD`, `LAST_YEAR`, `ALL` |
| `case_type` | string | N | 사건 유형 필터 (RESTRUCTURING, GROWTH, ALL) |

#### Response (200 OK)

```json
{
  "period": "YTD",
  "period_label": "2026년 누적",
  "kpis": {
    "total_cases": {
      "value": 156,
      "change_pct": 12.3,
      "change_direction": "up",
      "prev_period_value": 139
    },
    "active_cases": {
      "value": 89,
      "change_pct": -3.2,
      "change_direction": "down",
      "prev_period_value": 92
    },
    "total_obligations_amount": {
      "value": 523000000000,
      "formatted": "5,230억원",
      "change_pct": 8.7,
      "change_direction": "up"
    },
    "avg_performance_rate": {
      "value": 0.41,
      "formatted": "41.0%",
      "change_pct": 2.1,
      "change_direction": "up"
    },
    "avg_case_duration_days": {
      "value": 547,
      "formatted": "547일 (약 1.5년)",
      "change_pct": -5.3,
      "change_direction": "down"
    },
    "stakeholder_satisfaction_rate": {
      "value": 0.38,
      "formatted": "38.0%",
      "change_pct": 1.5,
      "change_direction": "up"
    }
  },
  "computed_at": "2026-02-19T10:00:00Z"
}
```

---

## 2. 사건 추이

### GET `/api/v3/analytics/cases/trend`

#### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|:----:|------|
| `granularity` | string | N | `monthly` (기본), `quarterly`, `yearly` |
| `from_date` | date | N | 시작일 (기본 1년 전) |
| `to_date` | date | N | 종료일 (기본 오늘) |
| `case_type` | string | N | 사건 유형 필터 |
| `group_by` | string | N | 추가 그룹핑 (industry, region, case_type) |

#### Response (200 OK)

```json
{
  "granularity": "monthly",
  "from_date": "2025-02-01",
  "to_date": "2026-02-19",
  "series": [
    {
      "period": "2025-02",
      "new_cases": 12,
      "completed_cases": 8,
      "active_cases": 76,
      "total_obligations_registered": 45000000000
    },
    {
      "period": "2025-03",
      "new_cases": 15,
      "completed_cases": 10,
      "active_cases": 81,
      "total_obligations_registered": 52000000000
    }
  ]
}
```

---

## 3. 이해관계자 분포

### GET `/api/v3/analytics/stakeholders/distribution`

#### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|:----:|------|
| `distribution_by` | string | Y | `stakeholder_type`, `stakeholder_class`, `amount_band`, `status` |
| `case_type` | string | N | 사건 유형 필터 |
| `year` | integer | N | 연도 필터 |

#### Response (200 OK)

```json
{
  "distribution_by": "stakeholder_type",
  "total_count": 1523,
  "total_amount": 523000000000,
  "segments": [
    {
      "label": "핵심 이해관계자",
      "count": 412,
      "count_pct": 0.27,
      "amount": 210000000000,
      "amount_pct": 0.40,
      "avg_satisfaction_rate": 0.78
    },
    {
      "label": "금융기관",
      "count": 856,
      "count_pct": 0.56,
      "amount": 250000000000,
      "amount_pct": 0.48,
      "avg_satisfaction_rate": 0.22
    },
    {
      "label": "거래처",
      "count": 255,
      "count_pct": 0.17,
      "amount": 63000000000,
      "amount_pct": 0.12,
      "avg_satisfaction_rate": 0.95
    }
  ]
}
```

---

## 4. 성과율 추이

### GET `/api/v3/analytics/performance/trend`

#### Query Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|:----:|------|
| `granularity` | string | N | `quarterly` (기본), `yearly` |
| `stakeholder_type` | string | N | 이해관계자 유형 필터 |
| `case_type` | string | N | 사건 유형 필터 |

#### Response (200 OK)

```json
{
  "granularity": "quarterly",
  "series": [
    {
      "period": "2025-Q1",
      "avg_performance_rate": 0.38,
      "secured_rate": 0.75,
      "general_rate": 0.18,
      "priority_rate": 0.93,
      "case_count": 35
    },
    {
      "period": "2025-Q2",
      "avg_performance_rate": 0.41,
      "secured_rate": 0.78,
      "general_rate": 0.22,
      "priority_rate": 0.95,
      "case_count": 42
    }
  ]
}
```

---

## 5. 개별 케이스 재무 요약

### GET `/api/v3/analytics/cases/{case_id}/financial-summary`

#### Response (200 OK)

```json
{
  "case_id": "550e8400-e29b-41d4-a716-446655440000",
  "case_number": "2024-BIZ-101",
  "company_name": "ABC 주식회사",
  "financials": {
    "total_assets": 8000000000,
    "total_liabilities": 12000000000,
    "total_obligations": 10000000000,
    "verified_obligations": 8500000000,
    "pending_obligations": 1500000000,
    "debt_ratio": 1.50,
    "latest_ebitda": 600000000,
    "cash_balance": 200000000
  },
  "execution_progress": {
    "plan_total": 5200000000,
    "paid_to_date": 1040000000,
    "progress_pct": 0.20,
    "next_payment_date": "2026-06-30",
    "next_payment_amount": 260000000
  },
  "stakeholder_breakdown": [
    {"type": "priority", "count": 5, "amount": 250000000, "rate": 1.00},
    {"type": "secured", "count": 12, "amount": 3000000000, "rate": 0.80},
    {"type": "general", "count": 45, "amount": 5250000000, "rate": 0.35}
  ]
}
```

---

## 에러 코드

| HTTP | 코드 | 의미 | 사용자 표시 |
|:----:|------|------|-----------|
| 400 | `INVALID_PERIOD` | 유효하지 않은 기간 | "유효하지 않은 기간 형식입니다" |
| 400 | `INVALID_DISTRIBUTION_BY` | 지원하지 않는 분포 기준 | "지원하지 않는 분포 기준입니다" |
| 404 | `CASE_NOT_FOUND` | 존재하지 않는 케이스 | "사건을 찾을 수 없습니다" |

<!-- affects: 04_frontend -->
<!-- requires-update: 06_data/cube-definitions.md -->
