# OLAP 피벗 분석 엔진 설계

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **Phase**: 3.6
> **근거**: ADR-002 (Mondrian XML), ADR-003 (Materialized View), K-AIR data-platform-olap-main

---

## 이 문서가 답하는 질문

- OLAP 엔진은 어떤 구조로 동작하는가?
- Mondrian XML 파서는 무엇을 하며 왜 사용하는가?
- SQL 생성기는 어떻게 피벗 쿼리를 만드는가?
- ETL 파이프라인은 어떻게 OLTP에서 OLAP 데이터를 동기화하는가?
- 자연어 질의(NL→피벗)는 어떤 흐름으로 처리되는가?
- 프로세스 KPI 큐브는 어떤 차원과 측도로 구성되는가? (Synapse 연동)

---

## 1. 엔진 개요

### 1.1 K-AIR 이식 원본

K-AIR `data-platform-olap-main`에서 80% 구현된 코드를 이식한다.

| K-AIR 파일 | Vision 이식 대상 | 이식 범위 |
|------------|-----------------|----------|
| `xml_parser.py` | `engines/mondrian_parser.py` | 전체 이식 (Mondrian XML → 큐브 메타) |
| `sql_generator.py` | `engines/pivot_engine.py` | 전체 이식 (메타 → SQL 생성) |
| LangGraph 워크플로우 | `engines/nl_pivot_workflow.py` | 5노드 구조 이식, 모델 교체 |
| ETL 서비스 | `engines/etl_service.py` | Materialized View 방식으로 재설계 |
| Metadata Store | `engines/mondrian_parser.py` | 인메모리 + JSON → DB 기반으로 변경 |

### 1.2 전체 아키텍처

```
┌─ OLAP 엔진 아키텍처 ──────────────────────────────────────────┐
│                                                                 │
│  ┌──────────────────┐                                          │
│  │ Mondrian XML     │  큐브 정의 파일 (cubes/*.xml)            │
│  │ Parser           │                                          │
│  │  - 큐브 이름      │                                          │
│  │  - 팩트 테이블    │                                          │
│  │  - 디멘전/계층    │                                          │
│  │  - 측도 (집계)    │                                          │
│  │  - 조인 관계      │                                          │
│  └───────┬──────────┘                                          │
│          │ CubeMetadata                                        │
│          ▼                                                      │
│  ┌──────────────────┐                                          │
│  │ SQL Generator    │  피벗 요청 → SQL 변환                    │
│  │ (Pivot Engine)   │                                          │
│  │  - SELECT 절     │                                          │
│  │  - FROM 절 (MV)  │                                          │
│  │  - WHERE 절      │                                          │
│  │  - GROUP BY 절   │                                          │
│  │  - HAVING 절     │                                          │
│  └───────┬──────────┘                                          │
│          │ SQL string                                          │
│          ▼                                                      │
│  ┌──────────────────┐                                          │
│  │ SQL Validator    │  안전성 검증                              │
│  │  - SQLGlot 파싱  │                                          │
│  │  - 위험 키워드   │                                          │
│  │  - 테이블 화이트 │                                          │
│  │    리스트 검증   │                                          │
│  └───────┬──────────┘                                          │
│          │ validated SQL                                       │
│          ▼                                                      │
│  ┌──────────────────┐                                          │
│  │ Query Executor   │  실행 + 결과 변환                        │
│  │  - 타임아웃 30초 │                                          │
│  │  - MAX_ROWS 1000 │                                          │
│  │  - 결과 → Grid   │                                          │
│  └──────────────────┘                                          │
│                                                                 │
│  ┌──────────────────┐                                          │
│  │ ETL Service      │  OLTP → MV 동기화                        │
│  │  - full sync     │                                          │
│  │  - incremental   │                                          │
│  │  - MV REFRESH    │                                          │
│  └──────────────────┘                                          │
│                                                                 │
│  ┌──────────────────┐                                          │
│  │ NL→Pivot         │  자연어 → 피벗 파라미터                  │
│  │ (LangGraph)      │                                          │
│  │  5노드 워크플로우 │                                          │
│  └──────────────────┘                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Mondrian XML 큐브 정의

### 2.1 XML 스키마

```xml
<!-- cubes/business_analysis_cube.xml -->
<Schema name="AxiomVision">
  <Cube name="BusinessAnalysisCube" factTable="mv_business_fact">

    <!-- Dimensions -->
    <Dimension name="CaseType" foreignKey="case_type_id">
      <Hierarchy hasAll="true" primaryKey="id" table="dim_case_type">
        <Level name="CaseCategory" column="category" />
        <Level name="CaseType" column="type_name" />
        <Level name="CaseStatus" column="status" />
      </Hierarchy>
    </Dimension>

    <Dimension name="Organization" foreignKey="org_id">
      <Hierarchy hasAll="true" primaryKey="id" table="dim_org">
        <Level name="Region" column="region" />
        <Level name="Industry" column="industry" />
        <Level name="CompanyName" column="org_name" />
      </Hierarchy>
    </Dimension>

    <Dimension name="Time" foreignKey="time_id">
      <Hierarchy hasAll="true" primaryKey="id" table="dim_time">
        <Level name="Year" column="filing_year" type="Numeric" />
        <Level name="Quarter" column="quarter" />
        <Level name="Month" column="month" type="Numeric" />
      </Hierarchy>
    </Dimension>

    <Dimension name="Stakeholder" foreignKey="stk_type_id">
      <Hierarchy hasAll="true" primaryKey="id" table="dim_stakeholder_type">
        <Level name="StakeholderType" column="stakeholder_type" />
        <Level name="StakeholderClass" column="stakeholder_class" />
        <Level name="AmountBand" column="amount_band" />
      </Hierarchy>
    </Dimension>

    <!-- Measures -->
    <Measure name="CaseCount" column="case_id" aggregator="distinct-count" />
    <Measure name="TotalObligationAmount" column="obligation_amount" aggregator="sum" formatString="#,###" />
    <Measure name="AdmittedRatio" column="admitted_ratio" aggregator="avg" formatString="0.00%" />
    <Measure name="AvgPerformanceRate" column="performance_rate" aggregator="avg" formatString="0.00%" />
    <Measure name="AvgCaseDuration" column="case_duration_days" aggregator="avg" formatString="#,###" />
    <Measure name="StakeholderSatisfactionRate" column="satisfaction_rate" aggregator="avg" formatString="0.00%" />

  </Cube>
