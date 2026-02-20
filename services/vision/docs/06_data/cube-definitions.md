# 비즈니스 도메인 큐브 정의

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 3.6
> **근거**: 01_architecture/olap-engine.md, 06_data/data-warehouse.md

---

## 이 문서가 답하는 질문

- 비즈니스 분석 큐브의 차원과 측도는 무엇인가?
- 현금흐름 큐브의 차원과 측도는 무엇인가?
- 각 차원의 계층 구조와 드릴다운 경로는?
- 측도의 집계 방식과 의미는?

---

## 1. 비즈니스 분석 큐브 (BusinessAnalysisCube)

### 1.1 개요

| 항목 | 값 |
|------|-----|
| **큐브 이름** | BusinessAnalysisCube |
| **팩트 테이블** | mv_business_fact |
| **차원 수** | 4 (비즈니스 유형, 대상 조직, 시간, 이해관계자) |
| **측도 수** | 6 |
| **주요 질의** | "유형별/기간별/이해관계자별 비즈니스 통계 및 KPI" |

### 1.2 차원 (Dimensions)

#### 비즈니스 유형 차원 (CaseType)

```
CaseType
├─ CaseCategory (비즈니스 대분류)
│   ├─ 구조조정
│   └─ 성장전략
├─ CaseType (비즈니스 유형)
│   ├─ 비용최적화
│   ├─ 수익확대
│   ├─ 사업재편
│   └─ 시장확장
└─ CaseStatus (비즈니스 상태)
    ├─ DRAFT
    ├─ FILED
    ├─ IN_PROGRESS
    ├─ PLAN_SUBMITTED
    ├─ PLAN_APPROVED
    ├─ EXECUTING
    ├─ COMPLETED
    └─ ARCHIVED
```

| 레벨 | 컬럼 | 타입 | 카디널리티 |
|------|------|------|:---------:|
| CaseCategory | `category` | String | 2 |
| CaseType | `type_name` | String | ~8 |
| CaseStatus | `status` | String | ~10 |

#### 대상 조직 차원 (Organization)

```
Organization
├─ Region (지역)
│   ├─ 서울
│   ├─ 경기
│   ├─ 부산
│   └─ ...
├─ Industry (업종)
│   ├─ 제조업
│   ├─ 서비스업
│   ├─ 건설업
│   ├─ 유통업
│   └─ ...
└─ CompanyName (회사명)
    └─ 개별 회사
```

| 레벨 | 컬럼 | 타입 | 카디널리티 |
|------|------|------|:---------:|
| Region | `region` | String | ~17 |
| Industry | `industry` | String | ~20 |
| CompanyName | `company_name` | String | High |

#### 시간 차원 (Time)

```
Time
├─ Year (연도)
│   ├─ 2020
│   ├─ 2021
│   └─ ...
├─ Quarter (분기)
│   ├─ Q1
│   ├─ Q2
│   ├─ Q3
│   └─ Q4
└─ Month (월)
    ├─ 1
    ├─ 2
    └─ ...12
```

| 레벨 | 컬럼 | 타입 | 카디널리티 |
|------|------|------|:---------:|
| Year | `filing_year` | Numeric | ~10 |
| Quarter | `quarter` | String | 4 |
| Month | `month` | Numeric | 12 |

#### 이해관계자 유형 차원 (Stakeholder)

```
Stakeholder
├─ StakeholderType (이해관계자 유형)
│   ├─ 금융기관
│   ├─ 거래처
│   ├─ 개인
│   ├─ 국가/지자체
│   └─ 기타
├─ StakeholderClass (이해관계자 분류)
│   ├─ 핵심 이해관계자
│   ├─ 주요 이해관계자
│   └─ 일반 이해관계자
└─ AmountBand (금액 구간)
    ├─ ~1억
    ├─ 1억~10억
    ├─ 10억~100억
    └─ 100억~
```

| 레벨 | 컬럼 | 타입 | 카디널리티 |
|------|------|------|:---------:|
| StakeholderType | `stakeholder_type` | String | ~5 |
| StakeholderClass | `stakeholder_class` | String | 3 |
| AmountBand | `amount_band` | String | ~4 |

