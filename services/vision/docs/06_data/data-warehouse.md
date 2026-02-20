# DW 스키마 (팩트/디멘전 테이블)

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **Phase**: 3.6
> **근거**: ADR-003, 01_architecture/olap-engine.md, 06_data/cube-definitions.md

---

## 이 문서가 답하는 질문

- Materialized View로 구현하는 팩트/디멘전 테이블의 DDL은?
- OLTP 테이블에서 어떻게 데이터를 추출하는가?
- CONCURRENTLY REFRESH를 위한 UNIQUE INDEX는?
- Star Schema의 조인 관계는?

---

## 1. Star Schema 구조

```
                    ┌──────────────┐
                    │ dim_time     │
                    │ ─────────    │
                    │ id (PK)     │
                    │ filing_year  │
                    │ quarter      │
                    │ month        │
                    └──────┬───────┘
                           │
┌──────────────┐   ┌──────┴───────────────┐   ┌──────────────┐
│dim_case_type │   │ mv_business_fact      │   │dim_stk_type  │
│ ─────────    │   │ ──────────────────    │   │ ─────────    │
│ id (PK)     │───│ case_type_id (FK)    │───│ id (PK)     │
│ category     │   │ org_id (FK)          │   │ stk_type     │
│ type_name    │   │ time_id (FK)         │   │ stk_class    │
│ status       │   │ stk_type_id (FK)     │   │ amount_band  │
└──────────────┘   │                      │   └──────────────┘
                    │ case_id             │
                    │ amount               │
                    │ admitted_ratio       │
                    │ performance_rate     │
                    │ case_duration_days   │
┌──────────────┐   │ satisfaction_rate     │
│ dim_org      │   └──────────────────────┘
│ ─────────    │           │
│ id (PK)     │───────────┘
│ region       │
│ industry     │
│ org_name     │
└──────────────┘
```

---

## 2. 디멘전 테이블 (Materialized View)

### 2.1 dim_case_type

```sql
CREATE MATERIALIZED VIEW dim_case_type AS
SELECT
    ROW_NUMBER() OVER (ORDER BY case_type, status) AS id,
    CASE
        WHEN case_type IN ('COST_OPTIMIZATION', 'RESTRUCTURING') THEN '구조조정'
        WHEN case_type IN ('REVENUE_EXPANSION', 'MARKET_EXPANSION') THEN '성장전략'
        ELSE '기타'
    END AS category,
    CASE
        WHEN case_type = 'COST_OPTIMIZATION' THEN '비용최적화'
        WHEN case_type = 'RESTRUCTURING' THEN '사업재편'
        WHEN case_type = 'REVENUE_EXPANSION' THEN '수익확대'
        WHEN case_type = 'MARKET_EXPANSION' THEN '시장확장'
        ELSE case_type
    END AS type_name,
    status
FROM (
    SELECT DISTINCT case_type, status
    FROM cases
) sub;

CREATE UNIQUE INDEX idx_dim_case_type_pk ON dim_case_type(id);
CREATE INDEX idx_dim_case_type_category ON dim_case_type(category);
```

### 2.2 dim_org

```sql
CREATE MATERIALIZED VIEW dim_org AS
SELECT
    c.id AS id,
    COALESCE(c.metadata->>'region', '미분류') AS region,
    COALESCE(c.metadata->>'industry', '미분류') AS industry,
    c.org_name AS org_name
FROM cases c
WHERE c.org_name IS NOT NULL;

CREATE UNIQUE INDEX idx_dim_org_pk ON dim_org(id);
CREATE INDEX idx_dim_org_region ON dim_org(region);
CREATE INDEX idx_dim_org_industry ON dim_org(industry);
```

### 2.3 dim_time

```sql
CREATE MATERIALIZED VIEW dim_time AS
SELECT
    ROW_NUMBER() OVER (ORDER BY filing_year, month) AS id,
    filing_year,
    'Q' || CEIL(month / 3.0)::INT AS quarter,
    month
FROM (
    SELECT DISTINCT
        EXTRACT(YEAR FROM filing_date)::INT AS filing_year,
        EXTRACT(MONTH FROM filing_date)::INT AS month
    FROM cases
    WHERE filing_date IS NOT NULL
) sub;

CREATE UNIQUE INDEX idx_dim_time_pk ON dim_time(id);
CREATE INDEX idx_dim_time_year ON dim_time(filing_year);
```

### 2.4 dim_stakeholder_type

```sql
CREATE MATERIALIZED VIEW dim_stakeholder_type AS
SELECT
    ROW_NUMBER() OVER (ORDER BY stakeholder_type, stakeholder_class) AS id,
    stakeholder_type,
    stakeholder_class,
    CASE
        WHEN s.amount <= 100000000 THEN '~1억'
        WHEN s.amount <= 1000000000 THEN '1억~10억'
        WHEN s.amount <= 10000000000 THEN '10억~100억'
        ELSE '100억~'
    END AS amount_band
FROM (
    SELECT DISTINCT
        s.stakeholder_type,
        s.stakeholder_class,
        s.amount
    FROM stakeholders s
) sub;

CREATE UNIQUE INDEX idx_dim_stakeholder_type_pk ON dim_stakeholder_type(id);
CREATE INDEX idx_dim_stakeholder_type_type ON dim_stakeholder_type(stakeholder_type);
```

---

## 3. 팩트 테이블 (Materialized View)

### 3.1 mv_business_fact