</Schema>
```

### 2.2 파서 출력 (CubeMetadata)

```python
@dataclass
class CubeMetadata:
    name: str                           # "BusinessAnalysisCube"
    fact_table: str                     # "mv_business_fact"
    dimensions: list[DimensionMeta]     # 차원 목록
    measures: list[MeasureMeta]         # 측도 목록
    joins: list[JoinMeta]              # 조인 관계

@dataclass
class DimensionMeta:
    name: str                           # "CaseType"
    foreign_key: str                    # "case_type_id"
    table: str                          # "dim_case_type"
    primary_key: str                    # "id"
    levels: list[LevelMeta]            # 계층 수준

@dataclass
class LevelMeta:
    name: str                           # "CaseCategory"
    column: str                         # "category"
    level_type: str                     # "String" | "Numeric"

@dataclass
class MeasureMeta:
    name: str                           # "CaseCount"
    column: str                         # "case_id"
    aggregator: str                     # "distinct-count" | "sum" | "avg"
    format_string: str | None           # "#,###"
```

---

### 2.3 프로세스 KPI 큐브 정의 (Synapse 연동)

Synapse 프로세스 마이닝 엔진의 시간축 데이터를 OLAP 큐브로 구성한다.

#### 데이터 소스
ProcessKPICube의 팩트 데이터는 다음 경로로 수집된다:
- Synapse Process Mining Engine (pm4py 기반) → `process_instances`, `conformance_results` 테이블
- ETL (Airflow DAG) → `process_kpi_fact` Materialized View → Mondrian OLAP Cube

#### XML 스키마

```xml
<!-- cubes/process_kpi_cube.xml -->
<Schema name="AxiomVision">
  <Cube name="ProcessKPICube" factTable="mv_process_kpi_fact">

    <!-- Dimensions -->
    <Dimension name="ProcessActivity" foreignKey="activity_id">
      <Hierarchy hasAll="true" primaryKey="id" table="dim_process_activity">
        <Level name="ProcessName" column="process_name" />
        <Level name="ActivityName" column="activity_name" />
        <Level name="Department" column="department" />
      </Hierarchy>
    </Dimension>

    <Dimension name="ProcessTime" foreignKey="process_time_id">
      <Hierarchy hasAll="true" primaryKey="id" table="dim_process_time">
        <Level name="Month" column="month" type="Numeric" />
        <Level name="Week" column="week" type="Numeric" />
        <Level name="Day" column="day" type="Numeric" />
        <Level name="Hour" column="hour" type="Numeric" />
      </Hierarchy>
    </Dimension>

    <Dimension name="ProcessVariant" foreignKey="variant_id">
      <Hierarchy hasAll="true" primaryKey="id" table="dim_process_variant">
        <Level name="VariantID" column="variant_id" />
        <Level name="DeviationFlag" column="deviation_flag" />
        <Level name="VariantLabel" column="variant_label" />
      </Hierarchy>
    </Dimension>

    <!-- Measures -->
    <Measure name="AvgDuration" column="duration_seconds" aggregator="avg" formatString="#,###" />
    <Measure name="CaseCount" column="case_id" aggregator="distinct-count" />
    <Measure name="SLAViolationRate" column="sla_violated" aggregator="avg" formatString="0.00%" />
    <Measure name="BottleneckScore" column="bottleneck_score" aggregator="avg" formatString="0.00" />
    <Measure name="WaitTimeRatio" column="wait_time_ratio" aggregator="avg" formatString="0.00%" />
    <Measure name="ReworkRate" column="rework_count" aggregator="avg" formatString="0.00%" />

  </Cube>
