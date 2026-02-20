# Axiom Vision - 아키텍처 개요

> **최종 수정일**: 2026-02-19
> **상태**: Draft
> **근거**: ADR-001, ADR-002, ADR-003, ADR-005, 00_overview/system-overview.md

---

## 이 문서가 답하는 질문

- Vision 모듈의 논리적/물리적 아키텍처는 어떻게 구성되는가?
- 3개 엔진(What-if, OLAP, See-Why) 간의 관계와 경계는?
- 왜 이러한 경계로 나누었는가?
- 동기/비동기 처리 경계는 어디인가?
- 장애 격리 지점은 어디인가?

---

## 1. 논리적 아키텍처

### 1.1 레이어 구조

```
┌─────────────────────────────────────────────────────────────────┐
│  API 레이어 (app/api/)                                           │
│  ├─ what_if.py     : What-if 시나리오 CRUD + 계산 트리거        │
│  ├─ olap.py        : OLAP 큐브 관리 + 피벗 쿼리                │
│  ├─ analytics.py   : 통계 대시보드 집계                         │
│  └─ root_cause.py  : 근본원인 분석 요청 [Phase 4]              │
├─────────────────────────────────────────────────────────────────┤
│  엔진 레이어 (app/engines/)                                      │
│  ├─ scenario_solver.py  : scipy 기반 제약 최적화                │
│  ├─ mondrian_parser.py  : Mondrian XML → 큐브 메타데이터 추출   │
│  ├─ pivot_engine.py     : 큐브 메타 → SQL 생성 + 실행          │
│  └─ causal_engine.py    : DoWhy 인과 추론 [Phase 4]            │
├─────────────────────────────────────────────────────────────────┤
│  코어 레이어 (app/core/)                                         │
│  ├─ config.py     : 환경 설정 (Pydantic Settings)               │
│  ├─ database.py   : SQLAlchemy async session                    │
│  └─ dependencies.py : FastAPI 의존성 주입                       │
├─────────────────────────────────────────────────────────────────┤
│  데이터 레이어 (PostgreSQL)                                      │
│  ├─ what_if_scenarios, scenario_parameter_overrides              │
│  ├─ scenario_results                                             │
│  ├─ Materialized Views (mv_business_fact, mv_cashflow_fact)     │
│  └─ causal_graphs, case_causal_analysis [Phase 4]               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 왜 이 레이어 경계인가?

| 경계 | 이유 |
|------|------|
| API ↔ 엔진 분리 | API는 HTTP 프로토콜 관심사만 처리. 엔진은 순수 계산 로직으로 단위 테스트 가능 |
| 엔진 간 독립 | What-if/OLAP/See-Why는 각각 독립적으로 배포/스케일 가능해야 함. scipy와 DoWhy는 무거운 계산이므로 향후 별도 워커로 분리 가능 |
| 코어 공유 | 설정, DB 세션, 인증은 모든 엔진이 공유하되, 엔진 간 직접 의존은 금지 |

---

## 2. 물리적 아키텍처

### 2.1 배포 단위

```
┌─ Docker Container: axiom-vision ──────────────────────────────┐
│                                                                │
│  FastAPI Application (uvicorn, port 8400)                      │
│  ├─ /api/v3/cases/{id}/what-if/*     → What-if API            │
│  ├─ /api/v3/pivot/*                  → OLAP API               │
│  ├─ /api/v3/analytics/*             → Analytics API           │
│  └─ /api/v3/cases/{id}/root-cause/* → See-Why API [Phase 4]  │
│                                                                │
│  Background Workers (asyncio)                                  │
│  ├─ Scenario computation (async task)                          │
│  ├─ ETL sync trigger (scheduled)                              │
│  └─ Causal analysis (async task) [Phase 4]                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
         │                     │                    │
         ▼                     ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ PostgreSQL   │   │ Redis        │   │ Axiom Core   │
│ (공유 DB)    │   │ (캐시, 선택) │   │ (JWT 검증)   │
└──────────────┘   └──────────────┘   └──────────────┘
```

### 2.2 MVP 배포 (Docker Compose)

```yaml
# docker-compose.yml (Vision 부분)
axiom-vision:
  build: ./services/vision
  ports:
    - "8400:8400"
  environment:
    - DATABASE_URL=postgresql+asyncpg://axiom:password@postgres:5432/axiom
    - REDIS_URL=redis://redis:6379/2
    - OPENAI_API_KEY=${OPENAI_API_KEY}
    - OPENAI_MODEL=gpt-4o
    - QUERY_TIMEOUT=30
    - MAX_ROWS=1000
  depends_on:
    - postgres
    - redis
```

### 2.3 프로덕션 배포 (EKS)

Phase 3 이후 Kubernetes 배포 시:
- What-if 솔버는 CPU-intensive이므로 별도 HPA (CPU 기반 오토스케일링)
- OLAP 쿼리는 읽기 중심이므로 PostgreSQL Read Replica 활용
- See-Why 엔진은 ML 모델 학습/추론이므로 GPU 노드 고려 (Phase 4)

---

## 3. 엔진 간 관계

### 3.1 의존성 그래프

```
         What-if 엔진
             │
             │ 사용: 시나리오 결과를 OLAP 큐브 데이터로 검증
             ▼
         OLAP 엔진 ←──── NL→피벗 (Oracle 모듈 위임)
             │
             │ 제공: 과거 데이터를 인과 분석 학습 데이터로 제공
             ▼
         See-Why 엔진 [Phase 4]
```

### 3.2 데이터 흐름

```
┌─ 사용자 요청 ────────────────────────────────────────────────┐
│                                                               │
│  1. What-if: "10년 실행 시나리오 생성"                        │
│     → POST /what-if/create                                   │
│     → 시나리오 저장 (DB)                                     │
│     → POST /what-if/{id}/compute                             │
│     → scipy solver 실행 (async, 최대 60초)                   │
│     → 결과 저장 (scenario_results)                           │
│     → GET /what-if/compare (다중 시나리오 비교)              │
│                                                               │
│  2. OLAP: "2024년 제조업 성과율"                              │
│     → POST /pivot/query (차원/측도/필터 지정)                │
│     → Mondrian 메타 → SQL 생성                               │
│     → Materialized View 쿼리 (최대 30초)                     │
│     → 결과 그리드 반환                                        │
│                                                               │
│  3. NL→피벗: "작년 구조조정 사건 통계 보여줘"                │
│     → POST /nl-query                                         │
│     → LLM → 피벗 파라미터 추출                               │
│     → 피벗 쿼리 실행                                         │
│     → 결과 + 생성된 SQL 반환                                 │
│                                                               │
│  4. See-Why: "이 회사의 실패 원인 분석" [Phase 4]            │
│     → POST /root-cause-analysis (async, 1-2분)               │
│     → 인과 그래프 로드 → 역추적                              │
│     → SHAP 계산 → 근본원인 3-5개 도출                       │
│     → LLM 설명 서술문 생성                                   │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. 동기/비동기 경계

| 작업 | 처리 방식 | 이유 | 타임아웃 |
|------|----------|------|---------|
| 시나리오 CRUD | 동기 | 단순 DB 연산, 즉시 응답 필요 | 5초 |
| 시나리오 계산 (compute) | **비동기** | scipy solver가 수십 초 소요 | 60초 |
| 피벗 쿼리 실행 | 동기 | MV 쿼리로 대부분 5초 이내 | 30초 |
| NL→피벗 변환 | 동기 | LLM 호출 포함, 10초 이내 목표 | 30초 |
| ETL 동기화 | **비동기** | 대량 데이터 갱신, 수분 소요 | 300초 |
| 근본원인 분석 | **비동기** | ML 추론 + LLM 호출, 1-2분 소요 | 120초 |
| MV 갱신 (REFRESH) | **비동기** | 팩트 테이블 전체 재집계 | 300초 |

### 4.1 비동기 작업 패턴

```python
# Async task pattern (What-if compute example)
@router.post("/cases/{case_id}/what-if/{scenario_id}/compute")
async def compute_scenario(case_id: UUID, scenario_id: UUID):
    # 1. Validate scenario exists
    scenario = await get_scenario(case_id, scenario_id)

    # 2. Mark as COMPUTING
    await update_status(scenario_id, ScenarioStatus.COMPUTING)

    # 3. Dispatch to background
    background_tasks.add_task(
        run_scenario_solver,
        scenario_id=scenario_id,
        constraints=scenario.constraints,
        timeout=settings.SCENARIO_SOLVER_TIMEOUT
    )

    # 4. Return immediately with task reference
    return {"status": "computing", "scenario_id": scenario_id}
```

---

## 5. 장애 격리 지점

### 5.1 장애 시나리오와 격리 전략

| 장애 시나리오 | 영향 범위 | 격리 전략 |
|-------------|----------|----------|
| scipy solver 무한 루프 | What-if 계산만 영향 | 60초 타임아웃 + asyncio.wait_for |
| LLM API 장애 | NL→피벗만 영향 | 수동 피벗 쿼리는 정상 동작 |
| PostgreSQL 과부하 | 전체 Vision | Connection pool 제한 (max 20), 쿼리 타임아웃 30초 |
| Redis 장애 | OLAP 캐시만 영향 | 캐시 미스 시 DB 직접 쿼리 (graceful degradation) |
| DoWhy ML 추론 오류 | See-Why만 영향 | 분석 실패 시 "분석 불가" 반환, 다른 엔진 정상 |
| Materialized View 갱신 실패 | OLAP 데이터 최신성 | 이전 MV 유지, 갱신 재시도 (3회) |

### 5.2 Circuit Breaker 적용 대상

```
LLM API 호출 (NL→피벗, 인과 설명):
  - 5회 연속 실패 시 circuit open (30초)
  - Half-open에서 1회 성공 시 close

Oracle 모듈 호출 (NL→SQL 위임):
  - 3회 연속 실패 시 circuit open (15초)
  - Fallback: "자연어 질의를 사용할 수 없습니다" 응답
```

### 장애 격리 참조

> **전체 복원력 설계**: Circuit Breaker 설정 (Core→Vision: 5회/60s, 30s Open), Fallback 전략 (Vision 장애 시 Core CRUD 정상), K8s Probe (Readiness: PostgreSQL 검사), Graceful Degradation은 Core의 [resilience-patterns.md](../../../core/docs/01_architecture/resilience-patterns.md)를 참조한다.

---

## 6. 디렉토리 구조 (최종)

```
services/vision/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory
│   ├── api/
│   │   ├── __init__.py
│   │   ├── what_if.py             # What-if 시나리오 API
│   │   ├── olap.py                # OLAP 피벗 API
│   │   ├── analytics.py           # 통계 대시보드 API
│   │   └── root_cause.py          # 근본원인 분석 API [Phase 4]
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── scenario_solver.py     # scipy 기반 시나리오 솔버
│   │   ├── mondrian_parser.py     # Mondrian XML 파서
│   │   ├── pivot_engine.py        # 피벗 쿼리 엔진
│   │   ├── etl_service.py         # ETL 동기화 서비스
│   │   ├── nl_pivot_workflow.py   # LangGraph NL→피벗 워크플로우
│   │   └── causal_engine.py       # DoWhy 인과 추론 [Phase 4]
│   ├── models/
│   │   ├── __init__.py
│   │   ├── scenario.py            # What-if SQLAlchemy 모델
│   │   ├── cube.py                # 큐브 메타데이터 모델
│   │   └── causal.py              # 인과 분석 모델 [Phase 4]
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── what_if.py             # What-if Pydantic 스키마
│   │   ├── olap.py                # OLAP Pydantic 스키마
│   │   └── root_cause.py          # See-Why Pydantic 스키마
│   └── core/
│       ├── __init__.py
│       ├── config.py              # Pydantic Settings
│       ├── database.py            # Async SQLAlchemy engine
│       └── dependencies.py        # FastAPI Depends
├── cubes/
│   ├── business_analysis_cube.xml # 비즈니스 분석 큐브 정의
│   └── cashflow_cube.xml          # 현금흐름 큐브 정의
├── tests/
│   ├── test_scenario_solver.py
│   ├── test_mondrian_parser.py
│   ├── test_pivot_engine.py
│   └── test_api/
├── docs/                          # 이 문서들
├── pyproject.toml
└── Dockerfile
```

---

## 결정 사항 (Decisions)

- Vision은 단일 FastAPI 서비스로 배포 (ADR-005)
- 무거운 계산(solver, ML)은 비동기 처리 필수
- OLAP은 별도 DW 없이 Materialized View 사용 (ADR-003)
- 엔진 간 직접 import 금지, API 레이어에서만 조합

## 사실 (Facts)

- K-AIR data-platform-olap의 Mondrian XML 파서 + SQL 생성기를 이식
- What-if 엔진과 See-Why 엔진은 완전 신규 개발
- PostgreSQL 공유 DB 사용 (Axiom Core와 동일 인스턴스)

## 금지 사항 (Forbidden)

- API 레이어에서 직접 SQL 실행 (반드시 엔진 레이어 경유)
- 엔진 간 직접 import (scenario_solver가 pivot_engine을 import 금지)
- 동기 요청에서 60초 이상 블로킹
- Vision에서 Axiom Core DB 테이블 직접 수정 (READ만 허용, 변경은 Core API 경유)

## 필수 사항 (Required)

- 모든 API 요청에 JWT 토큰 검증
- 모든 쿼리에 case_id + org_id 기반 데이터 격리
- 비동기 작업은 상태 추적 가능해야 함 (PENDING → COMPUTING → COMPLETED/FAILED)
- 모든 SQL 쿼리에 타임아웃 설정

<!-- affects: 02_api, 03_backend, 08_operations -->
<!-- requires-update: 00_overview/system-overview.md -->