```sql
CREATE MATERIALIZED VIEW mv_business_fact AS
SELECT
    dct.id AS case_type_id,
    do.id AS org_id,
    dt.id AS time_id,
    dst.id AS stk_type_id,

    c.id AS case_id,
    s.amount AS amount,
    CASE
        WHEN s.status = 'ADMITTED' THEN 1.0
        WHEN s.status = 'PARTIALLY_ADMITTED' THEN 0.5
        ELSE 0.0
    END AS admitted_ratio,
    COALESCE(pr.performance_rate, 0.0) AS performance_rate,
    EXTRACT(DAY FROM COALESCE(c.completed_at, NOW()) - c.filing_date)::INT
        AS case_duration_days,
    COALESCE(
        pr.actual_amount::DECIMAL / NULLIF(s.amount, 0),
        0.0
    ) AS satisfaction_rate

FROM cases c
JOIN stakeholders s ON s.case_id = c.id
LEFT JOIN performance_records pr ON pr.stakeholder_id = s.id

-- Join to dimension views
JOIN dim_case_type dct ON dct.type_name = (
    CASE
        WHEN c.case_type = 'COST_OPTIMIZATION' THEN '비용최적화'
        WHEN c.case_type = 'RESTRUCTURING' THEN '사업재편'
        WHEN c.case_type = 'REVENUE_EXPANSION' THEN '수익확대'
        WHEN c.case_type = 'MARKET_EXPANSION' THEN '시장확장'
        ELSE c.case_type
    END
) AND dct.status = c.status
JOIN dim_org do ON do.id = c.id
JOIN dim_time dt ON dt.filing_year = EXTRACT(YEAR FROM c.filing_date)::INT
    AND dt.month = EXTRACT(MONTH FROM c.filing_date)::INT
JOIN dim_stakeholder_type dst ON dst.stakeholder_type = s.stakeholder_type
    AND dst.stakeholder_class = s.stakeholder_class;

-- UNIQUE INDEX for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_mv_business_fact_pk
    ON mv_business_fact(case_type_id, org_id, time_id, stk_type_id, case_id);
```

### 3.2 mv_cashflow_fact

```sql
CREATE MATERIALIZED VIEW mv_cashflow_fact AS
SELECT
    dct.id AS case_type_id,
    do.id AS org_id,
    cfe.fiscal_year,
    cfe.fiscal_quarter,
    cfe.entry_type,        -- 'ACTUAL', 'BUDGET', 'FORECAST'

    cfe.case_id,
    cfe.amount,
    LAG(cfe.amount) OVER (
        PARTITION BY cfe.case_id, cfe.entry_type
        ORDER BY cfe.fiscal_year, cfe.fiscal_quarter
    ) AS prev_amount,
    CASE
        WHEN LAG(cfe.amount) OVER (
            PARTITION BY cfe.case_id, cfe.entry_type
            ORDER BY cfe.fiscal_year, cfe.fiscal_quarter
        ) > 0 THEN
            (cfe.amount - LAG(cfe.amount) OVER (
                PARTITION BY cfe.case_id, cfe.entry_type
                ORDER BY cfe.fiscal_year, cfe.fiscal_quarter
            ))::DECIMAL / LAG(cfe.amount) OVER (
                PARTITION BY cfe.case_id, cfe.entry_type
                ORDER BY cfe.fiscal_year, cfe.fiscal_quarter
            )
        ELSE 0.0
    END AS growth_rate

FROM cash_flow_entries cfe
JOIN cases c ON cfe.case_id = c.id
JOIN dim_case_type dct ON dct.status = c.status
JOIN dim_org do ON do.id = c.id;

CREATE UNIQUE INDEX idx_mv_cashflow_fact_pk
    ON mv_cashflow_fact(case_type_id, org_id, case_id, fiscal_year, fiscal_quarter, entry_type);
```

---

## 4. REFRESH 순서

디멘전 → 팩트 순서로 REFRESH해야 한다 (팩트가 디멘전을 참조하므로).

```
1. REFRESH MATERIALIZED VIEW CONCURRENTLY dim_case_type;
2. REFRESH MATERIALIZED VIEW CONCURRENTLY dim_org;
3. REFRESH MATERIALIZED VIEW CONCURRENTLY dim_time;
4. REFRESH MATERIALIZED VIEW CONCURRENTLY dim_stakeholder_type;
5. REFRESH MATERIALIZED VIEW CONCURRENTLY mv_business_fact;
6. REFRESH MATERIALIZED VIEW CONCURRENTLY mv_cashflow_fact;
```

---

## 결정 사항 (Decisions)

- Materialized View 기반 Star Schema (ADR-003)
- 별도 DW 인스턴스 불필요 (동일 PostgreSQL)
- CONCURRENTLY REFRESH로 무중단 갱신

## 사실 (Facts)

- 모든 MV에 UNIQUE INDEX 필수 (CONCURRENTLY 전제)
- 디멘전은 OLTP 데이터에서 DISTINCT 추출
- 팩트는 OLTP 조인 + 계산 컬럼

## 미결정 사항 (Open Questions)

- 대규모 데이터(사건 10만건+) 시 MV REFRESH 성능 (파티셔닝 검토 필요)
- 실시간에 가까운 동기화 필요 시 MV 대신 Incremental MV 또는 CDC 검토

<!-- affects: 03_backend/etl-pipeline.md, 06_data/cube-definitions.md -->