</Schema>
```

#### 차원 상세

| 차원 | 계층 | 컬럼 | 설명 |
|------|------|------|------|
| **ProcessActivity** | ProcessName | `process_name` | 프로세스명 (예: "주문-배송", "승인-결재") |
| | ActivityName | `activity_name` | 활동명 (예: "승인", "검토", "배송") |
| | Department | `department` | 담당 부서 |
| **ProcessTime** | Month | `month` | 월 (1~12) |
| | Week | `week` | 주차 (1~52) |
| | Day | `day` | 일 (1~31) |
| | Hour | `hour` | 시간대 (0~23) |
| **ProcessVariant** | VariantID | `variant_id` | 프로세스 변형 식별자 |
| | DeviationFlag | `deviation_flag` | 표준 경로 이탈 여부 (true/false) |
| | VariantLabel | `variant_label` | 변형 설명 (예: "표준경로", "재작업포함") |

#### 측도 상세

| 측도 | 집계 | 설명 |
|------|------|------|
| `AvgDuration` | avg | 활동별 평균 소요시간 (초) |
| `CaseCount` | distinct-count | 케이스 건수 |
| `SLAViolationRate` | avg | SLA 위반율 (0.0~1.0) |
| `BottleneckScore` | avg | Synapse 병목 점수 (0.0~1.0, 1.0이 최고 병목) |
| `WaitTimeRatio` | avg | 대기시간 / 전체시간 비율 |
| `ReworkRate` | avg | 재작업 비율 |

#### 데이터 소스: Synapse → Materialized View

```
┌─ 프로세스 KPI 데이터 흐름 ─────────────────────────────────────┐
│                                                                 │
│  Axiom Synapse (Process Mining Engine)                          │
│  ├─ 활동별 소요시간, 대기시간, 완료 시각                       │
│  ├─ 변형별 케이스 경로                                          │
│  └─ 병목 점수                                                   │
│          │                                                      │
│          │ REST API (배치 동기화)                                │
│          ▼                                                      │
│  Vision ETL Service                                             │
│  ├─ Synapse 데이터 → mv_process_kpi_fact 적재                  │
│  ├─ dim_process_activity, dim_process_time,                     │
│  │   dim_process_variant 디멘전 갱신                            │
│  └─ 동기화 주기: ETL_SYNC_INTERVAL (기본 1시간)                │
│          │                                                      │
│          ▼                                                      │
│  Materialized Views                                             │
│  ├─ mv_process_kpi_fact (프로세스 KPI 팩트)                    │
│  ├─ dim_process_activity (활동 디멘전)                          │
│  ├─ dim_process_time (프로세스 시간 디멘전)                     │
│  └─ dim_process_variant (변형 디멘전)                           │
└─────────────────────────────────────────────────────────────────┘
```

#### 예시 질의

| 자연어 질의 | 사용 차원 | 사용 측도 |
|------------|----------|----------|
| "부서별 평균 처리 시간" | ProcessActivity.Department | AvgDuration |
| "월별 SLA 위반율 추이" | ProcessTime.Month | SLAViolationRate |
| "병목 점수가 높은 활동 TOP 5" | ProcessActivity.ActivityName | BottleneckScore |
| "표준 경로 vs 이탈 경로 비교" | ProcessVariant.DeviationFlag | AvgDuration, CaseCount |
| "시간대별 처리 건수 분포" | ProcessTime.Hour | CaseCount |

---

## 3. SQL 생성기 (Pivot Engine)

### 3.1 피벗 쿼리 요청

```python
class PivotRequest(BaseModel):
    cube_name: str                      # "BusinessAnalysisCube"
    rows: list[str]                     # ["CaseType.CaseCategory", "Organization.Industry"]
    columns: list[str]                  # ["Time.Year"]
    measures: list[str]                 # ["CaseCount", "AvgPerformanceRate"]
    filters: list[PivotFilter] | None   # WHERE 조건
    limit: int = 1000
    offset: int = 0

