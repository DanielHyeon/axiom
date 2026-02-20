# 데이터 흐름

<!-- affects: all modules -->
<!-- requires-update: 01_architecture/architecture-overview.md -->

## 이 문서가 답하는 질문

- 데이터는 어떤 경로로 수집되고 활용되는가?
- 메타데이터는 어떤 생명주기를 가지는가?
- 쿼리 요청은 어떤 경로로 실행되는가?
- ETL 파이프라인은 어떻게 동작하는가?

---

## 1. 전체 데이터 흐름

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          1. 데이터소스 등록                               │
│                                                                          │
│  사용자 ──POST /datasources──▶ Weaver API                               │
│                                    │                                     │
│                          ┌─────────┴──────────┐                          │
│                          ▼                     ▼                          │
│                   MindsDB에                Neo4j에                       │
│                   CREATE DATABASE          :DataSource 노드               │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                          2. 메타데이터 추출                               │
│                                                                          │
│  사용자 ──POST /extract-metadata──▶ Weaver API                          │
│                                         │                                │
│                                   어댑터 선택                             │
│                                   (PG/MySQL/Oracle)                      │
│                                         │                                │
│                                   대상 DB 직접 연결                       │
│                                         │                                │
│                             ┌────────────┼────────────┐                  │
│                             ▼            ▼            ▼                  │
│                        스키마 수집   테이블 수집   컬럼/FK 수집            │
│                             │            │            │                  │
│                             └────────────┼────────────┘                  │
│                                          ▼                               │
│                                    Neo4j에 저장                           │
│                          (DataSource→Schema→Table→Column)                 │
│                                          │                               │
│                                    SSE 진행률 전송                         │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                          3. LLM 메타데이터 보강 (선택)                    │
│                                                                          │
│  시스템 ──자동/수동──▶ 보강 서비스                                        │
│                            │                                             │
│                   Neo4j에서 description NULL인 노드 추출                   │
│                            │                                             │
│                   LLM 호출 (테이블/컬럼 설명 생성)                         │
│                            │                                             │
│                   Neo4j description 필드 업데이트                          │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                          4. 쿼리 실행                                     │
│                                                                          │
│  사용자/AI ──POST /query──▶ Weaver API                                   │
│                                  │                                       │
│                           MindsDB HTTP API                               │
│                                  │                                       │
│                         SQL 파싱 + DB 라우팅                              │
│                                  │                                       │
│                    ┌─────────────┼─────────────┐                         │
│                    ▼             ▼             ▼                          │
│               PostgreSQL     MySQL         Oracle                        │
│               (서브쿼리)    (서브쿼리)     (서브쿼리)                      │
│                    │             │             │                          │
│                    └─────────────┼─────────────┘                         │
│                                  ▼                                       │
│                           결과 통합 반환                                  │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                          5. ETL (배치 수집)                               │
│                                                                          │
│  Airflow DAG ──스케줄──▶ 소스 DB                                         │
│                               │                                          │
│                         Extract (추출)                                   │
│                               │                                          │
│                         Transform (변환)                                 │
│                               │                                          │
│                         Load (적재) ──▶ 타겟 DB                          │
│                               │                                          │
│                         Weaver 메타데이터 갱신                            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 메타데이터 생명주기

```
생성 (Create)
    │
    │  POST /datasources → MindsDB + Neo4j 동시 등록
    │
    ▼
추출 (Extract)
    │
    │  POST /extract-metadata → 어댑터로 스키마 추출 → Neo4j 저장
    │
    ▼
보강 (Enrich) [선택]
    │
    │  LLM으로 테이블/컬럼 설명 자동 생성 → Neo4j description 업데이트
    │
    ▼
활용 (Use)
    │
    │  Oracle: NL2SQL 컨텍스트로 사용
    │  Vision: 분석 대상 테이블 탐색
    │  Canvas: 메타데이터 브라우저 UI
    │
    ▼
갱신 (Refresh)
    │
    │  POST /extract-metadata 재실행 → 기존 메타데이터 삭제 후 재생성
    │  원본 DB 스키마 변경 시 수행
    │
    ▼
삭제 (Delete)
    │
    │  DELETE /datasources/{name} → MindsDB DROP + Neo4j CASCADE DELETE
    │
    ▼
종료
```