### 1.3 측도 (Measures)

| 측도 이름 | 컬럼 | 집계 | 형식 | 의미 |
|----------|------|------|------|------|
| CaseCount | `case_id` | COUNT DISTINCT | #,### | 고유 비즈니스 건수 |
| TotalAmount | `amount` | SUM | #,### | 총 금액 (원) |
| AdmittedRatio | `admitted_ratio` | AVG | 0.00% | 평균 인정 비율 |
| AvgPerformanceRate | `performance_rate` | AVG | 0.00% | 평균 성과 지표(KPI) |
| AvgCaseDuration | `case_duration_days` | AVG | #,### | 평균 비즈니스 처리 기간 (일) |
| StakeholderSatisfactionRate | `satisfaction_rate` | AVG | 0.00% | 평균 이해관계자 만족도 |

---

## 2. 현금흐름 큐브 (CashflowCube)

### 2.1 개요

| 항목 | 값 |
|------|-----|
| **큐브 이름** | CashflowCube |
| **팩트 테이블** | mv_cashflow_fact |
| **차원 수** | 3 (비즈니스 유형, 대상 조직, 시간) |
| **측도 수** | 3 |
| **주요 질의** | "비즈니스별/연도별 현금흐름 추이와 예측 정확도" |

### 2.2 차원

| 차원 | 공유 | 설명 |
|------|:----:|------|
| CaseType | BusinessAnalysisCube과 공유 | 비즈니스 유형 |
| Organization | BusinessAnalysisCube과 공유 | 대상 조직 정보 |
| FiscalTime | 전용 | 회계연도 기반 시간 |

#### 회계연도 시간 차원 (FiscalTime)

```
FiscalTime
├─ FiscalYear (회계연도)
│   ├─ 2022
│   └─ ...
├─ FiscalQuarter (회계분기)
└─ EntryType (항목 유형)
    ├─ ACTUAL (실적)
    ├─ BUDGET (예산)
    └─ FORECAST (예측)
```

### 2.3 측도

| 측도 이름 | 컬럼 | 집계 | 형식 | 의미 |
|----------|------|------|------|------|
| Amount | `amount` | SUM | #,### | 현금흐름 금액 (원) |
| GrowthRate | `growth_rate` | AVG | 0.00% | 전년 대비 성장률 |
| ForecastAccuracy | `forecast_accuracy` | AVG | 0.00% | 예측 정확도 |

---

## 3. 드릴다운 경로 (Drill-down Paths)

### 3.1 비즈니스 분석 큐브

```
[전체] → CaseCategory(구조조정/성장전략) → CaseType(비용최적화/수익확대) → CaseStatus → 개별 비즈니스
[전체] → Year → Quarter → Month → 개별 비즈니스
[전체] → Region → Industry → CompanyName → 개별 비즈니스
[전체] → StakeholderType → StakeholderClass → AmountBand → 개별 이해관계자
```

### 3.2 분석 시나리오 예시

| 질의 | 행 | 열 | 측도 | 필터 |
|------|-----|-----|------|------|
| "연도별 비즈니스 건수" | Time.Year | - | CaseCount | CaseCategory=구조조정 |
| "업종별 KPI 비교" | Organization.Industry | - | AvgPerformanceRate | - |
| "이해관계자별 연도별 만족도" | Stakeholder.StakeholderClass | Time.Year | StakeholderSatisfactionRate | - |
| "지역별 비즈니스 유형 분포" | Organization.Region | CaseType.CaseType | CaseCount | - |

---

## 4. 큐브 XML 파일 위치

```
services/vision/cubes/
├─ business_analysis_cube.xml    # 비즈니스 분석 큐브 (Mondrian XML)
└─ cashflow_cube.xml              # 현금흐름 큐브 (Mondrian XML)
```

<!-- affects: 02_api/olap-api.md, 03_backend/mondrian-parser.md -->
<!-- requires-update: 06_data/data-warehouse.md -->