class PivotFilter(BaseModel):
    dimension_level: str                # "CaseType.CaseStatus"
    operator: str                       # "=", "in", "between", ">=", "<="
    values: list[str | int | float]     # ["COMPLETED", "IN_PROGRESS"]
```

### 3.2 SQL 생성 로직

```python
def generate_pivot_sql(
    request: PivotRequest,
    cube: CubeMetadata
) -> str:
    """
    Convert PivotRequest into a SELECT query against Materialized Views.

    Example output:
    SELECT
        ct.category AS "CaseType.CaseCategory",
        o.industry AS "Organization.Industry",
        t.filing_year AS "Time.Year",
        COUNT(DISTINCT f.case_id) AS "CaseCount",
        AVG(f.performance_rate) AS "AvgPerformanceRate"
    FROM mv_business_fact f
    JOIN dim_case_type ct ON f.case_type_id = ct.id
    JOIN dim_org o ON f.org_id = o.id
    JOIN dim_time t ON f.time_id = t.id
    WHERE ct.status IN ('COMPLETED', 'IN_PROGRESS')
    GROUP BY ct.category, o.industry, t.filing_year
    ORDER BY t.filing_year DESC
    LIMIT 1000 OFFSET 0;
    """
    select_cols = []
    join_clauses = []
    group_by_cols = []
    where_clauses = []

    # 1. Build SELECT + JOIN for row dimensions
    for row_spec in request.rows:
        dim_name, level_name = row_spec.split(".")
        dim = cube.get_dimension(dim_name)
        level = dim.get_level(level_name)

        alias = dim.table[0]  # Short alias
        col = f"{alias}.{level.column}"
        select_cols.append(f'{col} AS "{row_spec}"')
        group_by_cols.append(col)

        join = f"JOIN {dim.table} {alias} ON f.{dim.foreign_key} = {alias}.{dim.primary_key}"
        if join not in join_clauses:
            join_clauses.append(join)

    # 2. Build SELECT + JOIN for column dimensions (same logic)
    for col_spec in request.columns:
        # ... similar to rows ...
        pass

    # 3. Build measure aggregations
    for measure_name in request.measures:
        measure = cube.get_measure(measure_name)
        agg = AGGREGATOR_MAP[measure.aggregator]  # "distinct-count" → "COUNT(DISTINCT ...)"
        select_cols.append(f'{agg}(f.{measure.column}) AS "{measure_name}"')

    # 4. Build WHERE from filters
    if request.filters:
        for f in request.filters:
            where_clauses.append(build_filter_clause(f, cube))

    # 5. Assemble SQL
    sql = f"""
    SELECT {', '.join(select_cols)}
    FROM {cube.fact_table} f
    {chr(10).join(join_clauses)}
    {"WHERE " + " AND ".join(where_clauses) if where_clauses else ""}
    GROUP BY {', '.join(group_by_cols)}
    ORDER BY {group_by_cols[0]} DESC
    LIMIT {request.limit} OFFSET {request.offset}
    """
    return sql.strip()
