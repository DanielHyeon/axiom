# Insight View 구현 설계서

> **버전**: v3.1
> **작성일**: 2026-02-26
> **최종 수정**: 2026-02-26 (P0~P2 갭 보강: 연동 흐름, DDL, 에러 표준, 모니터링, Fallback 전략)
> **스키마 버전**: `insight/v3`
> **목표**: KPI 중심 영향 분석(Impact Graph) + 스키마 기준 데이터 그래프(Instance Graph) + NL2SQL 결과 그래프를 이원화하여 제공

---

## 목차

1. [개요](#1-개요)
   - 1.4 [피드백 반영 추적표 (P0~P2 → 섹션 매핑)](#14-피드백-반영-추적표)
2. [전체 아키텍처](#2-전체-아키텍처)
   - 2.4 [서비스 간 연동 흐름 (Oracle → Weaver 자동 인제스트)](#24-서비스-간-연동-흐름)
3. [데이터 모델 (B)](#3-데이터-모델)
   - 3.8 [저장소 스키마 상세 (DDL)](#38-저장소-스키마-상세-ddl)
   - 3.9 [Zustand 상태 관리 인터페이스](#39-zustand-상태-관리-인터페이스)
4. [API Contracts (A)](#4-api-contracts)
   - 4.11 [API 에러 응답 표준](#411-api-에러-응답-표준)
5. [SQL 파서 & 처리 전략 (C)](#5-sql-파서--처리-전략)
6. [Driver 중요도 점수 설계](#6-driver-중요도-점수-설계)
7. [보안 & 격리 (D)](#7-보안--격리)
   - 7.6 [운영 모니터링 메트릭](#76-운영-모니터링-메트릭)
8. [프론트엔드 화면 설계 & UX 규칙 (E)](#8-프론트엔드-화면-설계--ux-규칙)
   - 8.7 [에러 상태별 프론트엔드 Fallback 전략](#87-에러-상태별-프론트엔드-fallback-전략)
9. [Cytoscape 스타일 & 레이아웃 가이드](#9-cytoscape-스타일--레이아웃-가이드)
10. [라우트/메뉴 변경 상세](#10-라우트메뉴-변경-상세)
11. [성능 설계](#11-성능-설계)
12. [단계별 구현 계획](#12-단계별-구현-계획)
13. [위험 요소 및 대응](#13-위험-요소-및-대응)
14. [전체 테스트 체크리스트 (Final Gate)](#14-전체-테스트-체크리스트-final-gate)
15. [부록](#15-부록)

---

## 1. 개요

### 1.1 배경

현재 Axiom 시스템은 3개의 데이터 뷰를 제공한다.

| 뷰 | 현재 역할 | 한계 |
|---|---|---|
| 데이터 페이지 (`/data/datasources`) | 데이터소스 관리, 테이블 트리 | 관리 화면이라 분석 부적합 |
| 온톨로지 뷰 (`/data/ontology`) | 개념 그래프 (KPI/Process/Resource) | 실데이터 연결 없음 |
| NL2SQL (`/analysis/nl2sql`) | 자연어 → SQL → 테이블/차트 | 구조적 관계 시각화 없음 |

**문제**: 사용자는 "구조는 이해했는데 실제 데이터가 어떻게 흘러가는지 체감하기 어렵고", 반대로 "데이터는 보이는데 왜 그런지(관계/제약)를 놓치기 쉽다."

### 1.2 목표

1. **Insight 신규 페이지** (`/analysis/insight`) — KPI 중심 영향 그래프 (Impact Graph)
2. **NL2SQL Graph 탭** — 쿼리 결과를 서브그래프로 시각화
3. **온톨로지 데이터 프리뷰** — 개념 노드 클릭 시 실데이터 샘플/연결 표시

### 1.3 이원화 전략

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  스키마 기준 데이터 그래프    │     │  핵심 흐름 인사이트 그래프    │
│  (Instance Graph)           │     │  (Impact / Flow Graph)      │
│                             │     │                             │
│  목적: 탐색                  │     │  목적: 통찰                  │
│  "어디서 왔고 어디로 연결?"   │     │  "무엇이 무엇에 영향?"       │
│                             │     │                             │
│  노드: (테이블, PK) 레코드    │     │  노드: KPI/Driver/Transform │
│  엣지: FK/조인 관계           │     │  엣지: 영향 경로             │
│                             │     │                             │
│  위치: NL2SQL Graph 탭       │     │  위치: Insight 전용 페이지    │
│        온톨로지 프리뷰         │     │        사이드바 "분석" 섹션   │
└─────────────────────────────┘     └─────────────────────────────┘
```

### 1.4 피드백 반영 추적표 (P0~P2 → 섹션 매핑)

> 리뷰 피드백 항목이 설계서 어디에 반영되었는지 추적하는 인덱스.

| 피드백 ID | 우선순위 | 항목 | 반영 섹션 | 상태 |
|---|---|---|---|---|
| **P0-1** | 필수 | Query Log Ingest API 스펙 | §4.1, §4.1.1, §3.2 (LogItem), §7.1 (org_id 주입) | ✅ 반영 |
| **P0-2** | 필수 | Graph 응답 스키마 메타 확장 | §3.1 (GraphMeta: schema_version, cache, limits, explain) | ✅ 반영 |
| **P0-3** | 필수 | SQL 파서 2단계 전략 | §5.1~5.6 (primary/fallback, confidence, mode) | ✅ 반영 |
| **P0-4** | 필수 | Driver Scoring 후보 필터링 + 표본수 + DIMENSION 분리 | §6.1~6.6 (필터링, 카디널리티, 표본수, breakdown) | ✅ 반영 |
| **P0-5** | 필수 | Final Gate 운영급 보안/관측 | §7.3 (입력 방어), §7.4 (PII), §7.5 (trace_id), §14 FG-16~21 | ✅ 반영 |
| **P1-1** | 강추 | Impact Graph 202 Job 패턴 | §4.3 (200/202), §4.9 (Job), §4.9.1 (SSE), §11.3 (비동기 처리) | ✅ 반영 |
| **P1-2** | 강추 | Cytoscape 레이아웃 전략 (그래프별) | §9.1 (breadthfirst/cose-bilkent/dagre), §9.1 서버 프리레이아웃 | ✅ 반영 |
| **P1-3** | 강추 | Driver 상세 조회 (Evidence/Breakdown) | §4.5 (API), §8.2 (UX 규칙), §14 FG-27 | ✅ 반영 |
| **P2-1** | 제품급 | 온톨로지 프리뷰 매핑 신뢰도/커버리지 | §4.10 (API), §8.5 (UI), §14 FG-10 | ✅ 반영 |
| **P2-2** | 제품급 | UX "질문→근거→행동" 루프 고정 | §8.2 (NodeDetailPanel 필수 섹션), §8.3 (동작 흐름), §14 FG-27~28 | ✅ 반영 |
| **P2-3** | 제품급 | fingerprint 딥링크 + KPI 병합 | §4.2 (병합 규칙), §8.6 (딥링크 fallback 체인), §14 FG-26 | ✅ 반영 |

**설계서 목차 ↔ 피드백 카테고리 매핑**:

| 피드백 카테고리 | 설계서 섹션 |
|---|---|
| **A. API Contracts** | §4 (전체), §4.11 (에러 표준) |
| **B. Data Model** | §3 (전체), §3.8 (DDL), §3.9 (Zustand) |
| **C. Processing & Failure Strategy** | §5 (SQL 파서), §5.7 (캐시 키), §11.3 (비동기) |
| **D. Security & Isolation** | §7 (전체), §7.6 (모니터링), §14 FG-16~21 |
| **E. Frontend UX Rules** | §8 (전체), §8.7 (Fallback 전략), §9 (Cytoscape) |

---

## 2. 전체 아키텍처

### 2.1 시스템 구조

```
┌─────────────────────────────────────────────────────────┐
│                    Canvas Frontend                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐ │
│  │ Insight   │  │ NL2SQL   │  │ Ontology              │ │
│  │ Page      │  │ Graph Tab│  │ Data Preview          │ │
│  └────┬─────┘  └────┬─────┘  └───────────┬───────────┘ │
│       │              │                     │             │
│  ┌────┴──────────────┴─────────────────────┴──────────┐ │
│  │             Graph Engine Layer (공유)                │ │
│  │                                                     │ │
│  │  A. ImpactGraphBuilder  (쿼리로그 기반)              │ │
│  │  B. InstanceGraphBuilder (FK 기반)                   │ │
│  │  C. QuerySubgraphAdapter (NL2SQL 결과 기반)          │ │
│  └─────────────────────┬───────────────────────────────┘ │
│                        │                                 │
│  ┌─────────────────────┴───────────────────────────────┐ │
│  │          Cytoscape.js Graph Renderer (공유)          │ │
│  └─────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Weaver API    │  │ Oracle API    │  │ Synapse API   │
│ (메타데이터,   │  │ (NL2SQL)     │  │ (Neo4j 그래프) │
│  쿼리로그)    │  │              │  │              │
└───────────────┘  └───────────────┘  └───────────────┘
```

### 2.2 프론트엔드 폴더 구조

```
apps/canvas/src/
├── features/insight/
│   ├── api/
│   │   └── insightApi.ts              # Weaver insight endpoints 호출
│   ├── hooks/
│   │   ├── useImpactGraph.ts          # Impact Graph 데이터 페치/변환 (202 폴링 포함)
│   │   ├── useInstanceGraph.ts        # Instance Graph 데이터 페치/변환
│   │   ├── useQuerySubgraph.ts        # NL2SQL 결과 → 서브그래프 변환
│   │   ├── useDriverDetail.ts         # Driver 상세 + Evidence 조회
│   │   └── useKpiTimeseries.ts        # KPI 시계열 (Driver 분할) (P2)
│   ├── store/
│   │   └── useInsightStore.ts         # Zustand 상태 관리
│   ├── types/
│   │   └── insight.ts                 # 타입 정의
│   ├── utils/
│   │   ├── scoreCalculator.ts         # Driver 중요도 점수 계산/표시
│   │   ├── graphTransformer.ts        # API 응답 → Cytoscape 엘리먼트 변환
│   │   └── fingerprintUtils.ts        # KPI fingerprint 생성/비교 유틸
│   └── components/
│       ├── ImpactGraphViewer.tsx       # KPI 영향 그래프 (Cytoscape)
│       ├── InstanceGraphViewer.tsx     # 레코드 네트워크 그래프 (Cytoscape)
│       ├── QuerySubgraphViewer.tsx     # NL2SQL 결과 서브그래프
│       ├── KpiSelector.tsx            # KPI 선택 UI
│       ├── DriverRankingPanel.tsx      # Top Driver 순위 패널
│       ├── NodeDetailPanel.tsx         # 노드 상세 사이드 패널 (Evidence 고정)
│       ├── PathComparisonPanel.tsx     # Top 3 영향 경로 비교 (P2)
│       ├── KpiMiniChart.tsx           # Driver별 KPI 미니 시계열 (P2)
│       └── TimeRangeSelector.tsx       # 기간 필터
│
├── pages/insight/
│   ├── InsightPage.tsx                # 메인 Insight 페이지 (fingerprint 딥링크)
│   └── components/
│       ├── InsightHeader.tsx          # 헤더 (뷰 토글, 필터)
│       └── InsightSidebar.tsx         # 좌측 KPI/Driver 리스트
│
└── pages/nl2sql/components/
    └── QueryGraphPanel.tsx            # NL2SQL 결과 Graph 탭 (신규)
```

### 2.3 백엔드 API 구조 (Weaver 서비스)

```
services/weaver/app/
├── api/
│   └── insight.py                     # Insight 전용 라우터 (신규)
│       ├── POST /api/insight/logs                 # 쿼리 로그 인제스트
│       ├── POST /api/insight/logs:ingest           # 배치 인제스트 (멱등성 강화)
│       ├── GET  /api/insight/kpis                  # KPI 목록
│       ├── GET  /api/insight/impact                # KPI 영향 그래프 (200/202)
│       ├── GET  /api/insight/drivers               # Top Driver 랭킹
│       ├── GET  /api/insight/drivers/{driver_id}   # Driver 상세 + Evidence
│       ├── GET  /api/insight/kpi/timeseries        # KPI 시계열 (P2)
│       ├── POST /api/insight/instance-graph        # FK 기반 인스턴스 그래프
│       ├── POST /api/insight/query-subgraph        # SQL → 서브그래프 변환
│       ├── GET  /api/insight/jobs/{job_id}         # 비동기 작업 상태
│       └── GET  /api/insight/jobs/{job_id}/events  # SSE 이벤트 스트림 (P1)
│
│   └── ontology_preview.py            # 온톨로지 프리뷰 (신규)
│       └── GET  /api/ontology/preview/coverage     # 매핑 신뢰도/커버리지 (P2)
│
├── services/
│   ├── query_log_analyzer.py          # SQL 로그 파싱 및 분석
│   ├── query_log_store.py             # 쿼리 로그 저장/조회 (멱등성)
│   ├── impact_graph_builder.py        # 영향 그래프 생성 (202 async)
│   ├── instance_graph_builder.py      # FK 기반 인스턴스 그래프
│   └── driver_scorer.py              # Driver 점수 계산 엔진
│
└── core/
    ├── sql_parser.py                  # SQL 파싱 (2-stage: AST + fallback)
    └── pii_masker.py                  # 리터럴/PII 마스킹 유틸
```

### 2.4 서비스 간 연동 흐름 (Oracle → Weaver 자동 인제스트)

NL2SQL 실행 결과를 Insight 분석 파이프라인에 자동 공급하는 핵심 연동.

```
┌─────────────────┐     ① NL2SQL 실행     ┌─────────────────┐
│  Canvas Frontend │ ──────────────────► │  Oracle (NL2SQL) │
│                  │ ◄────────────────── │                  │
│                  │   ② SQL + 결과 반환   │                  │
└─────────────────┘                      └────────┬────────┘
                                                  │
                                         ③ 비동기 POST
                                         /api/insight/logs
                                         (fire-and-forget)
                                                  │
                                                  ▼
                                         ┌─────────────────┐
                                         │  Weaver (Insight)│
                                         │                  │
                                         │  로그 저장       │
                                         │  → 파싱/분석     │
                                         │  → 점수 재계산   │
                                         └─────────────────┘
```

**Oracle 측 연동 코드** (`services/oracle/app/api/nl2sql.py`):

```python
import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Weaver 내부 통신용 (서비스 간 통신, 동일 네트워크)
WEAVER_INSIGHT_URL = f"{settings.WEAVER_BASE_URL}/api/insight/logs"

async def forward_to_insight(
    request_id: str,
    trace_id: str,
    sql: str,
    datasource: str,
    dialect: str,
    status: str,
    duration_ms: int,
    row_count: int | None,
    nl_query: str | None,
    result_schema: list[dict] | None,
    access_token: str,          # 원래 사용자 토큰 전달 (org_id 결정용)
):
    """NL2SQL 실행 결과를 Weaver Insight에 비동기 전송 (fire-and-forget)"""
    entry = {
        "request_id": request_id,
        "trace_id": trace_id,
        "datasource": datasource,
        "dialect": dialect,
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "duration_ms": duration_ms,
        "row_count": row_count,
        "nl_query": nl_query,
        "sql": sql,
        "result_schema": result_schema,
        "intent": "ad_hoc",
        "tags": ["nl2sql", "auto"],
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                WEAVER_INSIGHT_URL,
                json={"entries": [entry]},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if resp.status_code != 200:
                logger.warning(f"Insight ingest failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        # fire-and-forget: NL2SQL 응답을 지연시키지 않음
        logger.warning(f"Insight ingest error (non-blocking): {e}")
```

**연동 규칙**:

| 규칙 | 설명 |
|---|---|
| 비차단 | Insight 전송 실패가 NL2SQL 응답에 영향 없음 (fire-and-forget) |
| 토큰 전달 | 원래 사용자의 access_token을 그대로 전달 → Weaver가 org_id 결정 |
| 재시도 없음 | 단건 실패는 무시. 배치 재전송은 별도 운영 파이프라인 (`logs:ingest`) 사용 |
| 타임아웃 | 내부 통신 5초 제한. 초과 시 로그만 남기고 진행 |
| 상태 매핑 | `executed` (성공), `failed` (SQL 에러), `generated` (실행 없이 SQL만 생성) |

---

## 3. 데이터 모델

### 3.1 공통 그래프 노드/엣지

```typescript
// features/insight/types/insight.ts

/** 그래프 노드 공통 타입 */
export interface GraphNode {
  id: string;
  label: string;
  type: 'KPI' | 'DRIVER' | 'DIMENSION' | 'TRANSFORM' | 'TABLE' | 'COLUMN' | 'RECORD' | 'PREDICATE';
  /** 노드 출처 — Explainability 핵심 */
  source: 'ontology' | 'query_log' | 'fk' | 'sql_parse' | 'manual' | 'rule' | 'merged';
  /** 노드 신뢰도 (0~1). sql_parse fallback 시 낮음 */
  confidence: number;
  /** UI 배지/필터링용 라벨 */
  labels?: string[];
  layer?: string;           // kpi | measure | process | resource
  score?: number;           // 중요도 점수 (0~100)
  properties: Record<string, unknown>;
  /** 서버 프리레이아웃 좌표 (P1, 선택) */
  position?: { x: number; y: number };
}

/** 그래프 엣지 공통 타입 */
export interface GraphEdge {
  source: string;
  target: string;
  type: 'FK' | 'JOIN' | 'WHERE_FILTER' | 'HAVING_FILTER' | 'AGGREGATE' | 'DERIVE' | 'IMPACT' | 'GROUP_BY';
  label?: string;
  weight?: number;          // 영향 강도 (0~1)
  /** 엣지 출처 */
  source_type?: 'ontology' | 'query_log' | 'fk' | 'sql_parse' | 'manual' | 'rule';
  /** 엣지 신뢰도 (0~1) */
  confidence?: number;
}

/** 그래프 데이터 컨테이너 */
export interface GraphData {
  meta: GraphMeta;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/** 강화된 메타데이터 (모든 API 공통) */
export interface GraphMeta {
  // 스키마/버전
  schema_version: string;          // "insight/v3"
  analysis_version: string;        // "2026-02-26.1"
  generated_at: string;            // ISO 8601

  // 범위
  time_range: { from: string; to: string };
  datasource: string;

  // 캐시
  cache_hit: boolean;
  cache_ttl_remaining_s?: number;

  // 제한값 투명 노출
  limits: {
    max_nodes: number;
    max_edges: number;
    depth: number;
    top_drivers?: number;
  };

  // 잘림 여부
  truncated: boolean;

  // 레이아웃 (서버 프리레이아웃 시)
  layout?: { name: string; computed_by: 'server' | 'client' };

  // trace 연계 (P0-5)
  trace_id?: string;

  // Explain (관측 가능성)
  explain?: {
    scoring_formula?: string;
    total_queries_analyzed: number;
    time_range_used: string;
    fallback_used?: boolean;
    mode?: 'primary' | 'fallback';
  };
}
```

### 3.2 쿼리 로그 항목 (LogItem)

```typescript
/** POST /api/insight/logs 요청 바디의 개별 항목 */
export interface QueryLogItem {
  /** Oracle 측 요청 ID (트래킹용) */
  request_id: string;
  /** OpenTelemetry traceparent 호환 또는 UUID */
  trace_id: string;
  /** 데이터소스 이름 */
  datasource: string;
  /** SQL 방언 */
  dialect: 'postgres' | 'snowflake' | 'bigquery' | 'mysql' | 'oracle_db' | 'mssql';
  /** 실행 시각 (ISO 8601) */
  executed_at: string;
  /** 상태 */
  status: 'generated' | 'executed' | 'failed';
  /** 실행 소요 시간 (ms) */
  duration_ms: number;
  /** 반환 행 수 (실행 성공 시) */
  row_count?: number;
  /** 에러 코드 (실패 시) */
  error_code?: string;
  /** 실행 사용자 */
  user?: { user_id?: string; role?: string };
  /** 원문 자연어 질의 (NL2SQL인 경우) */
  nl_query?: string;
  /** 질의 의도 분류 */
  intent?: 'explore' | 'root_cause' | 'summary' | 'monitoring' | 'ad_hoc';
  /** 원본 SQL */
  sql: string;
  /** 정규화 SQL (없으면 서버가 생성) */
  normalized_sql?: string;
  /** 결과 스키마 (컬럼명+타입) */
  result_schema?: Array<{ name: string; type: string }>;
  /** 분류 태그 */
  tags?: string[];
}
```

> **`org_id`는 바디에 포함하지 않음** — 서버가 `access_token → membership → effective_org_id`로 결정하여 강제 삽입. (섹션 7.1 참조)

### 3.3 SQL 파싱 결과

```typescript
/** SQL 파서 결과 (2-stage) */
export interface SqlParseResult {
  /** 사용된 방언 */
  dialect_used: string;
  /** 정규화 SQL (리터럴 마스킹 완료) */
  normalized_sql: string;
  /** 파서 경고 */
  warnings: string[];
  /** 파서 에러 */
  errors: string[];
  /** 파싱 신뢰도 (0~1, 연속값) */
  confidence: number;
  /** 파싱 모드 */
  mode: 'primary' | 'fallback';
  /** 추출된 테이블 */
  tables: Array<{ name: string; alias?: string; schema?: string }>;
  /** 추출된 조인 */
  joins: Array<{ left: string; right: string; type: string }>;
  /** 추출된 프레디킷 (WHERE/HAVING 조건) */
  predicates: Array<{ expr: string; columns: string[]; op: string }>;
  /** SELECT 컬럼 */
  select_columns: Array<{ table?: string; column: string; aggregate?: string }>;
  /** GROUP BY 컬럼 */
  group_by_columns: string[];
}
```

### 3.4 Impact Graph 전용 타입

```typescript
/** KPI 노드 */
export interface KpiNode extends GraphNode {
  type: 'KPI';
  kpi_name: string;
  current_value?: number;
  trend?: 'up' | 'down' | 'stable';
  change_pct?: number;
  fingerprint: string;       // sha256(datasource + table + column + aggregate + filters_signature)
  /** 온톨로지 매핑 시 aliases/description */
  aliases?: string[];
  description?: string;
}

/** Driver 노드 */
export interface DriverNode extends GraphNode {
  type: 'DRIVER';
  table: string;
  column: string;
  usage_frequency: number;
  centrality: number;
  discriminative: number;
  variance: number;
  cardinality_est: number;     // NDV 근사치
  sample_size: number;         // 분석에 사용된 쿼리 수
  top_values?: Array<{ value: string; count: number }>;
}

/** Dimension 노드 (GROUP BY 전용, Driver와 분리) */
export interface DimensionNode extends GraphNode {
  type: 'DIMENSION';
  table: string;
  column: string;
  cardinality_est: number;
  usage_in_group_by: number;
}

/** Predicate 노드 (WHERE/HAVING 조건절) */
export interface PredicateNode extends GraphNode {
  type: 'PREDICATE';
  expression: string;
  operator: string;
  columns: string[];
}

/** 영향 경로 */
export interface ImpactPath {
  path_id: string;
  kpi_id: string;
  driver_id: string;
  nodes: string[];             // 노드 ID 시퀀스
  strength: number;            // 영향 강도
  queries_count: number;
}
```

### 3.5 Driver 점수 브레이크다운

```typescript
/** Driver 점수 분해 (운영 CS 감소용) */
export interface DriverScoreBreakdown {
  driver_id: string;
  score: number;               // 최종 점수 (0~1)
  breakdown: {
    usage: number;             // 가중 기여분
    kpi_connection: number;
    centrality: number;
    discriminative: number;
    volatility: number;
    cardinality_adjust: number; // 감점 (음수 가능)
    sample_size_guard: number;  // 표본수 보정
  };
  cardinality_est: number;
  sample_size: number;
}
```

### 3.6 비동기 작업(Job) 타입

```typescript
/** Insight 비동기 작업 */
export interface InsightJob {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'failed';
  progress_pct?: number;
  poll_after_ms: number;       // 다음 폴링까지 권장 대기 시간
  created_at: string;
  completed_at?: string;
  result_url?: string;         // 완료 시 결과 URL
  error?: string;
}
```

### 3.7 Instance Graph 전용 타입

```typescript
/** 레코드 노드 */
export interface RecordNode extends GraphNode {
  type: 'RECORD';
  table: string;
  pk_value: string;
  summary: Record<string, unknown>;
  degree: number;
}

/** Instance Graph 요청 */
export interface InstanceGraphRequest {
  datasource: string;
  seed_table: string;
  seed_pk: string;
  depth?: number;            // 기본 2, 최대 3
  max_nodes?: number;        // 기본 200, 최대 500
}
```

### 3.8 저장소 스키마 상세 (DDL)

**insight_query_logs** (PostgreSQL — 쿼리 로그 마스터 테이블):

```sql
CREATE TABLE insight_query_logs (
    id              BIGSERIAL       NOT NULL,
    org_id          TEXT            NOT NULL,
    datasource      TEXT            NOT NULL,
    query_id        TEXT            NOT NULL,       -- idempotency key (hash)
    request_id      TEXT,
    trace_id        TEXT,
    dialect         TEXT            NOT NULL DEFAULT 'postgres',
    executed_at     TIMESTAMPTZ     NOT NULL,
    status          TEXT            NOT NULL CHECK (status IN ('generated','executed','failed')),
    duration_ms     INTEGER,
    row_count       INTEGER,
    error_code      TEXT,
    user_id         TEXT,
    user_role       TEXT,
    nl_query        TEXT,
    intent          TEXT,
    sql_raw_enc     BYTEA,                          -- 원본 SQL (AES-256 암호화)
    normalized_sql  TEXT            NOT NULL,        -- 마스킹 완료 SQL
    result_schema   JSONB,
    tags            TEXT[],
    -- 파싱 결과 (비정규화, 분석 성능용)
    parse_mode      TEXT            CHECK (parse_mode IN ('primary','fallback')),
    parse_confidence FLOAT,
    parsed_tables   TEXT[],                          -- 추출된 테이블 목록
    parsed_joins    JSONB,
    parsed_predicates JSONB,
    parsed_group_by TEXT[],
    -- 메타
    ingest_batch_id TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, id)
) PARTITION BY LIST (org_id);

-- 인덱스 전략
CREATE INDEX idx_iql_org_ds_time ON insight_query_logs (org_id, datasource, executed_at DESC);
CREATE INDEX idx_iql_org_query_id ON insight_query_logs (org_id, query_id);    -- 멱등성 조회
CREATE INDEX idx_iql_org_trace ON insight_query_logs (org_id, trace_id);       -- trace 추적
CREATE INDEX idx_iql_parsed_tables ON insight_query_logs USING GIN (parsed_tables);  -- 테이블 검색
CREATE INDEX idx_iql_tags ON insight_query_logs USING GIN (tags);

-- RLS
ALTER TABLE insight_query_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON insight_query_logs
    USING (org_id = current_setting('app.current_org_id'));
```

**insight_driver_scores** (PostgreSQL — Driver 점수 히스토리):

```sql
CREATE TABLE insight_driver_scores (
    id              BIGSERIAL       NOT NULL,
    org_id          TEXT            NOT NULL,
    driver_id       TEXT            NOT NULL,       -- 예: drv_{table}_{column}
    kpi_fingerprint TEXT            NOT NULL,
    datasource      TEXT            NOT NULL,
    table_name      TEXT            NOT NULL,
    column_name     TEXT            NOT NULL,
    role            TEXT            NOT NULL CHECK (role IN ('DRIVER','DIMENSION')),
    -- 점수
    score           FLOAT           NOT NULL,
    breakdown       JSONB           NOT NULL,       -- DriverScoreBreakdown.breakdown
    -- 통계
    cardinality_est INTEGER,
    sample_size     INTEGER         NOT NULL,
    total_rows      BIGINT,
    -- 기간
    time_range_from DATE            NOT NULL,
    time_range_to   DATE            NOT NULL,
    analysis_version TEXT           NOT NULL,       -- "2026-02-26.1"
    -- 메타
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    PRIMARY KEY (org_id, id)
);

CREATE INDEX idx_ids_org_kpi ON insight_driver_scores (org_id, kpi_fingerprint, score DESC);
CREATE INDEX idx_ids_org_driver ON insight_driver_scores (org_id, driver_id);

ALTER TABLE insight_driver_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON insight_driver_scores
    USING (org_id = current_setting('app.current_org_id'));
```

**마이그레이션 전략**:
- Alembic 마이그레이션 파일로 관리 (`services/weaver/alembic/versions/`)
- 파티션은 최초 org 생성 시 `CREATE TABLE insight_query_logs_{org_id} PARTITION OF ...`
- 인덱스는 파티션별 자동 상속

### 3.9 Zustand 상태 관리 인터페이스

```typescript
// features/insight/store/useInsightStore.ts
import { create } from 'zustand';

interface InsightState {
  // KPI 선택
  selectedKpiId: string | null;
  selectedKpiFingerprint: string | null;

  // 그래프 데이터
  impactGraph: GraphData | null;
  impactGraphLoading: boolean;
  impactGraphError: string | null;

  // 비동기 작업
  currentJobId: string | null;
  jobStatus: InsightJob | null;

  // Driver 선택/상세
  selectedDriverId: string | null;
  driverDetail: DriverDetailResponse | null;
  driverDetailLoading: boolean;

  // 경로 비교
  highlightedPaths: string[];          // 활성화된 path_id 배열 (최대 3)

  // 필터
  timeRange: '7d' | '30d' | '90d';
  datasource: string | null;

  // 뷰 상태
  nodeDetailOpen: boolean;
  kpiMiniChartExpanded: boolean;

  // 액션
  selectKpi: (kpiId: string, fingerprint: string) => void;
  clearKpi: () => void;
  setImpactGraph: (graph: GraphData) => void;
  setImpactGraphLoading: (loading: boolean) => void;
  setImpactGraphError: (error: string | null) => void;
  setJobStatus: (job: InsightJob | null) => void;
  selectDriver: (driverId: string | null) => void;
  setDriverDetail: (detail: DriverDetailResponse | null) => void;
  togglePath: (pathId: string) => void;
  setTimeRange: (range: '7d' | '30d' | '90d') => void;
  setDatasource: (ds: string | null) => void;
  reset: () => void;
}

export const useInsightStore = create<InsightState>((set, get) => ({
  // 초기값
  selectedKpiId: null,
  selectedKpiFingerprint: null,
  impactGraph: null,
  impactGraphLoading: false,
  impactGraphError: null,
  currentJobId: null,
  jobStatus: null,
  selectedDriverId: null,
  driverDetail: null,
  driverDetailLoading: false,
  highlightedPaths: [],
  timeRange: '30d',
  datasource: null,
  nodeDetailOpen: false,
  kpiMiniChartExpanded: false,

  // 액션 구현
  selectKpi: (kpiId, fingerprint) => set({
    selectedKpiId: kpiId,
    selectedKpiFingerprint: fingerprint,
    selectedDriverId: null,
    driverDetail: null,
    highlightedPaths: [],
    impactGraph: null,
    impactGraphError: null,
  }),

  clearKpi: () => set({
    selectedKpiId: null,
    selectedKpiFingerprint: null,
    impactGraph: null,
    selectedDriverId: null,
    driverDetail: null,
    highlightedPaths: [],
  }),

  setImpactGraph: (graph) => set({ impactGraph: graph, impactGraphLoading: false }),
  setImpactGraphLoading: (loading) => set({ impactGraphLoading: loading }),
  setImpactGraphError: (error) => set({ impactGraphError: error, impactGraphLoading: false }),
  setJobStatus: (job) => set({ jobStatus: job, currentJobId: job?.job_id ?? null }),

  selectDriver: (driverId) => set({
    selectedDriverId: driverId,
    nodeDetailOpen: driverId !== null,
    driverDetail: null,
    driverDetailLoading: driverId !== null,
  }),

  setDriverDetail: (detail) => set({ driverDetail: detail, driverDetailLoading: false }),

  togglePath: (pathId) => {
    const current = get().highlightedPaths;
    if (current.includes(pathId)) {
      set({ highlightedPaths: current.filter((p) => p !== pathId) });
    } else if (current.length < 3) {
      set({ highlightedPaths: [...current, pathId] });
    }
    // 최대 3개 제한: 이미 3개면 추가 무시
  },

  setTimeRange: (range) => set({ timeRange: range }),
  setDatasource: (ds) => set({ datasource: ds }),

  reset: () => set({
    selectedKpiId: null,
    selectedKpiFingerprint: null,
    impactGraph: null,
    impactGraphLoading: false,
    impactGraphError: null,
    currentJobId: null,
    jobStatus: null,
    selectedDriverId: null,
    driverDetail: null,
    driverDetailLoading: false,
    highlightedPaths: [],
    nodeDetailOpen: false,
    kpiMiniChartExpanded: false,
  }),
}));
```

---

## 4. API Contracts

### 4.1 `POST /api/insight/logs` — 쿼리 로그 인제스트

단건/복수 인제스트. 클라이언트 idempotency_key 선택 입력 가능.

```
Request:
  Headers:
    Authorization: Bearer <access_token>
    Content-Type: application/json
  Body:
  {
    "entries": [ <QueryLogItem>, ... ],
    "idempotency_key": "optional-client-side-key"
  }

Response 200:
{
  "accepted": 12,
  "deduped": 3,
  "rejected": 0,
  "errors": [],
  "ingest_batch_id": "uuid"
}
```

### 4.1.1 `POST /api/insight/logs:ingest` — 배치 인제스트 (멱등성 강화)

운영 파이프라인/재시도용. 서버 측 idempotency key 생성을 강제.

```
Request:
  Headers:
    Authorization: Bearer <access_token>
  Body:
  {
    "entries": [ <QueryLogItem>, ... ]
  }

서버 Idempotency Key 생성 규칙:
  hash(normalized_sql + effective_org_id + datasource + time_bucket_1m(executed_at))

  - normalized_sql이 없으면 서버가 sql_parser + pii_masker로 생성
  - time_bucket은 executed_at 기준 1분 단위 (예: 2026-02-26T10:30)

Response 200:
{
  "accepted": 10,
  "deduped": 2,
  "rejected": 1,
  "errors": [
    { "index": 5, "reason": "SQL parse failed and no normalized_sql provided" }
  ],
  "ingest_batch_id": "uuid"
}
```

> **동일 키 재요청 시**: 200 OK + `deduped` 카운트 증가. 409 대신 OK로 처리 (배치 운영 편의).

### 4.2 `GET /api/insight/kpis` — KPI 목록

```
Request:
  Headers: Authorization: Bearer <access_token>
  Query Params:
    datasource?: string
    time_range?: string      # 7d | 30d | 90d (기본: 30d)
    offset?: number          # (기본: 0)
    limit?: number           # (기본: 50, 최대: 200)

Response 200:
{
  "kpis": [
    {
      "id": "kpi_ar_balance",
      "name": "AR Balance",
      "source": "ontology",       // "ontology" | "query_log" | "merged"
      "primary": true,            // merged 시 ontology가 primary
      "fingerprint": "sha256:...",
      "table": "invoices",
      "column": "amount",
      "aggregate": "SUM",
      "filters_signature": "",    // fingerprint에 포함된 필터 서명
      "query_count": 45,
      "last_value": 12300000,
      "trend": "up",
      "change_pct": 12.5,
      "aliases": ["매출채권잔액"],
      "description": "총 미수금 합계"
    }
  ],
  "total": 15,
  "pagination": { "offset": 0, "limit": 50 }
}
```

**KPI 중복 제거 / 병합 규칙**:

```python
def compute_kpi_fingerprint(
    datasource: str, table: str, column: str,
    aggregate: str, filters_signature: str = ""
) -> str:
    raw = f"{datasource}:{table.lower()}.{column.lower()}.{aggregate.upper()}"
    if filters_signature:
        raw += f":{filters_signature}"
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"

def merge_kpis(ontology_kpis: list, query_log_kpis: list) -> list:
    fp_map = {}
    for kpi in ontology_kpis:
        fp_map[kpi.fingerprint] = {**kpi, 'source': 'ontology', 'primary': True}
    for kpi in query_log_kpis:
        if kpi.fingerprint in fp_map:
            fp_map[kpi.fingerprint]['source'] = 'merged'
            fp_map[kpi.fingerprint]['query_count'] = kpi.query_count
        else:
            fp_map[kpi.fingerprint] = {**kpi, 'source': 'query_log', 'primary': False}
    return list(fp_map.values())
```

### 4.3 `GET /api/insight/impact` — KPI 영향 그래프 (200/202)

```
Request:
  Headers: Authorization: Bearer <access_token>
  Query Params:
    kpi_fingerprint: string    # KPI fingerprint (필수)
    kpi_id?: string            # fallback ID
    top_drivers?: number       # (기본: 20, 최대: 50)
    time_range?: string        # 7d | 30d | 90d (기본: 30d)
    include_paths?: boolean    # (기본: true)
    layout?: 'client' | 'server'  # 서버 프리레이아웃 옵션 (P1)

Response 200 (캐시 히트 또는 즉시 생성):
{
  "kpi": {
    "id": "kpi_ar_balance",
    "name": "AR Balance",
    "fingerprint": "sha256:...",
    "current_value": 12300000,
    "trend": "up",
    "source": "ontology",
    "primary": true
  },
  "graph": {
    "meta": {
      "schema_version": "insight/v3",
      "analysis_version": "2026-02-26.1",
      "generated_at": "2026-02-26T10:00:00Z",
      "time_range": { "from": "2026-01-27", "to": "2026-02-26" },
      "datasource": "insolvency_pg",
      "cache_hit": true,
      "cache_ttl_remaining_s": 480,
      "limits": { "max_nodes": 120, "max_edges": 300, "depth": 3, "top_drivers": 20 },
      "truncated": false,
      "trace_id": "trace-abc-123",
      "explain": {
        "scoring_formula": "usage×0.35 + kpi×0.25 + centrality×0.20 + disc×0.10 + var×0.10",
        "total_queries_analyzed": 234,
        "time_range_used": "30d",
        "mode": "primary"
      }
    },
    "nodes": [
      { "id": "kpi_ar_balance", "label": "AR Balance", "type": "KPI",
        "source": "ontology", "confidence": 1.0, ... },
      { "id": "drv_customer_region", "label": "customer.region", "type": "DRIVER",
        "source": "query_log", "confidence": 0.87, "score": 81,
        "cardinality_est": 156, "sample_size": 234, ... },
      { "id": "dim_invoice_month", "label": "invoice.month", "type": "DIMENSION",
        "source": "query_log", "confidence": 0.92, "cardinality_est": 12, ... },
      { "id": "trn_monthly_agg", "label": "월별 집계", "type": "TRANSFORM",
        "source": "query_log", "confidence": 0.80, ... }
    ],
    "edges": [
      { "source": "drv_customer_region", "target": "trn_monthly_agg",
        "type": "WHERE_FILTER", "weight": 0.8, "confidence": 0.87 },
      { "source": "dim_invoice_month", "target": "trn_monthly_agg",
        "type": "GROUP_BY", "weight": 0.6, "confidence": 0.92 },
      { "source": "trn_monthly_agg", "target": "kpi_ar_balance",
        "type": "AGGREGATE", "weight": 1.0, "confidence": 1.0 }
    ]
  },
  "paths": [
    { "path_id": "p1", "kpi_id": "kpi_ar_balance", "driver_id": "drv_customer_region",
      "nodes": ["drv_customer_region", "trn_monthly_agg", "kpi_ar_balance"],
      "strength": 0.87, "queries_count": 15 }
  ]
}

Response 202 (캐시 미스 + 생성에 시간 소요):
{
  "job_id": "job_abc123",
  "status": "queued",
  "poll_after_ms": 800
}
```

### 4.4 `GET /api/insight/drivers` — Driver 랭킹

```
Request:
  Headers: Authorization: Bearer <access_token>
  Query Params:
    datasource?: string
    kpi_id?: string
    kpi_fingerprint?: string
    time_range?: string
    offset?: number        # (기본: 0)
    limit?: number         # (기본: 30, 최대: 100)

Response 200:
{
  "drivers": [
    {
      "id": "drv_customer_region",
      "table": "customers",
      "column": "region",
      "role": "DRIVER",
      "source": "query_log",
      "score": 0.81,
      "cardinality_est": 156,
      "sample_size": 234,
      "connected_kpis": ["kpi_ar_balance", "kpi_revenue"],
      "top_values": [
        { "value": "서울", "count": 1234 },
        { "value": "부산", "count": 567 }
      ]
    }
  ],
  "total": 30,
  "pagination": { "offset": 0, "limit": 30 },
  "scoring_info": {
    "min_queries": 50,
    "total_queries_analyzed": 234,
    "formula": "usage×0.35 + kpi×0.25 + centrality×0.20 + disc×0.10 + var×0.10"
  }
}
```

### 4.5 `GET /api/insight/drivers/{driver_id}` — Driver 상세 + Evidence (P1)

운영 CS 감소를 위한 점수 근거 및 Evidence 제공.

```
Request:
  Headers: Authorization: Bearer <access_token>
  Path Params: driver_id
  Query Params:
    time_range?: string

Response 200:
{
  "driver": {
    "driver_id": "drv_customer_region",
    "label": "customers.region",
    "type": "DRIVER",
    "source": "query_log",
    "score": 0.81,
    "breakdown": {
      "usage": 0.25,
      "kpi_connection": 0.20,
      "centrality": 0.15,
      "discriminative": 0.11,
      "volatility": 0.10,
      "cardinality_adjust": -0.05,
      "sample_size_guard": 0.05
    },
    "cardinality_est": 156,
    "sample_size": 234,
    "total_rows": 12345
  },
  "evidence": {
    "top_queries": [
      { "query_id": "q1", "normalized_sql": "SELECT ... WHERE region = ?",
        "count": 120, "executed_at": "2026-02-26T10:30:00Z" },
      { "query_id": "q2", "normalized_sql": "SELECT ... GROUP BY region",
        "count": 85 }
    ],
    "paths": [
      { "path_id": "p1", "nodes": ["KPI:rev", "TABLE:invoice", "COLUMN:region"],
        "weight": 0.62 }
    ]
  },
  "value_distribution": {
    "top_values": [
      { "value": "서울", "count": 1234, "pct": 34.5 },
      { "value": "부산", "count": 567, "pct": 15.8 }
    ],
    "total_distinct": 156,
    "null_count": 23
  }
}
```

### 4.6 `GET /api/insight/kpi/timeseries` — KPI 시계열 (P2)

Driver별로 분할된 KPI 시계열 조회. NodeDetailPanel 미니차트에 사용.

```
Request:
  Headers: Authorization: Bearer <access_token>
  Query Params:
    kpi_fingerprint: string
    driver_id?: string       # 지정 시 driver 값별 분할
    time_range?: string      # 7d | 30d | 90d
    granularity?: string     # day | week (기본: day)

Response 200:
{
  "kpi_name": "AR Balance",
  "series": [
    { "date": "2026-02-20", "value": 12000000, "driver_value": "서울" },
    { "date": "2026-02-20", "value": 5500000, "driver_value": "부산" },
    { "date": "2026-02-21", "value": 12300000, "driver_value": "서울" },
    ...
  ],
  "meta": {
    "schema_version": "insight/v3",
    "time_range": { "from": "2026-01-27", "to": "2026-02-26" },
    "granularity": "day"
  }
}
```

### 4.7 `POST /api/insight/instance-graph` — 인스턴스 그래프

```
Request:
  Headers: Authorization: Bearer <access_token>
  Body: <InstanceGraphRequest>

Response 200:
{
  "graph": {
    "meta": { ...GraphMeta },
    "nodes": [ ...RecordNode ],
    "edges": [ ...GraphEdge(FK) ]
  }
}
```

### 4.8 `POST /api/insight/query-subgraph` — SQL 서브그래프

```
Request:
  Headers: Authorization: Bearer <access_token>
  Body:
  {
    "sql": "SELECT c.name, SUM(i.amount) FROM customers c JOIN invoices i ON c.id = i.customer_id WHERE i.status = 'PAID' GROUP BY c.name",
    "datasource": "insolvency_pg"
  }

Response 200:
{
  "parse_result": <SqlParseResult>,
  "graph": <GraphData>
}
```

### 4.9 `GET /api/insight/jobs/{job_id}` — 작업 상태

```
Response 200:
{
  "job_id": "job_abc123",
  "status": "queued" | "running" | "done" | "failed",
  "progress_pct": 65,
  "poll_after_ms": 800,
  "created_at": "2026-02-26T10:30:00Z",
  "completed_at": null,
  "result_url": null,
  "error": null
}
```

### 4.9.1 `GET /api/insight/jobs/{job_id}/events` — SSE 이벤트 (P1)

```
Response: text/event-stream

data: {"status": "running", "progress_pct": 30, "message": "Analyzing query logs..."}

data: {"status": "running", "progress_pct": 70, "message": "Building impact graph..."}

data: {"status": "done", "progress_pct": 100, "result_url": "/api/insight/impact?_cache_key=job_abc123"}
```

### 4.10 `GET /api/ontology/preview/coverage` — 매핑 신뢰도/커버리지 (P2)

```
Request:
  Headers: Authorization: Bearer <access_token>
  Query Params:
    datasource?: string

Response 200:
{
  "tables": [
    {
      "table": "invoices",
      "coverage": 0.82,
      "confidence": 0.74,
      "mapped_columns": 41,
      "total_columns": 50,
      "mapping_method": "rule",     // manual | rule | auto
      "conflicts": 0
    }
  ],
  "overall": {
    "avg_coverage": 0.75,
    "avg_confidence": 0.68,
    "total_tables": 12,
    "mapped_tables": 9
  }
}
```

**Coverage / Confidence 산출 공식** (P2-1):

```python
def compute_table_coverage(table: str, datasource: str) -> dict:
    """테이블별 매핑 커버리지 + 신뢰도 계산"""
    total_cols = get_column_count(datasource, table)
    mapped_cols = get_mapped_column_count(datasource, table)

    # Coverage: 매핑된 컬럼 비율
    coverage = mapped_cols / total_cols if total_cols > 0 else 0.0

    # Confidence: 매핑 방식별 가중 평균 + 충돌 감점
    METHOD_WEIGHTS = {
        'manual': 1.0,      # 수동 매핑 — 최고 신뢰
        'rule': 0.75,        # 규칙 기반 매핑
        'auto': 0.50,        # 자동 추정 매핑
    }
    mappings = get_column_mappings(datasource, table)
    if not mappings:
        return {"coverage": 0.0, "confidence": 0.0, "mapping_method": "none"}

    # 가중 평균
    weighted_sum = sum(METHOD_WEIGHTS.get(m.method, 0.3) for m in mappings)
    base_confidence = weighted_sum / len(mappings)

    # 충돌 감점: 동일 컬럼에 2개 이상 매핑 존재 시
    conflict_count = count_conflicts(datasource, table)
    conflict_penalty = min(conflict_count * 0.05, 0.20)  # 최대 -0.20

    # 주 매핑 방식 결정 (가장 빈번한 method)
    primary_method = most_common([m.method for m in mappings])

    return {
        "coverage": round(coverage, 2),
        "confidence": round(max(0, base_confidence - conflict_penalty), 2),
        "mapped_columns": mapped_cols,
        "total_columns": total_cols,
        "mapping_method": primary_method,
        "conflicts": conflict_count,
    }
```

### 4.11 API 에러 응답 표준

모든 Insight API가 공유하는 에러 응답 포맷.

**공통 에러 바디**:

```json
{
  "error": {
    "code": "INSIGHT_ERR_CODE",
    "message": "사람이 읽을 수 있는 설명",
    "detail": "디버깅용 기술 상세 (운영 환경에서는 생략 가능)",
    "trace_id": "trace-abc-123"
  }
}
```

**HTTP 상태 코드별 에러 매핑**:

| 상태 코드 | 에러 코드 | 조건 | 응답 예시 |
|---|---|---|---|
| **400** | `INVALID_PARAMS` | 필수 파라미터 누락/형식 오류 | `kpi_fingerprint is required` |
| **400** | `SQL_PARSE_FAILED` | SQL 파싱 완전 실패 (fallback도 불가) | `Unable to parse SQL` |
| **401** | `UNAUTHORIZED` | 토큰 없음/만료 | `Access token expired` |
| **403** | `FORBIDDEN` | 권한 부족 (RoleGuard) | `Insufficient role for this resource` |
| **404** | `KPI_NOT_FOUND` | fingerprint/id로 KPI 미발견 | `KPI not found: sha256:...` |
| **404** | `DRIVER_NOT_FOUND` | driver_id 미발견 | `Driver not found: drv_...` |
| **404** | `JOB_NOT_FOUND` | job_id 미발견 | `Job not found: job_...` |
| **409** | `JOB_ALREADY_RUNNING` | 동일 KPI에 대해 Job 진행 중 | `Analysis already in progress` |
| **413** | `PAYLOAD_TOO_LARGE` | SQL > 100KB 또는 배치 > 100건 | `SQL too large (120000 chars, max 100000)` |
| **422** | `UNSUPPORTED_DIALECT` | 지원하지 않는 SQL 방언 | `Dialect 'teradata' not supported` |
| **429** | `RATE_LIMITED` | 요청 빈도 초과 | `Rate limit exceeded, retry after 30s` |
| **500** | `INTERNAL_ERROR` | 서버 내부 오류 | `Internal server error` |
| **503** | `SERVICE_UNAVAILABLE` | 의존 서비스 불가 (Redis/Neo4j) | `Graph service temporarily unavailable` |

**FastAPI 에러 핸들러 예시**:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

class InsightError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, detail: str = ""):
        self.code = code
        self.message = message
        self.status = status
        self.detail = detail

async def insight_error_handler(request: Request, exc: InsightError) -> JSONResponse:
    trace_id = request.headers.get("X-Trace-Id", "")
    body = {
        "error": {
            "code": exc.code,
            "message": exc.message,
            "trace_id": trace_id,
        }
    }
    if settings.DEBUG and exc.detail:
        body["error"]["detail"] = exc.detail
    return JSONResponse(status_code=exc.status, content=body)

# 등록
app.add_exception_handler(InsightError, insight_error_handler)
```

---

## 5. SQL 파서 & 처리 전략

### 5.1 2-Stage 파싱 전략

| Stage | 엔진 | confidence | 결과 |
|---|---|---|---|
| Primary | sqlglot AST (RAISE mode) | 0.85~1.0 | 완전한 테이블/조인/프레디킷/컬럼 추출 |
| Primary (WARN) | sqlglot AST (WARN mode) | 0.50~0.84 | 부분 추출, 경고 포함 |
| Fallback | 정규식/토큰 기반 | 0.10~0.49 | FROM/JOIN 테이블 + WHERE 컬럼 패턴만 |

### 5.2 Primary Parse: sqlglot AST

```python
import sqlglot
from sqlglot import exp

def parse_sql_primary(sql: str, dialect: str = "postgres") -> tuple[SqlParseResult | None, float]:
    """Primary: sqlglot AST 기반 완전 파싱"""
    try:
        tree = sqlglot.parse_one(sql, read=dialect, error_level=sqlglot.ErrorLevel.RAISE)
        result = extract_from_ast(tree)
        return result, 0.95
    except sqlglot.errors.ParseError:
        pass
    # WARN mode: 부분 파싱 시도
    try:
        tree = sqlglot.parse_one(sql, read=dialect, error_level=sqlglot.ErrorLevel.WARN)
        result = extract_from_ast(tree)
        return result, 0.65
    except Exception:
        return None, 0.0
```

### 5.3 Fallback Parse: 정규식/토큰

```python
import re

_FROM_RE = re.compile(r'\bFROM\s+(["\w]+(?:\.["\w]+)?)\s*(?:AS\s+)?(\w+)?', re.IGNORECASE)
_JOIN_RE = re.compile(r'\bJOIN\s+(["\w]+(?:\.["\w]+)?)\s*(?:AS\s+)?(\w+)?', re.IGNORECASE)
_WHERE_COL_RE = re.compile(
    r'\bWHERE\b(.+?)(?:\bGROUP\b|\bORDER\b|\bLIMIT\b|\bHAVING\b|$)',
    re.IGNORECASE | re.DOTALL
)

def parse_sql_fallback(sql: str) -> SqlParseResult:
    """Fallback: 정규식 기반 최소 회복 파싱"""
    tables = [
        {"name": m.group(1), "alias": m.group(2)}
        for m in _FROM_RE.finditer(sql)
    ] + [
        {"name": m.group(1), "alias": m.group(2)}
        for m in _JOIN_RE.finditer(sql)
    ]

    predicates = []
    where_match = _WHERE_COL_RE.search(sql)
    if where_match:
        clause = where_match.group(1)
        for col_match in re.finditer(r'(\w+\.\w+)\s*(=|>|<|IN|LIKE|BETWEEN)', clause, re.IGNORECASE):
            predicates.append({
                "expr": col_match.group(0),
                "columns": [col_match.group(1)],
                "op": col_match.group(2).upper()
            })

    return SqlParseResult(
        dialect_used="unknown",
        normalized_sql="",
        warnings=["AST parsing failed, using regex fallback"],
        errors=[],
        confidence=0.3,
        mode="fallback",
        tables=tables,
        joins=[],
        predicates=predicates,
        select_columns=[],
        group_by_columns=[],
    )
```

### 5.4 통합 파서

```python
def parse_sql(sql: str, dialect: str = "postgres") -> SqlParseResult:
    """2-Stage SQL 파서"""
    # Stage 1: Primary (AST)
    result, confidence = parse_sql_primary(sql, dialect)
    if result is not None:
        result.mode = "primary"
        result.confidence = confidence
        result.dialect_used = dialect
        return result

    # Stage 2: Fallback (regex)
    return parse_sql_fallback(sql)
```

### 5.5 PII 마스킹 + 정규화 (P0-5)

```python
# core/pii_masker.py
import re

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
_PHONE_RE = re.compile(r'\b\d{2,4}[-.\s]?\d{3,4}[-.\s]?\d{4}\b')
_SSN_RE = re.compile(r'\b\d{6}[-]?\d{7}\b')
_STRING_LITERAL_RE = re.compile(r"'[^']*'")
_NUMBER_LITERAL_RE = re.compile(r'\b\d+\.?\d*\b(?!\.\w)')

def mask_pii(sql: str) -> str:
    """SQL 내 리터럴/PII 패턴 마스킹"""
    sql = _EMAIL_RE.sub("'[EMAIL]'", sql)
    sql = _PHONE_RE.sub("'[PHONE]'", sql)
    sql = _SSN_RE.sub("'[SSN]'", sql)
    sql = _STRING_LITERAL_RE.sub("?", sql)
    # 숫자 리터럴은 WHERE/HAVING 절에서만 마스킹 (SELECT의 상수는 보존)
    return sql

def normalize_sql(sql: str) -> str:
    """SQL 정규화: 공백 통일 + 대소문자 키워드 통일 + 리터럴 마스킹"""
    masked = mask_pii(sql)
    # 추가 정규화 (공백 통일, 키워드 대문자 등)
    return " ".join(masked.split())
```

### 5.6 Fallback 발동 시 그래프 구성 규칙

- `mode=fallback`이면:
  - TABLE 노드 중심으로만 그래프 생성 (COLUMN/PREDICATE 노드 최소화)
  - 모든 노드/엣지에 `confidence` ≤ 0.5 부여
  - UI: **"정확도 낮음(폴백)"** 배지 + "원문 SQL 보기" 버튼 우선 제공
  - 응답 `meta.explain.fallback_used = true`

### 5.7 캐시 키에 analysis_version 포함

```python
def build_cache_key(kpi_fingerprint: str, org_id: str, params: dict) -> str:
    """analysis_version을 포함한 캐시 키 생성"""
    key_parts = [
        f"insight:impact",
        org_id,
        kpi_fingerprint,
        params.get('time_range', '30d'),
        str(params.get('top_drivers', 20)),
        get_current_analysis_version()  # "2026-02-26.1"
    ]
    return ":".join(key_parts)
```

---

## 6. Driver 중요도 점수 설계

### 6.1 점수 공식

```
score = (usage × 0.35) + (kpi_connection × 0.25) + (centrality × 0.20) + (discriminative × 0.10) + (volatility × 0.10)
      + cardinality_adjust + sample_size_guard
```

### 6.2 각 항목 정의

| 항목 | 산출 방법 | 범위 | 설명 |
|---|---|---|---|
| `usage` | `COUNT(쿼리 등장) / MAX(전체 컬럼 등장)` | 0~1 | 정규화 등장 빈도 |
| `kpi_connection` | `COUNT(연결된 KPI) / MAX(KPI 연결 수)` | 0~1 | KPI 직간접 연결 |
| `centrality` | Betweenness Centrality 정규화 | 0~1 | 경로 중심성 |
| `discriminative` | `1 - (등장 비율)` | 0~1 | 고유성 |
| `volatility` | 최근 30일 CV 정규화 | 0~1 | 값 변동성 |
| `cardinality_adjust` | NDV 기반 감점 | -0.3~0 | PK/boolean 감점 |
| `sample_size_guard` | 표본수 보정 | -0.2~0 | 소표본 감점 |

### 6.3 후보군 필터링 규칙 (필수, P0)

Driver 후보는 아래 조건을 **모두** 만족해야 한다:

```python
def filter_driver_candidates(columns: list[ColumnStats], graph) -> list[ColumnStats]:
    """Driver 후보 필터링 — 노이즈 컬럼 사전 제거"""
    candidates = []
    for col in columns:
        # 1. WHERE/JOIN/GROUP BY에 등장한 적 있어야 함
        if col.where_count == 0 and col.join_count == 0 and col.group_by_count == 0:
            continue

        # 2. KPI measure 테이블로 연결되는 그래프 경로가 존재해야 함
        if not graph.has_path_to_kpi(col.table, col.column):
            continue

        # 3. PENALTY_COLUMNS 제외 (tenant_id는 완전 제외)
        if col.name == 'tenant_id' or col.name == 'org_id':
            continue

        # 4. SELECT 출력 전용 컬럼은 DIMENSION으로 분리
        if col.where_count == 0 and col.join_count == 0 and col.group_by_count > 0:
            col.role = 'DIMENSION'
            continue  # DRIVER가 아닌 DIMENSION으로 분류

        candidates.append(col)
    return candidates

PENALTY_COLUMNS = {
    'id', 'created_at', 'updated_at', 'deleted_at',
    'is_deleted', 'is_active', 'version', 'user_id',
}
# PENALTY_COLUMNS에 해당하는 컬럼은 score × 0.3 감점 적용
```

### 6.4 카디널리티 보정

```python
def cardinality_adjust(ndv: int, total_rows: int) -> float:
    """NDV 기반 카디널리티 감점"""
    if total_rows == 0:
        return 0.0
    ratio = ndv / total_rows
    if ratio > 0.95:    return -0.30   # PK/UUID
    elif ratio > 0.80:  return -0.15   # 높은 카디널리티
    elif ndv <= 2:      return -0.10   # boolean/flag (과대평가 방지)
    elif ndv <= 5:      return -0.05   # low-cardinality (status 등)
    return 0.0
```

### 6.5 최소 표본수 조건

```python
MIN_QUERIES_FOR_SCORING = 50  # 30일 기준 최소 50건

def sample_size_guard(query_count: int) -> float:
    """표본수 부족 시 감점"""
    if query_count < MIN_QUERIES_FOR_SCORING:
        return -0.20  # 최대 감점
    elif query_count < MIN_QUERIES_FOR_SCORING * 2:
        return -0.10  # 부분 감점
    return 0.0

# 미달 시 프론트엔드 안내:
# "분석 데이터가 부족합니다 (현재 N건, 최소 50건 필요). NL2SQL로 더 많은 쿼리를 실행하면 정확한 분석이 가능합니다."
```

### 6.6 Score Breakdown 저장

모든 Driver의 breakdown은 DB에 저장하고 API로 노출한다. (섹션 4.5 참조)

```python
def compute_driver_score(col: ColumnStats, graph) -> DriverScoreBreakdown:
    base = (
        col.usage_normalized * 0.35
        + col.kpi_connection_normalized * 0.25
        + col.centrality_normalized * 0.20
        + col.discriminative_normalized * 0.10
        + col.volatility_normalized * 0.10
    )
    card_adj = cardinality_adjust(col.ndv, col.total_rows)
    sample_adj = sample_size_guard(col.query_count)

    if col.name in PENALTY_COLUMNS:
        base *= 0.3

    final = max(0, min(1, base + card_adj + sample_adj))

    return DriverScoreBreakdown(
        driver_id=col.driver_id,
        score=final,
        breakdown={
            "usage": col.usage_normalized * 0.35,
            "kpi_connection": col.kpi_connection_normalized * 0.25,
            "centrality": col.centrality_normalized * 0.20,
            "discriminative": col.discriminative_normalized * 0.10,
            "volatility": col.volatility_normalized * 0.10,
            "cardinality_adjust": card_adj,
            "sample_size_guard": sample_adj,
        },
        cardinality_est=col.ndv,
        sample_size=col.query_count,
    )
```

---

## 7. 보안 & 격리

### 7.1 org_id 서버 주입 원칙

**모든 Insight API에 공통 적용되는 철칙:**

```
1. 요청 헤더의 org_id/tenant_id는 절대 신뢰하지 않음
2. 서버는 access_token → membership → effective_org_id로 스코프 결정
3. 요청 바디에서 org_id는 받지 않음 (있어도 무시)
4. 응답/저장 모두 effective_org_id로 강제 세팅
```

```python
# 공통 의존성
async def get_effective_org_id(token: str = Depends(verify_access_token)) -> str:
    """access_token에서 membership 기반 effective_org_id 추출"""
    claims = decode_jwt(token)
    membership = await get_user_membership(claims['sub'])
    return membership.org_id  # 서버 결정

# 모든 API에 적용
@router.post("/api/insight/logs")
async def ingest_logs(
    body: IngestRequest,
    org_id: str = Depends(get_effective_org_id),
):
    for entry in body.entries:
        entry.org_id = org_id  # 바디의 org_id는 무시, 서버 값으로 강제
    ...
```

### 7.2 저장소 격리

**PostgreSQL (QueryLogStore)**:
```sql
-- 파티셔닝 키에 org_id 포함
CREATE TABLE insight_query_logs (
    id BIGSERIAL,
    org_id TEXT NOT NULL,
    datasource TEXT NOT NULL,
    query_id TEXT NOT NULL,
    ...
    PRIMARY KEY (org_id, id)
) PARTITION BY LIST (org_id);

-- RLS 권장
ALTER TABLE insight_query_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON insight_query_logs
    USING (org_id = current_setting('app.current_org_id'));
```

**Neo4j (Synapse)**:
```cypher
-- 모든 노드에 org_id 필수 속성
CREATE (n:KPI {id: $id, org_id: $org_id, ...})

-- 모든 조회 Cypher에 org_id 조건 강제
MATCH (n:KPI {org_id: $org_id})
WHERE n.id = $kpi_id
RETURN n
```

**Redis 캐시 키**: `insight:{org_id}:impact:{kpi_fingerprint}:...`

### 7.3 입력 방어 (P0-5)

```python
MAX_SQL_LENGTH = 100_000  # 100KB
MAX_ENTRIES_PER_BATCH = 100
PARSE_TIMEOUT_MS = 200

@router.post("/api/insight/logs")
async def ingest_logs(body: IngestRequest, ...):
    # 1. 배치 크기 제한
    if len(body.entries) > MAX_ENTRIES_PER_BATCH:
        raise HTTPException(413, "Too many entries (max 100)")

    for entry in body.entries:
        # 2. SQL 길이 제한
        if len(entry.sql) > MAX_SQL_LENGTH:
            raise HTTPException(413, f"SQL too large ({len(entry.sql)} chars, max {MAX_SQL_LENGTH})")

        # 3. 파싱 타임아웃
        try:
            result = await asyncio.wait_for(
                parse_sql(entry.sql, entry.dialect),
                timeout=PARSE_TIMEOUT_MS / 1000
            )
        except asyncio.TimeoutError:
            entry.parse_result = fallback_minimal(entry.sql)
```

### 7.4 PII 마스킹 (P0-5)

- `normalized_sql` 생성 시 모든 리터럴 마스킹 (섹션 5.5 참조)
- 이메일/전화/주민등록번호 유사 패턴 검출 및 치환
- 그래프 노드의 `label`에 PII가 노출되지 않도록 검증
- 로그 저장 시 원본 SQL과 normalized_sql 분리 저장 (원본은 암호화)

### 7.5 trace_id 전파 (P0-5)

```
ingest(trace_id) → 분석(trace_id) → 그래프 응답(meta.trace_id)

1. POST /api/insight/logs 의 entries[].trace_id를 저장
2. 분석 파이프라인에서 trace_id 유지
3. GET /api/insight/impact 응답의 meta.trace_id에 포함
4. 응답 헤더: X-Trace-Id: <trace_id>
5. 프론트엔드: 개발자 도구에서 trace_id로 전체 경로 추적 가능
```

### 7.6 운영 모니터링 메트릭

> Prometheus / OpenTelemetry 기반 수집. Grafana 대시보드 + 알럿 연동.

**Ingest 파이프라인**

| 메트릭 | 타입 | 레이블 | 알럿 기준 |
|---|---|---|---|
| `insight.ingest.count` | Counter | `org_id`, `status` (ok/error) | error rate > 5% (5m) |
| `insight.ingest.entry_count` | Histogram | `org_id` | p99 > 80 entries/batch |
| `insight.ingest.duration_ms` | Histogram | `org_id` | p95 > 500ms |
| `insight.ingest.dedup_count` | Counter | `org_id` | — |
| `insight.forward.count` | Counter | `source` (oracle/manual) | error rate > 10% (5m) |

**분석 파이프라인**

| 메트릭 | 타입 | 레이블 | 알럿 기준 |
|---|---|---|---|
| `insight.parse.mode` | Counter | `mode` (primary/fallback), `dialect` | fallback ratio > 30% (1h) |
| `insight.parse.confidence` | Histogram | `mode` | primary p50 < 0.85 |
| `insight.parse.timeout_count` | Counter | `dialect` | > 10/min |
| `insight.impact.build_time_ms` | Histogram | `org_id`, `cache` (hit/miss) | p95 miss > 5000ms |
| `insight.impact.cache_hit_ratio` | Gauge | `org_id` | < 40% (1d) |
| `insight.impact.node_count` | Histogram | `org_id` | p99 > 100 |
| `insight.driver.score_compute_ms` | Histogram | `org_id` | p95 > 2000ms |

**저장소**

| 메트릭 | 타입 | 레이블 | 알럿 기준 |
|---|---|---|---|
| `insight.db.query_log_rows` | Gauge | `org_id` | > 10M rows/org |
| `insight.db.partition_size_bytes` | Gauge | `org_id` | > 5GB |
| `insight.cache.size_bytes` | Gauge | `cache_type` (graph/kpi) | > 1GB |
| `insight.cache.eviction_count` | Counter | `cache_type` | > 100/h |

**프론트엔드 (RUM)**

| 메트릭 | 타입 | 수집 방법 | 알럿 기준 |
|---|---|---|---|
| `insight.fe.graph_render_ms` | Histogram | `performance.measure()` | p95 > 1000ms |
| `insight.fe.ttfb_ms` | Histogram | Navigation Timing API | p95 > 800ms |
| `insight.fe.poll_retry_count` | Counter | useImpactGraph hook | avg > 5 retries |
| `insight.fe.error_boundary_hit` | Counter | ErrorBoundary `componentDidCatch` | > 0/5min |

```python
# 메트릭 수집 예시 (FastAPI middleware)
from prometheus_client import Counter, Histogram

INGEST_COUNT = Counter(
    "insight_ingest_count", "Ingest requests",
    ["org_id", "status"],
)
PARSE_MODE = Counter(
    "insight_parse_mode", "SQL parse mode usage",
    ["mode", "dialect"],
)
IMPACT_BUILD = Histogram(
    "insight_impact_build_time_ms", "Impact graph build time",
    ["org_id", "cache"],
    buckets=[100, 500, 1000, 2000, 5000, 10000],
)
```

---

## 8. 프론트엔드 화면 설계 & UX 규칙

### 8.1 Insight 페이지 (`/analysis/insight`)

```
┌──────────────────────────────────────────────────────────────────┐
│  Insight                             [7d ▾] [30d] [90d]  [⚙]   │
├──────────┬───────────────────────────────────────┬───────────────┤
│          │                                       │               │
│  KPI     │     Impact Graph (Cytoscape.js)       │  Node Detail  │
│  목록    │                                       │  Panel        │
│          │     ┌─────┐                           │               │
│  ● AR    │     │ KPI │  ◄── 중심 노드            │  [선택 노드   │
│    Balance│    └──┬──┘                           │   상세 정보]  │
│          │       │                               │               │
│  ○ 매출  │   ┌───┴───┐                           │  Score        │
│          │   │       │                           │  Breakdown    │
│  ○ 처리  │ ┌─┴─┐ ┌───┴──┐                       │  ──────────── │
│    건수  │ │D1 │ │ D2   │  ◄── Driver            │  usage  0.25  │
│          │ └───┘ └──────┘                        │  kpi   0.20  │
│  ───────│                                       │  cent  0.15  │
│  Top     │  ┌──────────────────────┐            │  disc  0.11  │
│  Drivers │  │ 경로 비교 Top 3       │            │  vol   0.10  │
│          │  │ ☑ Path 1 (0.87)      │            │  card  -0.05 │
│  1.region│  │ ☐ Path 2 (0.65)      │            │  ──── ─────  │
│  2.status│  │ ☐ Path 3 (0.42)      │            │  total 0.81  │
│  3.type  │  └──────────────────────┘            │               │
│          │                                       │  Evidence     │
│          │  ═══ 상태 바 ═════════════            │  ──────────── │
│          │  [primary ✓] [234 queries]            │  Top Queries: │
│          │  [nodes: 23/120] [cached ✓]           │   ▸ q1 (120) │
│          │  [trace: abc-123]                     │   ▸ q2 (85)  │
│          │                                       │               │
│ [더 보기…]│  [Truncated: 더 보기 →]               │  [KPI 미니    │
│          │                                       │   차트 ▼]     │
└──────────┴───────────────────────────────────────┴───────────────┘
```

### 8.2 UX 규칙 — "질문→근거→행동" 루프

**NodeDetailPanel 필수 섹션** (항상 노출):

1. **Score Breakdown**: Driver 점수의 모든 항목별 기여분 수치 표시
2. **Evidence — Top Queries**: 이 Driver가 등장한 상위 쿼리 목록 (항상 노출)
   - 클릭 시: Query Subgraph 탭으로 점프 + 해당 쿼리 하이라이트
3. **경로 비교 Top 3**: 체크박스 토글로 그래프 하이라이트 전환
4. **KPI 미니차트** (P2): Driver 값별로 분할된 KPI 시계열
   - `GET /api/insight/kpi/timeseries?kpi=...&driver=...` 호출
   - 접힌 상태로 기본 표시, 클릭 시 펼침

### 8.3 동작 흐름

1. 페이지 진입 → KPI 목록 로드 (페이지네이션)
2. KPI 선택 → `GET /api/insight/impact?kpi_fingerprint=...`
3. **200** → 즉시 렌더링
4. **202** → 로딩 UI + "근거 수집/분석 중" + 폴링 (또는 SSE)
   - `poll_after_ms` 간격으로 폴링
   - 완료 → 자동 렌더
   - **실패** → "폴백 그래프(테이블 중심)" 또는 "최근 캐시 보기" 버튼
5. Driver 노드 클릭 → `GET /api/insight/drivers/{id}` → 우측 패널에 상세 + Evidence
6. Driver 더블클릭 → 경로 하이라이트
7. `meta.truncated === true` → "더 보기" 버튼 (limit 증가 재요청)
8. `meta.explain` 정보를 그래프 하단 상태 바에 표시

#### 8.3.1 `useImpactGraph` 폴링 훅 상세

```typescript
// hooks/useImpactGraph.ts
import { useCallback, useEffect, useRef } from 'react';
import { useInsightStore } from '@/stores/insightStore';

type JobStatus = 'idle' | 'loading' | 'polling' | 'done' | 'error';

interface UseImpactGraphReturn {
  status: JobStatus;
  data: ImpactGraphResponse | null;
  error: InsightError | null;
  retry: () => void;
  cancel: () => void;
}

export function useImpactGraph(
  kpiFingerprint: string | null,
  timeRange: '7d' | '30d' | '90d',
): UseImpactGraphReturn {
  const abortRef = useRef<AbortController | null>(null);
  const pollCountRef = useRef(0);
  const setGraph = useInsightStore((s) => s.setGraph);
  const setLoading = useInsightStore((s) => s.setLoading);

  const MAX_POLL = 30;           // 최대 폴링 횟수
  const MAX_POLL_TOTAL_MS = 300_000; // 전체 타임아웃 5분
  const startTimeRef = useRef(0);

  const fetchGraph = useCallback(async () => {
    if (!kpiFingerprint) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();
    pollCountRef.current = 0;
    startTimeRef.current = Date.now();
    setLoading(true);

    try {
      const res = await fetch(
        `/api/insight/impact?kpi_fingerprint=${kpiFingerprint}&time_range=${timeRange}`,
        { signal: abortRef.current.signal },
      );

      // ── 200: 캐시 히트 → 즉시 렌더 ──
      if (res.status === 200) {
        const body: ImpactGraphResponse = await res.json();
        setGraph(body);
        return;
      }

      // ── 202: 캐시 미스 → 폴링 시작 ──
      if (res.status === 202) {
        const { job_id, poll_after_ms } = await res.json();
        await pollJob(job_id, poll_after_ms);
        return;
      }

      // ── 그 외 에러 ──
      throw new InsightError(res.status, await res.text());
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      throw err;
    } finally {
      setLoading(false);
    }
  }, [kpiFingerprint, timeRange]);

  async function pollJob(jobId: string, intervalMs: number) {
    while (pollCountRef.current < MAX_POLL) {
      // 전체 타임아웃 체크
      if (Date.now() - startTimeRef.current > MAX_POLL_TOTAL_MS) {
        throw new InsightError(408, '분석 시간이 초과되었습니다');
      }

      await sleep(intervalMs);
      pollCountRef.current += 1;

      const res = await fetch(`/api/insight/jobs/${jobId}`, {
        signal: abortRef.current!.signal,
      });
      const job: JobResponse = await res.json();

      switch (job.status) {
        case 'done': {
          const graphRes = await fetch(
            `/api/insight/impact?kpi_fingerprint=${kpiFingerprint}&time_range=${timeRange}`,
            { signal: abortRef.current!.signal },
          );
          const body: ImpactGraphResponse = await graphRes.json();
          setGraph(body);
          return;
        }
        case 'failed':
          throw new InsightError(500, job.error ?? '분석에 실패했습니다');
        case 'running':
          // 다음 폴 — interval은 서버 응답의 poll_after_ms 우선, 없으면 기존값
          intervalMs = job.poll_after_ms ?? intervalMs;
          break;
      }
    }
    throw new InsightError(408, '폴링 횟수 초과');
  }

  const cancel = useCallback(() => abortRef.current?.abort(), []);

  useEffect(() => {
    fetchGraph();
    return cancel;
  }, [fetchGraph, cancel]);

  // ... status, data, error를 insightStore에서 derive
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
```

**폴링 전략 요약**:

| 항목 | 값 | 근거 |
|---|---|---|
| 초기 대기 | 서버 `poll_after_ms` (보통 2000ms) | 서버가 예상 완료 시간 기반 제공 |
| 최대 폴링 횟수 | 30회 | 2s 간격 기준 ~60초 |
| 전체 타임아웃 | 5분 | 대형 그래프 빌드 최대 허용 |
| 취소 | `AbortController` | KPI 변경 / 페이지 이탈 시 즉시 취소 |
| 실패 처리 | §8.7 Fallback 전략 참조 | 폴백 그래프 또는 최근 캐시 |

### 8.4 NL2SQL Graph 탭

```
기존:  [ Chart ] [ Table ] [ SQL ]
변경:  [ Chart ] [ Table ] [ SQL ] [ Graph ]
```

**Graph 탭 내용**:
- 노드: TABLE(사각형), COLUMN(원), PREDICATE(육각형), DIMENSION(팔각형)
- 엣지: JOIN(실선 파랑), WHERE_FILTER(점선 주황), HAVING_FILTER(점선 빨강), AGGREGATE(굵은 초록), GROUP_BY(이중선 보라)
- **confidence 배지**: primary(초록) / fallback(빨강)
- **fallback 시**: "원문 SQL 보기" 버튼 우선 노출
- "Insight에서 열기" → fingerprint 기반 딥링크

### 8.5 온톨로지 데이터 프리뷰

```
  ┌─────────────────────────────────┐
  │ 실데이터 연결                    │
  │                                 │
  │ 매핑 테이블: invoices           │
  │ 레코드 수: 12,345              │
  │ 매핑 신뢰도: ████████░░ 82%    │
  │ 커버리지: 41/50 컬럼 매핑됨     │
  │ 매핑 방식: rule                 │
  │                                 │
  │ 상위 값 분포:                   │
  │  - PAID: 8,234 (66.7%)         │
  │  - PENDING: 2,456 (19.9%)      │
  │  - OVERDUE: 1,655 (13.4%)      │
  │                                 │
  │ [데이터 그래프로 열기 →]         │
  │ [Insight에서 보기 →]            │
  └─────────────────────────────────┘
```

- `GET /api/ontology/preview/coverage?datasource=...` 호출
- 신뢰도 < 50%: 경고 아이콘 + "매핑 정확도가 낮습니다" 안내

### 8.6 Fingerprint 기반 딥링크

```
/analysis/insight?fp=sha256:...&timeRange=30d&driver=drv_customer_region

Fallback 체인:
1. fingerprint로 KPI 조회 → 성공 시 사용
2. kpi_id로 조회 → 성공 시 사용
3. 둘 다 실패 → "KPI를 찾을 수 없습니다" + KPI 목록 표시
```

```typescript
// InsightPage.tsx
function InsightPage() {
  const [searchParams] = useSearchParams();
  const fingerprint = searchParams.get('fp');
  const kpiId = searchParams.get('kpi');
  const timeRange = (searchParams.get('timeRange') ?? '30d') as '7d' | '30d' | '90d';
  const driverId = searchParams.get('driver');

  const { data: resolvedKpi } = useResolveKpi(fingerprint, kpiId);

  useEffect(() => {
    if (resolvedKpi) selectKpi(resolvedKpi.id);
    if (driverId) selectNode(driverId);
  }, [resolvedKpi, driverId]);
  ...
}
```

### 8.7 에러 상태별 프론트엔드 Fallback 전략

> 모든 API 호출 실패에 대해 사용자가 "막다른 길"에 빠지지 않도록 Fallback UI를 제공한다.

| 에러 상황 | HTTP | 사용자 메시지 | Fallback UI | 자동 복구 |
|---|---|---|---|---|
| KPI 목록 로드 실패 | 5xx | "KPI 목록을 불러올 수 없습니다" | 재시도 버튼 + EmptyState | 30초 후 자동 재시도 (최대 3회) |
| Impact Graph 빌드 실패 | 202→failed | "분석에 실패했습니다" | "테이블 중심 폴백 그래프" 버튼 + "최근 캐시 보기" 버튼 | — |
| Impact Graph 타임아웃 | 202→timeout | "분석이 지연되고 있습니다" | 폴링 계속 + "최근 캐시 보기" 버튼 | 폴링 지속 (최대 5분) |
| Driver 상세 실패 | 4xx/5xx | "상세 정보를 불러올 수 없습니다" | 패널에 요약 정보만 표시 (점수 + 이름) | — |
| SQL 파싱 실패 (fallback) | 200 (mode=fallback) | confidence 배지 빨강 | "원문 SQL 보기" 버튼 우선 노출 | — |
| 온톨로지 프리뷰 실패 | 5xx | "프리뷰를 불러올 수 없습니다" | 개념 노드 기본 정보만 표시 | — |
| 딥링크 KPI 미존재 | 404 | "KPI를 찾을 수 없습니다" | KPI 목록 표시 + 검색 유도 | — |
| 네트워크 오프라인 | — | "네트워크에 연결할 수 없습니다" | 최근 캐시 데이터 표시 (있으면) | `navigator.onLine` 감지 후 자동 복구 |
| 권한 없음 | 401/403 | "접근 권한이 없습니다" | 로그인 화면 리다이렉트 (401) / 안내 메시지 (403) | — |

```typescript
// ErrorFallback.tsx — 공통 에러 Fallback 컴포넌트
interface ErrorFallbackProps {
  error: InsightError;
  onRetry?: () => void;
  fallbackContent?: React.ReactNode;
}

function ErrorFallback({ error, onRetry, fallbackContent }: ErrorFallbackProps) {
  const retryCountRef = useRef(0);
  const MAX_AUTO_RETRY = 3;

  useEffect(() => {
    // 5xx 에러 시 자동 재시도 (30초 간격, 최대 3회)
    if (error.status >= 500 && retryCountRef.current < MAX_AUTO_RETRY) {
      const timer = setTimeout(() => {
        retryCountRef.current += 1;
        onRetry?.();
      }, 30_000);
      return () => clearTimeout(timer);
    }
  }, [error, onRetry]);

  return (
    <div className="flex flex-col items-center gap-4 p-8">
      <AlertCircle className="h-12 w-12 text-destructive" />
      <p className="text-sm text-muted-foreground">{error.message}</p>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>재시도</Button>
      )}
      {fallbackContent}
    </div>
  );
}
```

---

## 9. Cytoscape 스타일 & 레이아웃 가이드

### 9.1 레이아웃 전략 (그래프 타입별, P1)

| 그래프 타입 | 레이아웃 | 이유 | 설정 |
|---|---|---|---|
| Impact Graph | `breadthfirst` (KPI 루트) | KPI 중심 방사형 계층, driver ring 느낌 | `roots: [kpiNodeId], directed: true, spacingFactor: 1.5` |
| Instance Graph | `cose-bilkent` (< 200 노드) / `breadthfirst` (≥ 200) | FK 관계 클러스터링 / 대량 시 성능 | `idealEdgeLength: 100, nodeRepulsion: 8000` |
| Query Subgraph | `dagre` (LR) | SQL 실행 흐름: TABLE → JOIN → FILTER → AGG | `rankDir: 'LR', rankSep: 60, nodeSep: 40` |

```typescript
export function getLayoutConfig(
  graphType: 'impact' | 'instance' | 'query',
  nodeCount: number,
  kpiNodeId?: string,
): cytoscape.LayoutOptions {
  switch (graphType) {
    case 'impact':
      return {
        name: 'breadthfirst',
        roots: kpiNodeId ? [kpiNodeId] : undefined,
        directed: true,
        spacingFactor: 1.5,
        padding: 30,
        animate: true,
        animationDuration: 500,
      };
    case 'instance':
      if (nodeCount >= 200) {
        return { name: 'breadthfirst', directed: false, spacingFactor: 1.2, animate: 'end' };
      }
      return {
        name: 'cose-bilkent',
        idealEdgeLength: 100,
        nodeRepulsion: 8000,
        nestingFactor: 0.1,
        gravity: 0.25,
        numIter: 2500,
        animate: 'end',
        animationDuration: 500,
      };
    case 'query':
      return {
        name: 'dagre',
        rankDir: 'LR',
        rankSep: 60,
        nodeSep: 40,
        padding: 20,
        animate: true,
        animationDuration: 300,
      };
  }
}
```

**서버 프리레이아웃 옵션** (P1):
- `GET /api/insight/impact?layout=server` → 노드에 `position: {x, y}` 포함
- 응답 `meta.layout: { name: "breadthfirst", computed_by: "server" }`
- 프론트엔드: `layout=server` 시 Cytoscape에 `preset` 레이아웃 사용

### 9.2 노드 스타일 (Impact Graph)

```typescript
const INSIGHT_NODE_STYLES = {
  KPI:       { shape: 'star',            'background-color': '#60a5fa', 'border-color': '#3b82f6', width: 60, height: 60, 'font-size': 12, 'font-weight': 'bold' },
  DRIVER:    { shape: 'round-rectangle', 'background-color': '#34d399', 'border-color': '#10b981', width: (n) => 30 + n.data('score') * 30, height: 30, 'font-size': 10 },
  DIMENSION: { shape: 'octagon',         'background-color': '#a78bfa', 'border-color': '#8b5cf6', width: 35, height: 35, 'font-size': 10 },
  TRANSFORM: { shape: 'diamond',         'background-color': '#fbbf24', 'border-color': '#f59e0b', width: 35, height: 35, 'font-size': 9 },
  PREDICATE: { shape: 'hexagon',         'background-color': '#fb923c', 'border-color': '#f97316', width: 30, height: 30, 'font-size': 9 },
};
```

### 9.3 노드 스타일 (Query Subgraph)

```typescript
const QUERY_NODE_STYLES = {
  TABLE:     { shape: 'round-rectangle', 'background-color': '#818cf8', width: 50, height: 35, 'font-size': 11 },
  COLUMN:    { shape: 'ellipse',         'background-color': '#a78bfa', width: 30, height: 30, 'font-size': 9 },
  DIMENSION: { shape: 'octagon',         'background-color': '#c084fc', width: 32, height: 32, 'font-size': 9 },
  PREDICATE: { shape: 'hexagon',         'background-color': '#fb923c', width: 28, height: 28, 'font-size': 8 },
};
```

### 9.4 엣지 스타일

```typescript
const EDGE_STYLES = {
  FK:            { 'line-style': 'solid',  'line-color': '#6b7280', width: 2 },
  JOIN:          { 'line-style': 'solid',  'line-color': '#60a5fa', width: 2 },
  WHERE_FILTER:  { 'line-style': 'dashed', 'line-color': '#f97316', width: 1.5 },
  HAVING_FILTER: { 'line-style': 'dashed', 'line-color': '#ef4444', width: 1.5 },
  AGGREGATE:     { 'line-style': 'solid',  'line-color': '#34d399', width: 3 },
  DERIVE:        { 'line-style': 'dotted', 'line-color': '#a78bfa', width: 1 },
  IMPACT:        { 'line-style': 'solid',  'line-color': '#f43f5e', width: 2.5 },
  GROUP_BY:      { 'line-style': 'double', 'line-color': '#8b5cf6', width: 2 },
};
```

### 9.5 상태 스타일

```typescript
const STATE_STYLES = {
  selected:    { 'border-width': 3, 'border-color': '#f59e0b', 'overlay-opacity': 0.1 },
  highlighted: { 'border-width': 2, 'border-color': '#ef4444', opacity: 1 },
  path_1:      { 'border-color': '#ef4444', 'line-color': '#ef4444' },   // red
  path_2:      { 'border-color': '#f97316', 'line-color': '#f97316' },   // orange
  path_3:      { 'border-color': '#eab308', 'line-color': '#eab308' },   // yellow
  dimmed:      { opacity: 0.2 },
  low_confidence: { 'border-style': 'dashed', 'border-color': '#f97316' }, // confidence < 0.5
};
```

---

## 10. 라우트/메뉴 변경 상세

### 10.1 routes.ts

```typescript
ANALYSIS: {
  OLAP: '/analysis/olap',
  NL2SQL: '/analysis/nl2sql',
  INSIGHT: '/analysis/insight',   // 신규
},
```

### 10.2 routeConfig.tsx

```typescript
const InsightPage = lazy(() =>
  import('@/pages/insight/InsightPage').then((m) => ({ default: m.InsightPage }))
);

// analysis/olap 아래에 추가
{
  path: 'analysis/insight',
  element: (
    <RoleGuard roles={['admin', 'manager', 'attorney', 'analyst', 'engineer']}>
      <SuspensePage><InsightPage /></SuspensePage>
    </RoleGuard>
  ),
},
```

### 10.3 Sidebar.tsx

```tsx
import { ..., Lightbulb } from 'lucide-react';

// 분석 섹션에 추가 (OLAP Pivot 아래)
<NavLink to={ROUTES.ANALYSIS.INSIGHT} className={navItemClass}>
  <Lightbulb className="h-4 w-4" />
  Insight
</NavLink>
```

---

## 11. 성능 설계

### 11.1 그래프 렌더링 제한

| 제한 항목 | 기본값 | 최대값 | 초과 시 처리 |
|---|---|---|---|
| Impact Graph 노드 | 50 | 120 | Top N 스코어만 + "더 보기" |
| Impact Graph 엣지 | 100 | 300 | 약한 엣지 제거 |
| Instance Graph 노드 | 200 | 500 | depth 줄임 + truncated |
| Query Subgraph 노드 | 30 | 80 | 초과 드묾 |
| 그래프 depth | 2 | 3 | 3 초과 거부 |

### 11.2 캐시 전략

| 대상 | 캐시 키 | 위치 | TTL | 무효화 |
|---|---|---|---|---|
| KPI 목록 | `insight:{org_id}:kpis:{hash}` | Redis | 5분 | 로그 신규 저장 시 |
| Impact Graph | `insight:{org_id}:impact:{fp}:{analysis_ver}` | Redis | 10분 | 점수 재계산 시 |
| Driver 랭킹 | `insight:{org_id}:drivers:{hash}` | Redis | 10분 | 점수 재계산 시 |
| Query Subgraph | (프론트 메모리) | 클라이언트 | 세션 내 | 새 쿼리 실행 시 |

### 11.3 비동기 처리

- 쿼리 로그 분석 → 백그라운드 태스크
- Driver 점수 재계산 → 5분 주기 또는 신규 로그 10건 축적 시
- Impact Graph:
  - 캐시 히트 → **200** 즉시 반환
  - 캐시 미스 + 추정 < 3초 → 동기 생성 후 **200**
  - 캐시 미스 + 추정 ≥ 3초 → **202** + `job_id` + `poll_after_ms`

```python
async def get_or_build_impact_graph(kpi_fp: str, org_id: str, params: dict):
    cache_key = build_cache_key(kpi_fp, org_id, params)

    # 1. 캐시 히트
    cached = await redis.get(cache_key)
    if cached:
        result = json.loads(cached)
        result['meta']['cache_hit'] = True
        result['meta']['cache_ttl_remaining_s'] = await redis.ttl(cache_key)
        return 200, result

    # 2. 복잡도 추정
    estimated = estimate_build_time(kpi_fp, org_id, params)
    if estimated < 3:
        result = await build_impact_graph(kpi_fp, org_id, params)
        await redis.setex(cache_key, 600, json.dumps(result))
        return 200, result

    # 3. 비동기 생성
    job_id = str(uuid.uuid4())
    await enqueue_job(job_id, kpi_fp, org_id, params)
    return 202, {"job_id": job_id, "status": "queued", "poll_after_ms": 800}
```

---

## 12. 단계별 구현 계획

### Phase 1: 기반 인프라 + Query Subgraph MVP (2~3주)

**백엔드**:

| 파일 | 신규/수정 | 설명 | 구현 상태 |
|---|---|---|---|
| `services/weaver/app/core/sql_parser.py` | 신규 | 2-stage SQL 파서 | ⚠️ `worker/parse_task.py`에 regex 파서 내장 (sqlglot 미사용) |
| `services/weaver/app/core/pii_masker.py` | 신규 | PII 마스킹 + SQL 정규화 | ⚠️ `services/sql_normalize.py`로 이동, **PII regex 누락** |
| `services/weaver/app/services/query_log_store.py` | 신규 | 로그 저장 (org_id 파티셔닝, 멱등성) | ✅ `services/insight_query_store.py`로 구현 (asyncpg) |
| `services/weaver/app/api/insight.py` | 신규 | logs, logs:ingest, query-subgraph | ✅ POST /logs, POST /logs:ingest, POST /query-subgraph 구현 |
| `services/weaver/app/main.py` | 수정 | insight 라우터 등록 | ✅ 구현 |
| `services/weaver/requirements.txt` | 수정 | sqlglot 추가 | ⚠️ sqlglot 미사용 (regex 전환) |

**프론트엔드**:

| 파일 | 신규/수정 | 설명 |
|---|---|---|
| `features/insight/types/insight.ts` | 신규 | 전체 타입 (GraphMeta, SqlParseResult 등) |
| `features/insight/api/insightApi.ts` | 신규 | API 클라이언트 |
| `features/insight/utils/graphTransformer.ts` | 신규 | API → Cytoscape 변환 + 레이아웃 선택 |
| `features/insight/components/QuerySubgraphViewer.tsx` | 신규 | 서브그래프 + confidence 배지 |
| `pages/nl2sql/components/QueryGraphPanel.tsx` | 신규 | Graph 탭 |
| `pages/nl2sql/components/ResultPanel.tsx` | 수정 | Graph 탭 추가 |

**Phase 1 테스트**:

| # | 항목 | 기준 | 방법 | 구현 상태 |
|---|---|---|---|---|
| T1-1 | SQL 파서 primary | SELECT/FROM/JOIN/WHERE/GROUP BY 정확 파싱, confidence ≥ 0.85 | pytest | ⚠️ regex 파서로 대체 (confidence 미저장) |
| T1-2 | SQL 파서 fallback | 비표준 SQL → mode=fallback, confidence ≤ 0.49 | pytest | ✅ fallback 모드 동작 |
| T1-3 | PII 마스킹 | 이메일/전화/SSN 패턴 마스킹 확인 | pytest | ❌ PII regex (EMAIL/PHONE/SSN) 미구현 |
| T1-4 | 로그 인제스트 | POST /logs 정상 저장 + 멱등성 검증 | curl + pytest | ✅ ON CONFLICT DO NOTHING 동작 |
| T1-5 | tenant_id 격리 | tenant_A 로그가 tenant_B 조회에 미노출 | pytest | ✅ RLS + SET LOCAL 동작 |
| T1-6 | query-subgraph | 유효 SQL → 200 + 올바른 노드/엣지 | curl + pytest | ✅ 구현 완료 (5노드/2엣지 확인) |
| T1-7 | Graph 탭 렌더링 | NL2SQL 실행 후 그래프 렌더링 | 브라우저 E2E | ✅ QuerySubgraphViewer (Cytoscape dagre LR) 구현 |
| T1-8 | confidence 배지 | primary/fallback 배지 정확 표시 | 브라우저 | ✅ stats bar (parse_mode + confidence%) 구현 |
| T1-9 | 입력 방어 | 100KB SQL → 413, 중첩 폭탄 → 200ms 내 컷 | pytest | ❌ MAX_SQL_LENGTH 검증 미구현 |
| T1-10 | trace_id | ingest trace_id → 응답 meta.trace_id 연계 | curl | ✅ request_id → trace_id 전파 동작 |

---

### Phase 2: Impact Graph + Insight 페이지 (4~6주)

**백엔드**:

| 파일 | 신규/수정 | 설명 | 구현 상태 |
|---|---|---|---|
| `services/weaver/app/services/query_log_analyzer.py` | 신규 | DRIVER/DIMENSION 분류 | ✅ 구현 (asyncpg, PR8 cooccur 통합 미적용) |
| `services/weaver/app/services/impact_graph_builder.py` | 신규 | 영향 그래프 (202 async) | ✅ 구현 (PR8 cooccur·node_id 통합 미적용) |
| `services/weaver/app/services/driver_scorer.py` | 신규 | 점수 계산 + breakdown 저장 | ✅ 수식 100% 일치 |
| `services/weaver/app/api/insight.py` | 수정 | kpis, impact, drivers, drivers/{id}, jobs | ⚠️ POST /impact + GET /jobs 구현, **Worker 큐 enqueue 누락** |
| `services/oracle/app/api/nl2sql.py` | 수정 | 실행 → POST /insight/logs 자동 전송 | ❌ 미구현 (Oracle→Weaver 자동 인제스트 연동) |

**프론트엔드**:

| 파일 | 신규/수정 | 설명 | 구현 상태 |
|---|---|---|---|
| `lib/routes/routes.ts` | 수정 | ANALYSIS.INSIGHT 추가 | ✅ 구현 |
| `lib/routes/routeConfig.tsx` | 수정 | InsightPage 라우트 | ✅ 구현 |
| `layouts/Sidebar.tsx` | 수정 | Insight 메뉴 | ✅ 구현 |
| `features/insight/store/useInsightStore.ts` | 신규 | Zustand | ✅ 구현 |
| `features/insight/hooks/useImpactGraph.ts` | 신규 | 202 폴링/SSE 포함 | ✅ 구현 |
| `features/insight/hooks/useDriverDetail.ts` | 신규 | Driver Evidence 조회 | ❌ 미구현 |
| `features/insight/components/ImpactGraphViewer.tsx` | 신규 | Cytoscape 렌더러 | ✅ 구현 |
| `features/insight/components/KpiSelector.tsx` | 신규 | KPI 목록 (페이지네이션) | ✅ 구현 |
| `features/insight/components/DriverRankingPanel.tsx` | 신규 | Driver 순위 | ❌ 미구현 |
| `features/insight/components/NodeDetailPanel.tsx` | 신규 | 상세 + Breakdown + Evidence | ❌ 미구현 |
| `features/insight/components/PathComparisonPanel.tsx` | 신규 | Top 3 경로 비교 | ❌ 미구현 |
| `features/insight/components/TimeRangeSelector.tsx` | 신규 | 기간 필터 | ❌ 미구현 |
| `features/insight/utils/scoreCalculator.ts` | 신규 | Breakdown 표시 | ❌ 미구현 |
| `features/insight/utils/fingerprintUtils.ts` | 신규 | fingerprint 유틸 | ❌ 미구현 |
| `pages/insight/InsightPage.tsx` | 신규 | 메인 (fingerprint 딥링크) | ✅ 구현 |
| `pages/insight/components/InsightHeader.tsx` | 신규 | 헤더 | ❌ 미구현 |
| `pages/insight/components/InsightSidebar.tsx` | 신규 | 좌측 패널 | ❌ 미구현 |

**Phase 2 테스트**:

| # | 항목 | 기준 | 방법 | 구현 상태 |
|---|---|---|---|---|
| T2-1 | DRIVER/DIMENSION 분류 | GROUP BY만 → DIMENSION, WHERE → DRIVER | pytest | ✅ 4축 스코어링 수식 100% 일치 |
| T2-2 | 카디널리티 보정 | NDV>95% → score 대폭 감점 | pytest | ⚠️ time_dim_penalty/common_dim_penalty 구현, NDV 직접 참조는 없음 |
| T2-3 | 최소 표본수 | <50건 → 감점 + UI 안내 | pytest + 브라우저 | ✅ min_distinct_queries=2 필터 동작 |
| T2-4 | KPI fingerprint 병합 | 동일 fp KPI 병합, ontology primary | pytest | ⚠️ KpiMetricMapper 모듈 완성, DB 로더·통합 미적용 |
| T2-5 | Impact API (200) | 캐시 히트 → 200 + 올바른 GraphData | curl | ❌ cache_key 저장 경로 미구현 |
| T2-6 | Impact API (202) | 캐시 미스 → 202 + job_id → 폴링 → 완료 | curl | ⚠️ 202 반환 동작, **Worker 큐 enqueue 누락으로 job 미실행** |
| T2-7 | Driver 상세 + Evidence | breakdown + top_queries + paths 반환 | curl | ✅ evidence_samples + paths 구현 |
| T2-8 | Insight 렌더링 | 3-패널 레이아웃 정상, 콘솔 에러 없음 | 브라우저 E2E | — 프론트엔드 범위 |
| T2-9 | 202 UX | 로딩 UI + 완료 시 자동 렌더 + 실패 시 폴백 | 브라우저 E2E | — 프론트엔드 범위 |
| T2-10 | Evidence 패널 | Top Queries 항상 노출, 클릭 → subgraph 점프 | 브라우저 E2E | — 프론트엔드 범위 |
| T2-11 | 경로 비교 | Top 3 토글 on/off, dimmed/highlighted | 브라우저 E2E | — 프론트엔드 범위 |
| T2-12 | Truncation UX | truncated → "더 보기" 버튼 동작 | 브라우저 E2E | — 프론트엔드 범위 |
| T2-13 | 상태 바 | mode/queries/cache/trace 정보 표시 | 브라우저 | — 프론트엔드 범위 |

---

### Phase 3: 연결 + 온톨로지 + 미니차트 (2~3주)

**작업**:

| 파일 | 설명 |
|---|---|
| `pages/nl2sql/components/QueryGraphPanel.tsx` | Insight fingerprint 딥링크 |
| `pages/ontology/components/NodeDetail.tsx` | 실데이터 + 신뢰도/커버리지 |
| `features/ontology/hooks/useNodeDataPreview.ts` | coverage API 호출 |
| `services/weaver/app/api/ontology_preview.py` | coverage API |
| `features/insight/hooks/useKpiTimeseries.ts` | KPI 시계열 훅 |
| `features/insight/components/KpiMiniChart.tsx` | Driver별 미니차트 |
| `pages/insight/InsightPage.tsx` | fingerprint 딥링크 fallback |

**Phase 3 테스트**:

| # | 항목 | 기준 | 방법 |
|---|---|---|---|
| T3-1 | fingerprint 딥링크 | fp 파라미터 → KPI 정확 해석 + fallback | 브라우저 E2E |
| T3-2 | 온톨로지 프리뷰 | 매핑 테이블 + 값 분포 + 신뢰도/커버리지 | 브라우저 E2E |
| T3-3 | coverage API | 테이블별 coverage/confidence 반환 | curl |
| T3-4 | KPI 미니차트 | Driver 선택 → timeseries 미니차트 표시 | 브라우저 E2E |
| T3-5 | 전체 플로우 | 온톨로지 → NL2SQL → Insight 3단계 끊김 없음 | 수동 시나리오 |

---

## 13. 위험 요소 및 대응

| 위험 | 영향 | 대응 |
|---|---|---|
| 쿼리 로그 부족 | 초기 Insight 가치 하락 | 최소 표본수(50건) 체크 + UI 안내. Phase 1 Query Subgraph 즉시 가치 제공 |
| 그래프 노드 폭발 | 렌더링 성능 저하 | depth 3 제한, 노드 120/500 제한, "더 보기" 점진 로딩 |
| SQL 파싱 실패 | Subgraph 품질 저하 | 2-stage fallback + confidence 표시 + "원문 SQL 보기" |
| KPI 중복 | 목록 혼란 | fingerprint 병합, ontology primary 표시 |
| Impact Graph 생성 지연 | UX 저하 | 202 + 폴링/SSE + 실패 시 폴백 그래프 |
| 테넌트 데이터 유출 | 보안 사고 | org_id 서버 주입, RLS, Neo4j org_id 조건 강제 |
| PK/UUID 오탐 | Driver 품질 저하 | 카디널리티 보정 + 후보 필터링 |
| PII 노출 | 규정 위반 | pii_masker + normalized_sql + 감사 |
| 악성 SQL 입력 | 서버 과부하 | 100KB 제한 + 200ms 파싱 타임아웃 |

---

## 14. 전체 테스트 체크리스트 (Final Gate)

| # | 카테고리 | 테스트 항목 | 통과 기준 |
|---|---|---|---|
| FG-1 | 라우팅 | `/analysis/insight` 접속 | 페이지 정상 렌더링, 콘솔 에러 없음 |
| FG-2 | 사이드바 | Insight 메뉴 표시 + 클릭 | 분석 섹션 Lightbulb 아이콘 |
| FG-3 | KPI 로드 | 진입 시 KPI 목록 | 최소 1개 표시 또는 빈 상태 안내 |
| FG-4 | Impact Graph | KPI 선택 → 그래프 | Cytoscape 노드/엣지 1초 이내 렌더링 |
| FG-5 | Driver 클릭 | 노드 → 우측 패널 | Breakdown + Evidence + 값 분포 |
| FG-6 | 경로 하이라이트 | Driver → KPI 경로 | dimmed/highlighted 상태 전환 |
| FG-7 | 기간 필터 | 7d/30d/90d 전환 | 데이터 갱신 + 로딩 |
| FG-8 | NL2SQL Graph | 쿼리 실행 후 Graph 탭 | TABLE/COLUMN/PREDICATE 노드 구분 |
| FG-9 | NL2SQL → Insight | "Insight에서 열기" | fingerprint 딥링크 이동 |
| FG-10 | 온톨로지 프리뷰 | 개념 노드 클릭 | 매핑 + 값 분포 + 신뢰도/커버리지 |
| FG-11 | 빈 상태 | 데이터 없을 때 | EmptyState 표시 |
| FG-12 | 에러 처리 | API 실패 시 | ErrorState + toast |
| FG-13 | 성능 | 300 노드 이하 | 렌더링 1초, 인터랙션 16ms |
| FG-14 | 반응형 | 1024px 이상 | 3-패널 정상, 미만 패널 접힘 |
| FG-15 | 다크 테마 | 전체 UI | bg-neutral-950 기반 가독성 |
| **FG-16** | **보안: org 격리** | **A/B 교차 조회** | org_A 토큰으로 org_B 데이터 0건. seed 100개(A)+100개(B) 삽입 후 교차 검증 |
| **FG-17** | **보안: RoleGuard 우회** | **라우트 직접, 파라미터 변조, org_id 주입** | 401/403 + 감사로그 기록 |
| **FG-18** | **보안: 입력 방어** | **100K SQL, 중첩 괄호 폭탄, 비정상 유니코드** | 413 또는 400, 처리시간 200ms 내 |
| **FG-19** | **보안: PII 마스킹** | **normalized_sql + 노드 label** | 이메일/전화/SSN 미노출 |
| **FG-20** | **보안: 멱등성** | **동일 key 2회 전송** | deduped=1, 데이터 1건 |
| **FG-21** | **관측: trace_id** | **ingest → 분석 → 응답** | meta.trace_id 또는 X-Trace-Id 헤더 반환 |
| **FG-22** | **비동기: 202 완료** | **캐시 미스 → 202 → 폴링 → done** | 자동 렌더링 |
| **FG-23** | **비동기: Job 실패** | **분석 실패** | 에러 메시지 + 폴백 그래프 또는 "최근 캐시" 버튼 |
| **FG-24** | **파서: confidence** | **primary/fallback** | 배지 정확 표시, fallback 시 "원문 SQL" 버튼 |
| **FG-25** | **관측: meta.explain** | **상태 바** | 쿼리 수, 기간, formula, mode 표시 |
| **FG-26** | **딥링크: fingerprint** | **fp 파라미터** | KPI 정확 해석 + fallback 체인 |
| **FG-27** | **UX: Evidence** | **NodeDetailPanel** | Top Queries 항상 노출 + 클릭→subgraph 점프 |
| **FG-28** | **UX: 경로 비교** | **Top 3 토글** | 3경로 동시 하이라이트, 개별 on/off |

---

## 15. 부록

### 15.1 구현 우선순위 타임라인

```
Week 1-2:  [Phase 1A] 2-stage SQL 파서 + PII 마스킹 + /api/insight/logs 인제스트
Week 2-3:  [Phase 1B] NL2SQL Graph 탭 + Cytoscape + confidence 배지
Week 4-5:  [Phase 2A] 로그 분석 + DRIVER/DIMENSION 분류 + Driver 점수 (카디널리티 보정)
Week 5-7:  [Phase 2B] Insight 페이지 + Impact Graph (202 async) + fingerprint 병합
Week 7-8:  [Phase 2C] Driver 상세 (Evidence + Breakdown) + 기간 필터 + 경로 비교
Week 8-9:  [Phase 3A] NL2SQL ↔ Insight fingerprint 딥링크 + KPI 미니차트
Week 9-10: [Phase 3B] 온톨로지 프리뷰 (coverage/confidence) + 전체 연결
Week 10:   [Final]   통합 테스트 + 보안 (FG-16~21) + 성능 최적화
```

### 15.2 용어 정리

| 용어 | 정의 |
|---|---|
| **KPI** | 핵심 성과 지표. 집계 함수(SUM/AVG/COUNT 등)가 적용된 컬럼 |
| **Driver** | KPI에 영향을 주는 입력 변수. WHERE/JOIN에 등장하는 컬럼 |
| **Dimension** | 데이터를 분류하는 축. GROUP BY에 등장하는 컬럼 |
| **Transform** | KPI 계산 중간 단계 (조인, 집계, 변환) |
| **Predicate** | WHERE/HAVING 조건식 (예: `status = 'PAID'`) |
| **Impact Path** | Driver에서 KPI까지의 영향 경로 |
| **Fingerprint** | KPI 고유 식별자. `sha256(datasource + table + column + aggregate + filters_signature)` |
| **confidence** | 파싱/매핑 신뢰도 (0~1, 연속값). primary ≥ 0.85, fallback ≤ 0.49 |
| **mode** | SQL 파서 모드. `primary` (AST) / `fallback` (regex) |
| **effective_org_id** | 서버가 access_token에서 결정한 조직 ID. 바디에서 수신하지 않음 |
| **Evidence** | Driver 점수의 근거. top_queries + paths |

### 15.3 의존성

| 패키지 | 버전 | 용도 |
|---|---|---|
| `sqlglot` (백엔드) | >=25.0 | 2-stage SQL 파싱 |
| Cytoscape.js (프론트) | 기설치 | 그래프 렌더링 |
| cytoscape-dagre (프론트) | 기설치 | dagre 레이아웃 |
| cytoscape-cose-bilkent (프론트) | 기설치 | cose-bilkent 레이아웃 |

### 15.4 구현 갭 분석 (2026-02-26)

> 설계서 v3.1 기준으로 실제 구현 코드를 대조한 결과.
> 상세 PR별 분석은 [PR 구현 가이드](./insight-view-pr-implementation.md)의 "구현 갭 분석 요약" 참조.

**전체 요약**:

| PR | 일치도 | 핵심 갭 |
|---|---|---|
| PR1 (DB) | 95% | PARTITION 미사용 (의도적), 테이블 구조 설계 이상 |
| PR2 (공통) | 98% | 파일 통합 (의도적) |
| PR3 (Auth) | 100% | 완전 일치 |
| PR4 (Ingest) | 70% | **PII regex 누락**, MAX_SQL_LENGTH 미검증, hash 절단 미적용 |
| PR5 (Redis Job) | 65% | **heartbeat 미구현**, TTL 분리 없음, **Worker 큐 enqueue 누락** |
| PR6 (Workers) | 75% | sqlglot→regex (의도적), heartbeat 미호출, cache 저장 누락 |
| PR7 (Analysis) | 90% | scorer 수식 100% 일치, DB 접근 asyncpg 전환 (의도적) |
| PR8 (Accuracy) | 40% | 개별 모듈 완성, **analyzer·graph_builder 통합 미적용** |

**P0 수정 필요 (기능 동작 불가)**:

- **[P0-1]** Worker 큐 enqueue 연결 — job 생성 후 실행 경로 없음
- **[P0-2]** PII regex (EMAIL/PHONE/SSN) 추가 — 보안 필수

**P1 수정 필요 (핵심 기능 미완)**:

- **[P1-1]** Impact 결과 Redis cache 저장 — 캐시 히트 200 경로 미동작
- **[P1-2]** PR8 cooccur + node_id → analyzer·graph_builder 통합 — 정확도 개선 핵심

**P2 수정 필요 (안정성·모니터링)**:

- **[P2-1]** heartbeat 구현 + impact_task 호출
- **[P2-2]** parse_mode/confidence DB 저장
- **[P2-3]** load_kpi_definitions DB 로더
- **[P2-4]** MAX_SQL_LENGTH 검증, hash 절단

---

### 15.5 변경 이력

| 버전 | 날짜 | 설명 |
|---|---|---|
| v1.0 | 2026-02-26 | 초안 |
| v2.0 | 2026-02-26 | P0~P2 1차 피드백 반영 |
| v3.0 | 2026-02-26 | P0~P2 전면 보강: org_id 서버 주입, 리치 LogItem, 2-stage 파서 confidence/mode, Driver 후보 필터링/카디널리티/표본수, Score Breakdown, FG-16~28 보안/관측/UX 게이트, 202 Job+SSE, breadthfirst 레이아웃, Evidence UX 고정, KPI timeseries, coverage API, PII 마스킹, trace_id 전파 |
| v3.1 | 2026-02-26 | P0~P2 갭 보강: §1.4 피드백 추적표, §2.4 Oracle→Weaver 자동 인제스트 연동, §3.8 DDL(인덱스/RLS/파티션), §3.9 Zustand 스토어 인터페이스, §4.10 coverage/confidence 산출 공식, §4.11 API 에러 응답 표준, §7.6 운영 모니터링 메트릭(Prometheus/RUM), §8.3.1 useImpactGraph 폴링 훅 pseudocode, §8.7 에러 Fallback 전략 매트릭스 |
| v3.1.1 | 2026-02-26 | 구현 갭 분석: §12 Phase 1/2 테이블에 구현 상태 컬럼 추가, §15.4 PR1~PR8 갭 분석 요약 (P0~P2 우선순위 분류) |