### 메타데이터 갱신 트리거

| 트리거 | 방법 | 빈도 |
|--------|------|------|
| 수동 갱신 | Canvas UI에서 "메타데이터 새로고침" 버튼 | 필요 시 |
| 스케줄 갱신 | Airflow DAG에서 주기적 추출 | 일 1회 (권장) |
| 스키마 변경 감지 | (미구현) DDL 이벤트 모니터링 | 실시간 (향후) |

---

## 3. 쿼리 실행 흐름 상세

### 3.1 단일 DB 쿼리

```
POST /api/query
{ "sql": "SELECT * FROM erp_db.public.processes LIMIT 10" }
    │
    ▼
Weaver API (query_service.py)
    │
    │  SQL 유효성 검사 (빈 문자열, DDL 차단)
    │
    ▼
MindsDB Client (client.py)
    │
    │  POST http://mindsdb:47334/api/sql/query
    │  { "query": "SELECT * FROM erp_db.public.processes LIMIT 10" }
    │
    ▼
MindsDB Server
    │
    │  1. SQL 파싱
    │  2. erp_db = PostgreSQL Handler
    │  3. PostgreSQL에 쿼리 전달
    │  4. 결과 수집
    │
    ▼
응답 반환
{ "columns": [...], "data": [...], "row_count": 10 }
```

### 3.2 크로스 DB 조인 쿼리

```
POST /api/query
{ "sql": "SELECT p.process_code, f.total_revenue
          FROM erp_db.public.processes p
          JOIN finance_db.accounting.revenue_summary f
          ON p.org_id = f.org_id" }
    │
    ▼
MindsDB Server
    │
    │  1. SQL 파싱 → 2개 DB 감지
    │  2. 서브쿼리 분배:
    │     - erp_db (PostgreSQL): SELECT * FROM public.processes
    │     - finance_db (MySQL): SELECT * FROM accounting.revenue_summary
    │  3. 각 DB에서 결과 수집
    │  4. 메모리 내 JOIN 실행
    │  5. 결과 반환
    │
    ▼
응답 반환
```

---

## 4. ETL 파이프라인

### 4.1 Airflow DAG 구조

```python
# Example: 일간 재무 데이터 동기화 DAG
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "axiom-weaver",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "daily_revenue_sync",
    default_args=default_args,
    schedule_interval="0 2 * * *",  # Every day at 2 AM
    start_date=datetime(2026, 1, 1),
    catchup=False,
) as dag:

    extract = PythonOperator(
        task_id="extract_from_finance_db",
        python_callable=extract_revenue_data,
        op_kwargs={"source": "finance_db", "date": "{{ ds }}"},
    )

    transform = PythonOperator(
        task_id="transform_revenue_data",
        python_callable=transform_revenue_data,
    )

    load = PythonOperator(
        task_id="load_to_erp_db",
        python_callable=load_to_target,
        op_kwargs={"target": "erp_db", "table": "external_revenue_summary"},
    )

    refresh_metadata = PythonOperator(
        task_id="refresh_weaver_metadata",
        python_callable=trigger_metadata_extraction,
        op_kwargs={"datasource": "erp_db"},
    )

    extract >> transform >> load >> refresh_metadata
```

### 4.2 ETL 후 메타데이터 자동 갱신

ETL로 새 테이블이 생기거나 스키마가 변경되면, 마지막 태스크에서 Weaver의 메타데이터 추출을 트리거한다.

```python
async def trigger_metadata_extraction(datasource: str):
    """ETL 완료 후 Weaver 메타데이터 갱신"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://weaver:8000/api/datasources/{datasource}/extract-metadata",
            json={"include_row_counts": True},
        )
        if response.status_code != 200:
            raise Exception(f"Metadata extraction failed: {response.text}")
```

---

## 5. 관련 문서

| 문서 | 설명 |
|------|------|
| `01_architecture/data-fabric.md` | 데이터 패브릭 설계 |
| `02_api/query-api.md` | 쿼리 API |
| `02_api/metadata-api.md` | 메타데이터 추출 API |
| `05_llm/metadata-enrichment.md` | LLM 보강 |
| `08_operations/deployment.md` | Airflow 배포 |