```

### 3.3 SQL 검증

```python
import sqlglot

def validate_pivot_sql(sql: str, allowed_tables: set[str]) -> bool:
    """
    Validate generated SQL for safety.

    Checks:
    1. Parseable by SQLGlot
    2. Only SELECT statements (no INSERT/UPDATE/DELETE)
    3. Only references allowed tables
    4. No dangerous keywords (DROP, TRUNCATE, ALTER)
    """
    try:
        parsed = sqlglot.parse_one(sql, dialect="postgres")
    except sqlglot.errors.ParseError:
        raise SQLValidationError("Generated SQL is not parseable")

    # Check statement type
    if not isinstance(parsed, sqlglot.exp.Select):
        raise SQLValidationError("Only SELECT statements are allowed")

    # Check referenced tables
    tables = {t.name for t in parsed.find_all(sqlglot.exp.Table)}
    unauthorized = tables - allowed_tables
    if unauthorized:
        raise SQLValidationError(f"Unauthorized tables: {unauthorized}")

    # Check for dangerous keywords
    sql_upper = sql.upper()
    for keyword in ["DROP", "TRUNCATE", "ALTER", "DELETE", "INSERT", "UPDATE", "GRANT"]:
        if keyword in sql_upper:
            raise SQLValidationError(f"Dangerous keyword detected: {keyword}")

    return True
```

---

## 4. ETL 파이프라인

### 4.1 OLTP → Materialized View 동기화

```
┌─ ETL 동기화 흐름 ──────────────────────────────────────────────┐
│                                                                 │
│  OLTP 테이블 (Axiom Core)                                      │
│  ├─ cases                                                       │
│  ├─ stakeholders                                                │
│  ├─ performance_records                                         │
│  ├─ assets                                                      │
│  └─ cash_flow_entries                                           │
│          │                                                      │
│          │ (1) Full Sync: REFRESH MATERIALIZED VIEW CONCURRENTLY│
│          │ (2) Incremental: event_outbox 이벤트 기반            │
│          ▼                                                      │
│  Materialized Views (OLAP)                                     │
│  ├─ mv_business_fact         (비즈니스 팩트)                   │
│  ├─ mv_cashflow_fact         (현금흐름 팩트)                   │
│  ├─ mv_process_kpi_fact      (프로세스 KPI 팩트) [Synapse]     │
│  ├─ dim_case_type            (사건 유형 디멘전)                │
│  ├─ dim_org                  (조직 디멘전)                     │
│  ├─ dim_time                 (시간 디멘전)                     │
│  ├─ dim_stakeholder_type     (이해관계자 유형 디멘전)          │
│  ├─ dim_process_activity     (프로세스 활동 디멘전) [Synapse]  │
│  ├─ dim_process_time         (프로세스 시간 디멘전) [Synapse]  │
│  └─ dim_process_variant      (프로세스 변형 디멘전) [Synapse]  │
│                                                                 │
│  갱신 전략:                                                     │
│  ├─ Full Sync: 매일 03:00 UTC (Airflow DAG)                   │
│  ├─ Incremental: 새 데이터 입력 이벤트 시 즉시                 │
│  └─ Manual: API 호출 또는 관리자 트리거                        │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Full Sync (Airflow DAG)

```python
# Airflow DAG definition (concept)
dag = DAG(
    'vision_olap_full_sync',
    schedule_interval='0 3 * * *',  # Daily at 03:00 UTC
    default_args={'retries': 3, 'retry_delay': timedelta(minutes=5)}
)

refresh_business_mv = PostgresOperator(
    task_id='refresh_business_mv',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY mv_business_fact;',
    dag=dag
)

refresh_cashflow_mv = PostgresOperator(
    task_id='refresh_cashflow_mv',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY mv_cashflow_fact;',
    dag=dag
)

refresh_process_kpi_mv = PostgresOperator(
    task_id='refresh_process_kpi_mv',
    sql='REFRESH MATERIALIZED VIEW CONCURRENTLY mv_process_kpi_fact;',
    dag=dag
)

sync_synapse_process_data = PythonOperator(
    task_id='sync_synapse_process_data',
    python_callable=sync_process_data_from_synapse,  # Synapse API → staging table
    dag=dag
)

refresh_business_mv >> refresh_cashflow_mv
sync_synapse_process_data >> refresh_process_kpi_mv
```

---

## 5. NL→피벗 워크플로우 (LangGraph)

### 5.1 5노드 구조 (K-AIR 이식)

```
┌─ NL→Pivot LangGraph Workflow ──────────────────────────────────┐
│                                                                 │
│  Node 1: metadata_load                                         │
│  ├─ 사용 가능한 큐브 메타데이터 로드                           │
│  ├─ 차원/측도 목록을 LLM 컨텍스트로 구성                      │
│  └─ 출력: cube_context (str)                                   │
│          │                                                      │
│          ▼                                                      │
│  Node 2: nl_to_pivot_params                                    │
│  ├─ 사용자 자연어 → PivotRequest 파라미터 변환                 │
│  ├─ LLM: GPT-4o (Structured Output, JSON 모드)                │
│  ├─ 프롬프트: cube_context + 사용자 질의                       │
│  └─ 출력: PivotRequest (rows, columns, measures, filters)      │
│          │                                                      │
│          ▼                                                      │
│  Node 3: sql_generation                                        │
│  ├─ PivotRequest → SQL 생성 (generate_pivot_sql)               │
│  └─ 출력: sql_string                                           │
│          │                                                      │
│          ▼                                                      │
│  Node 4: sql_validation                                        │
│  ├─ SQLGlot 구조 검증                                         │
│  ├─ 테이블 화이트리스트 검증                                   │
│  ├─ 위험 키워드 차단                                           │
│  └─ 실패 시: Node 2로 재시도 (최대 2회)                       │
│          │                                                      │
│          ▼                                                      │
│  Node 5: execution_and_response                                │
│  ├─ SQL 실행 (타임아웃 30초, MAX_ROWS 1000)                   │
│  ├─ 결과 → PivotResponse 변환                                 │
│  └─ 생성된 SQL + 피벗 파라미터 함께 반환                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. 캐싱 전략

| 캐싱 계층 | 대상 | TTL | 무효화 조건 |
|----------|------|-----|-----------|
| Materialized View | 팩트/디멘전 데이터 | MV REFRESH 시점 | Full/Incremental Sync |
| Redis 캐시 | 피벗 쿼리 결과 | 1시간 (3600초) | MV REFRESH 시, 수동 무효화 |
| 인메모리 캐시 | 큐브 메타데이터 | 앱 재시작 또는 XML 변경 | 큐브 정의 업로드 시 |

---

## 결정 사항 (Decisions)

- Mondrian XML 형식으로 큐브 정의 (ADR-002)
- Materialized View로 OLAP 성능 확보, 별도 DW 불필요 (ADR-003)
- NL→피벗 변환에 GPT-4o Structured Output 사용
- SQLGlot으로 생성된 SQL 안전성 검증
- 프로세스 KPI 데이터는 Synapse에서 배치 동기화하여 MV에 적재 (실시간 아님)
- ProcessKPICube는 기존 큐브와 동일한 Mondrian XML 형식으로 정의

## 금지 사항 (Forbidden)

- 사용자 입력이 SQL에 직접 삽입되는 것 (SQL injection 방지)
- OLTP 테이블에 직접 OLAP 쿼리 실행 (MV만 사용)
- MV REFRESH 중 동시 쿼리 차단 (CONCURRENTLY 옵션 필수)

## 필수 사항 (Required)

- 모든 생성된 SQL은 SQLGlot 검증 통과 필수
- MV REFRESH는 CONCURRENTLY 옵션 사용 (읽기 차단 방지)
- 쿼리 결과는 MAX_ROWS 제한 적용
- 큐브 메타데이터 변경 시 캐시 무효화
- Synapse 프로세스 데이터 동기화 실패 시 기존 MV 데이터 유지 (덮어쓰기 금지)
- mv_process_kpi_fact에 Synapse 동기화 시각(synced_at) 컬럼 포함

<!-- affects: 02_api/olap-api.md, 03_backend/mondrian-parser.md, 06_data/cube-definitions.md, 00_overview/system-overview.md -->
<!-- requires-update: 06_data/data-warehouse.md, 06_data/cube-definitions.md -->
