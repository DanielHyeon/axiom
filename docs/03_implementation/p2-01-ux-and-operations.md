# P2-01: UX/Operations 개선 구현 계획

> **범위**: #16 ERD 시각화, #17 피드백 대시보드, #18 HIL(Human-in-the-Loop), #19 Driver 계층, #20 LLM 리랭킹 + PRF
> **작성일**: 2026-03-20
> **예상 공수**: 총 8~10 스프린트 (각 스프린트 5일)

---

## 1. 현재 상태 분석

### 1.1 ERD 시각화 (#16)

| 항목 | 현재 상태 |
|------|----------|
| **KAIR 소스** | `ERDiagram.vue` (236줄) + `MermaidERView.vue` (679줄) — Mermaid.js 기반 ER 다이어그램. 테이블 검색, FK 기반 관계 자동 추출, SVG 다운로드, 컬럼 제한 표시(8개), PK/FK 마커, 통계 패널 |
| **Axiom 대상** | `features/datasource/` — SchemaExplorer.tsx(스키마 탐색 UI) 존재. ERD 시각화 컴포넌트 **없음** |
| **API** | Weaver `GET /api/datasources/{name}/schemas`, `GET .../tables` 존재. Oracle `GET /text2sql/meta/tables`, `GET .../columns` 존재. ERD 전용 API 없음 |
| **라우트** | `ROUTES.DATA.DATASOURCES = '/data/datasources'` — ERD 탭 추가 가능 |
| **타입** | `TableMeta`, `ColumnMeta` in `nl2sql.ts` — ERD 렌더링에 충분한 메타 필드 보유 |

### 1.2 피드백 대시보드 (#17)

| 항목 | 현재 상태 |
|------|----------|
| **Oracle 피드백 API** | `POST /feedback` — rating(positive/negative/partial), comment, corrected_sql 저장. **통계 조회 API 없음** |
| **DB 스키마** | `oracle.query_feedback` 테이블: id, query_id, tenant_id, user_id, rating, corrected_sql, comment, created_at |
| **query_history** | `oracle.query_history` 테이블: status, execution_time_ms, datasource_id, tables_used, created_at |
| **프론트엔드** | `QueryHistoryPanel.tsx` — 이력 목록만 표시. 피드백 통계 대시보드 **없음** |
| **라우트** | `ROUTES.SETTINGS_LOGS = '/settings/logs'` — 하위 탭 또는 별도 라우트 추가 필요 |

### 1.3 Human-in-the-Loop (#18)

| 항목 | 현재 상태 |
|------|----------|
| **KAIR 소스** | `ReactInput.vue` (375줄) — `waitingForUser` 상태 토글, 에이전트 질문 표시, 사용자 응답 전송, 고급 설정(maxToolCalls, maxSqlSeconds) |
| **KAIR 백엔드** | `controller.py` — `ControllerResult.status = "ask_user"`, `ControllerTriageResult.decision = "ask_user"`, `session_state` 토큰으로 세션 유지, `user_response` 파라미터로 사용자 응답 수신 |
| **KAIR 라우터** | `react.py` — `ReactRequest.user_response`, `ReactRequest.session_state` 필드. NDJSON 스트림에서 `status: "needs_user_input"` 이벤트 발행 |
| **Axiom 백엔드** | `nl2sql_pipeline.py` — 단순 1-shot 파이프라인. ReAct 루프 **없음**, ask_user **없음** |
| **Axiom 프론트엔드** | `Nl2SqlPage.tsx` — `postReactStream()` NDJSON 스트림 소비. `ReactStreamStep` 타입. HIL 전환 UI **없음** |
| **Axiom API 타입** | `ReactRequest` in `text2sql.py` — `session_state`, `user_response` 필드 **없음** |

### 1.4 Driver 계층 확장 (#19)

| 항목 | 현재 상태 |
|------|----------|
| **KAIR 모델** | `ontology.py` — `OntologyLayerType` Enum: KPI, Measure, **Driver**, Process, Resource (5계층) |
| **KAIR 관계** | `OntologyRelationType` — CAUSES, INFLUENCES, MEASURED_AS, EXECUTES, PRODUCES, USED_WHEN 등 16개 관계 타입. Driver 전용: CAUSES (Driver->Measure->KPI), INFLUENCES (Driver->Process) |
| **Axiom 온톨로지 타입** | `ontology.ts` — `OntologyLayer = 'kpi' | 'measure' | 'process' | 'resource'` (**4계층, Driver 없음**) |
| **Axiom 관계 타입** | `OntologyRelation = '달성' | '측정' | '참여' | '매핑'` (4개, Driver 관련 CAUSES/INFLUENCES **없음**) |
| **Synapse 서비스** | `ontology_service.py` — `layer` 필드를 normalize하지만 고정 enum 없음. 기본값 `"resource"`. Neo4j 라벨은 동적(`layer.capitalize()`) |
| **프론트 필터** | `OntologyFilters.layers: Set<OntologyLayer>` — Driver 레이어 필터 **불가** |

### 1.5 LLM 리랭킹 + PRF (#20)

| 항목 | 현재 상태 |
|------|----------|
| **KAIR 구현** | `table_search_flow.py` — 다축 벡터 검색(question/HyDE/regex/intent) + PRF 1x (top-A 테이블 텍스트 + 질문 결합 -> 재임베딩 -> 재검색) + LLM rerank (`get_table_rerank_generator()`) + sibling/FK expansion |
| **KAIR PRF 매개변수** | `table_prf_top_a=20`, `table_prf_top_k=300`, `table_prf_weight=0.8`, `table_prf_max_chars=2500` |
| **KAIR 리랭킹** | `TableRerankCandidate` 모델, `rerank_fetch_k=60`, LLM 기반 인덱스 재정렬 |
| **Axiom Oracle** | `nl2sql_pipeline.py` — 단순 LLM SQL 생성. 벡터 검색 **없음**, PRF **없음**, LLM 리랭킹 **없음** |
| **Axiom Synapse** | Neo4j 벡터 인덱스 + `graph_search.py` 존재하나, 테이블 레벨 PRF 미구현 |
| **의존성** | HyDE, 임베딩 클라이언트, Neo4j 벡터 인덱스가 선행 필요 |

---

## 2. 구현 항목별 상세 계획

---

### #16 ERD 시각화 (Mermaid 기반)

#### 2.16.1 아키텍처

```
[DatasourcesPage]
   |-- [ERD 탭]
   |      |-- <ERDiagramPanel>
   |             |-- <ERDToolbar> (검색, 필터, 테이블 수 제한, SVG 다운로드)
   |             |-- <MermaidERDRenderer> (mermaid.js 렌더링 엔진)
   |             |-- <ERDStatsFooter> (테이블/관계/컬럼 카운트)
   |-- [기존 탭들]
```

#### 2.16.2 신규 파일

| 파일 경로 | 용도 | LOC 예상 |
|-----------|------|----------|
| `features/datasource/components/ERDiagramPanel.tsx` | ERD 메인 컨테이너 (상태 관리, 데이터 로딩) | ~250 |
| `features/datasource/components/ERDToolbar.tsx` | 검색, 필터, 다운로드 컨트롤 | ~120 |
| `features/datasource/components/MermaidERDRenderer.tsx` | Mermaid.js 렌더링 + SVG 출력 | ~200 |
| `features/datasource/hooks/useERDData.ts` | 테이블/컬럼 메타데이터 패칭 + 캐싱 | ~100 |
| `features/datasource/utils/mermaidCodeGen.ts` | Mermaid ER 코드 생성 순수 함수 | ~150 |
| `features/datasource/types/erd.ts` | ERD 관련 타입 정의 | ~40 |

#### 2.16.3 구현 단계

**Step 16-1: 의존성 설치 + 타입 정의** (복잡도: Low)

- **무엇**: mermaid.js 패키지 설치, ERD 타입 정의
- **위치**: `canvas/package.json`, `features/datasource/types/erd.ts`
- **방법**:
  ```bash
  cd canvas && pnpm add mermaid@^11
  ```
- **타입 정의**:
  ```typescript
  // features/datasource/types/erd.ts
  export interface ERDTableInfo {
    name: string;
    schema: string;
    description?: string;
    columns: ERDColumnInfo[];
  }

  export interface ERDColumnInfo {
    name: string;
    dataType: string;
    isPrimaryKey: boolean;
    isForeignKey: boolean;
    nullable: boolean;
    referencedTable?: string;
  }

  export interface ERDStats {
    tables: number;
    relationships: number;
    columns: number;
  }

  export interface ERDFilter {
    searchQuery: string;
    showConnectedOnly: boolean;
    maxTables: number;
  }
  ```
- **검증**: `pnpm tsc --noEmit` 통과

**Step 16-2: Mermaid 코드 생성 유틸리티** (복잡도: Medium)

- **무엇**: 테이블 + 컬럼 메타데이터에서 Mermaid `erDiagram` 코드 생성
- **위치**: `features/datasource/utils/mermaidCodeGen.ts`
- **방법**: KAIR `MermaidERView.vue`의 `generateMermaidER()` 로직을 순수 함수로 포팅
  - `_id` 접미사 기반 FK 관계 추론 (KAIR 동일)
  - 테이블명 정규화 (`/[^a-zA-Z0-9_]/g` -> `_`)
  - 컬럼 타입 매핑 (int/float/datetime/boolean/text/string)
  - PK/FK 마커 추가
  - 최대 8개 컬럼 표시 (나머지 `_more_N_cols`)
- **핵심 함수**:
  ```typescript
  export function generateMermaidERCode(
    tables: ERDTableInfo[],
    options?: { maxColumnsPerTable?: number }
  ): { code: string; stats: ERDStats }

  export function getConnectedTables(
    seedTables: ERDTableInfo[],
    allTables: ERDTableInfo[]
  ): ERDTableInfo[]
  ```
- **검증**: 단위 테스트 — 빈 테이블, 단일 테이블, FK 관계 있는 다중 테이블

**Step 16-3: ERD 데이터 훅** (복잡도: Medium)

- **무엇**: TanStack Query 기반 테이블/컬럼 메타데이터 패칭 훅
- **위치**: `features/datasource/hooks/useERDData.ts`
- **방법**:
  - Oracle `getTables()` + `getTableColumns()` API 호출 (이미 `oracleNl2sqlApi.ts`에 구현됨)
  - 데이터소스 선택 시 테이블 목록 로드 → 각 테이블 컬럼 병렬 로드
  - `ERDTableInfo[]`로 변환
  ```typescript
  export function useERDData(datasourceId: string | null) {
    // useQuery: 테이블 목록
    // useQueries: 각 테이블 컬럼 (병렬)
    // 반환: { tables, isLoading, error, refetch }
  }
  ```
- **의존**: Step 16-1 타입
- **검증**: 데이터소스 선택 후 테이블/컬럼 로드 확인

**Step 16-4: MermaidERDRenderer 컴포넌트** (복잡도: Medium)

- **무엇**: Mermaid.js 렌더링 전용 컴포넌트
- **위치**: `features/datasource/components/MermaidERDRenderer.tsx`
- **방법**:
  - `useRef<HTMLDivElement>` + `useEffect`로 Mermaid 초기화/렌더링
  - `mermaid.initialize({ startOnLoad: false, theme: 'default', er: { layoutDirection: 'TB' } })`
  - 라이트 테마 대응 (`themeVariables` 설정)
  - 에러 시 `<pre>` fallback
  - 빈 데이터 시 빈 상태 UI
  - SVG 렌더링 후 `diagramEl.innerHTML = svg`
- **Props**:
  ```typescript
  interface MermaidERDRendererProps {
    mermaidCode: string;
    isRendering: boolean;
    onRendered?: (hasDiagram: boolean) => void;
  }
  ```
- **검증**: 코드 전달 시 SVG 렌더링 확인

**Step 16-5: ERD 툴바 + 메인 패널 + 페이지 통합** (복잡도: Medium)

- **무엇**: 검색/필터 툴바 + 메인 ERDiagramPanel 조립 + DatasourcesPage 탭 추가
- **위치**: `features/datasource/components/ERDToolbar.tsx`, `features/datasource/components/ERDiagramPanel.tsx`
- **방법**:
  - ERDToolbar: 검색 input, "연결된 테이블만" 체크박스, 최대 테이블 수 select, SVG 다운로드 버튼, 새로고침 버튼
  - ERDiagramPanel: 상태 조합 (filter + data + mermaidCode 생성 + 렌더러 연결)
  - SVG 다운로드: `XMLSerializer().serializeToString(svg)` -> Blob -> `<a>` download
  - DatasourcesPage에 탭 추가: `[목록 | 스키마 탐색 | ERD]`
- **검증**: 데이터소스 선택 → ERD 탭 → 다이어그램 표시 → 검색 → SVG 다운로드

**Step 16-6: 고급 기능 (스키마 필터, 줌/팬)** (복잡도: Low)

- **무엇**: 스키마별 필터, 다이어그램 줌/팬 지원
- **방법**:
  - 스키마 선택 드롭다운 (Weaver `getDatasourceSchemas()` 활용)
  - CSS `overflow: auto` + `transform: scale()` 기반 줌 (또는 panzoom 라이브러리)
  - debounce 300ms 검색
- **검증**: 대규모 스키마(50+ 테이블)에서 렌더링 성능 확인

---

### #17 피드백 통계 대시보드

#### 2.17.1 아키텍처

```
[SettingsPage > Logs 탭]
   또는
[ROUTES.SETTINGS_FEEDBACK = '/settings/feedback']  (신규 라우트)
   |
   |-- <FeedbackDashboard>
          |-- <FeedbackSummaryCards> (총 쿼리, 정답률, 실패율, 평균 응답시간)
          |-- <FeedbackTrendChart> (일별/주별 positive/negative/partial 추이)
          |-- <FailurePatternTable> (실패 패턴 분석 — 에러 코드별 빈도)
          |-- <DatasourceBreakdown> (데이터소스별 피드백 분포)
          |-- <TopQueriesTable> (가장 많이 실패한 질문 TOP-N)
```

#### 2.17.2 신규 파일

| 파일 경로 | 용도 | LOC 예상 |
|-----------|------|----------|
| `services/oracle/app/api/feedback_stats.py` | 피드백 통계 API 엔드포인트 (4개) | ~150 |
| `services/oracle/app/core/feedback_analytics.py` | 통계 집계 쿼리 모듈 | ~200 |
| `features/feedback/api/feedbackApi.ts` | 피드백 통계 API 클라이언트 | ~80 |
| `features/feedback/hooks/useFeedbackStats.ts` | TanStack Query 훅 | ~60 |
| `features/feedback/components/FeedbackDashboard.tsx` | 대시보드 메인 컨테이너 | ~180 |
| `features/feedback/components/FeedbackSummaryCards.tsx` | KPI 카드 (4개) | ~100 |
| `features/feedback/components/FeedbackTrendChart.tsx` | 시계열 차트 (recharts) | ~150 |
| `features/feedback/components/FailurePatternTable.tsx` | 실패 패턴 테이블 | ~120 |
| `features/feedback/components/DatasourceBreakdown.tsx` | 데이터소스별 분포 차트 | ~100 |
| `features/feedback/types/feedbackStats.ts` | 통계 타입 정의 | ~50 |
| `pages/settings/FeedbackStatsPage.tsx` | 페이지 컴포넌트 | ~40 |

#### 2.17.3 구현 단계

**Step 17-1: 백엔드 통계 집계 모듈** (복잡도: Medium)

- **무엇**: PostgreSQL 집계 쿼리 모듈 작성
- **위치**: `services/oracle/app/core/feedback_analytics.py`
- **방법**:
  ```python
  class FeedbackAnalytics:
      def __init__(self, database_url: str | None = None): ...

      async def get_summary(self, tenant_id: UUID, date_from: str, date_to: str) -> dict:
          """총 쿼리 수, 피드백 수, positive/negative/partial 비율, 평균 응답시간"""
          # SQL: JOIN query_history + query_feedback
          # GROUP BY rating -> 비율 계산

      async def get_trend(self, tenant_id: UUID, date_from: str, date_to: str, granularity: str) -> list[dict]:
          """일별/주별 피드백 추이"""
          # SQL: DATE_TRUNC(granularity, created_at), rating별 COUNT

      async def get_failure_patterns(self, tenant_id: UUID, date_from: str, date_to: str, limit: int) -> list[dict]:
          """실패 쿼리 패턴 분석 — status='error' 그룹핑"""
          # SQL: error_message 패턴별 COUNT, 최근 발생일

      async def get_datasource_breakdown(self, tenant_id: UUID, date_from: str, date_to: str) -> list[dict]:
          """데이터소스별 쿼리 수 + 피드백 분포"""
          # SQL: GROUP BY datasource_id, rating

      async def get_top_failed_queries(self, tenant_id: UUID, date_from: str, date_to: str, limit: int) -> list[dict]:
          """가장 많이 negative 피드백 받은 질문 TOP-N"""
          # SQL: question별 negative 카운트, 최근 SQL 예시
  ```
- **검증**: 단위 테스트 — 빈 데이터, 정상 데이터, 날짜 범위 필터링

**Step 17-2: 백엔드 통계 API 엔드포인트** (복잡도: Low)

- **무엇**: FastAPI 라우터 추가
- **위치**: `services/oracle/app/api/feedback_stats.py`
- **엔드포인트**:
  ```
  GET /feedback/stats/summary?date_from=...&date_to=...
  GET /feedback/stats/trend?date_from=...&date_to=...&granularity=day|week
  GET /feedback/stats/failures?date_from=...&date_to=...&limit=20
  GET /feedback/stats/by-datasource?date_from=...&date_to=...
  GET /feedback/stats/top-failed?date_from=...&date_to=...&limit=10
  ```
- **인증**: `@router.get(...)` + `Depends(get_current_user)` + role check (admin, manager)
- **`main.py` 등록**: `app.include_router(feedback_stats.router)` 추가
- **검증**: curl/httpie로 엔드포인트 호출

**Step 17-3: 프론트엔드 타입 + API + 훅** (복잡도: Low)

- **무엇**: 타입 정의, API 클라이언트, TanStack Query 훅
- **위치**: `features/feedback/types/`, `features/feedback/api/`, `features/feedback/hooks/`
- **타입**:
  ```typescript
  // feedbackStats.ts
  export interface FeedbackSummary {
    total_queries: number;
    total_feedbacks: number;
    positive_rate: number;
    negative_rate: number;
    partial_rate: number;
    avg_execution_time_ms: number;
    period: { from: string; to: string };
  }

  export interface FeedbackTrendPoint {
    date: string;
    positive: number;
    negative: number;
    partial: number;
    total: number;
  }

  export interface FailurePattern {
    pattern: string;
    count: number;
    last_occurred: string;
    example_question?: string;
  }

  export interface DatasourceStats {
    datasource_id: string;
    total_queries: number;
    positive: number;
    negative: number;
    partial: number;
  }
  ```
- **검증**: 타입 컴파일 통과

**Step 17-4: 대시보드 UI 컴포넌트** (복잡도: High)

- **무엇**: 5개 시각화 컴포넌트 + 메인 대시보드
- **위치**: `features/feedback/components/`
- **방법**:
  - `FeedbackSummaryCards`: 4개 KPI 카드 (총 쿼리, 정답률 %, 실패율 %, 평균 응답시간 ms). Shadcn Card 컴포넌트 사용
  - `FeedbackTrendChart`: recharts `AreaChart` 사용. X축=날짜, Y축=건수, 3개 시리즈(positive/negative/partial)
  - `FailurePatternTable`: 정렬 가능한 테이블. 패턴명, 빈도, 최근 발생일
  - `DatasourceBreakdown`: recharts `BarChart` — 데이터소스별 스택 바
  - `FeedbackDashboard`: DateRangePicker(기간 선택) + 그리드 레이아웃으로 위 컴포넌트 조합
- **의존**: recharts (이미 설치 확인 필요, 아니면 `pnpm add recharts`)
- **검증**: 대시보드 페이지 접근, 기간 변경 시 차트 업데이트

**Step 17-5: 라우트 등록 + 사이드바 메뉴** (복잡도: Low)

- **무엇**: 피드백 대시보드 라우트 추가
- **위치**: `lib/routes/routes.ts`, `lib/routes/routeConfig.tsx`, 사이드바 컴포넌트
- **방법**:
  ```typescript
  // routes.ts에 추가
  SETTINGS_FEEDBACK: '/settings/feedback',
  ```
  - `routeConfig.tsx`에 lazy import 추가
  - 사이드바 Settings 하위에 "피드백 통계" 메뉴 추가
- **검증**: `/settings/feedback` 접근 가능 확인

---

### #18 Human-in-the-Loop (Vue -> React 변환)

#### 2.18.1 아키텍처

```
KAIR 플로우:
  사용자 질문 → ReAct 루프 → controller → triage → ask_user
                                                       ↓
  프론트엔드 ← NDJSON status:"needs_user_input" ← 세션 토큰
       ↓
  [ReactInput: waitingForUser=true, questionToUser=에이전트 질문]
       ↓
  사용자 답변 → POST /react (user_response + session_state) → ReAct 루프 재개

Axiom 포팅 플로우:
  사용자 질문 → Oracle ReAct 스트림 → 에이전트 루프 → ask_user 판단
                                                          ↓
  프론트엔드 ← NDJSON event:"needs_user_input" ← session_state
       ↓
  [HumanInTheLoopInput: mode=followup, agentQuestion=...]
       ↓
  사용자 답변 → postReactStream(user_response, session_state) → 루프 재개
```

#### 2.18.2 백엔드 변경 (Oracle)

**Step 18-1: ReactRequest에 HIL 필드 추가** (복잡도: Low)

- **무엇**: `user_response`, `session_state` 필드를 ReactRequest에 추가
- **위치**: `services/oracle/app/api/text2sql.py`
- **변경**:
  ```python
  class ReactRequest(BaseModel):
      question: str = Field(..., min_length=2, max_length=2000)
      datasource_id: str
      case_id: str | None = None
      options: ReactOptions = Field(default_factory=ReactOptions)
      # HIL 필드 추가
      session_state: str | None = Field(default=None, description="이전 세션 상태 토큰 (ask_user 이후 재개용)")
      user_response: str | None = Field(default=None, description="ask_user에 대한 사용자 응답")
  ```
- **검증**: 스키마 변경 후 기존 요청 호환 확인 (Optional이므로 backward compatible)

**Step 18-2: NL2SQL 파이프라인에 Triage + ask_user 로직 추가** (복잡도: High)

- **무엇**: KAIR `controller.py`의 ask_user 판단 로직을 Oracle 파이프라인에 통합
- **위치**: `services/oracle/app/pipelines/nl2sql_pipeline.py`
- **방법**:
  - `NL2SQLPipeline`에 `ControllerResult` 데이터클래스 추가:
    ```python
    @dataclass
    class ControllerResult:
        status: str  # "submit_sql" | "ask_user" | "error"
        final_sql: str = ""
        question_to_user: str = ""
        session_state: str | None = None
    ```
  - 생성된 SQL 품질 검증 실패 시 `ask_user` 판단 로직:
    - SQL Guard 실패 → 재시도 (최대 2회)
    - 재시도 후에도 실패 → `status = "ask_user"`, `question_to_user`에 사용자 안내 메시지
  - 세션 상태 직렬화: `json.dumps({"question": ..., "sql": ..., "context": ...})` -> base64 인코딩
  - `user_response` 수신 시: 세션 상태 복원 → 원래 질문 + 사용자 응답 결합 → 재생성
- **핵심 로직** (KAIR에서 간소화 포팅):
  ```python
  # Triage 판단 (간소화 버전)
  async def _triage_failed_sql(self, question: str, error: str, context: dict) -> ControllerResult:
      # 1) SQL Guard 실패 패턴 분석
      # 2) 스키마 불일치 -> ask_user (테이블/컬럼 명확화 요청)
      # 3) 모호한 집계 -> ask_user (기간/단위 명확화 요청)
      # 4) 기타 -> 일반적 추가 정보 요청
      question_to_user = self._generate_clarification_question(error, context)
      return ControllerResult(status="ask_user", question_to_user=question_to_user)
  ```
- **검증**: SQL 생성 실패 시 `ask_user` 상태 반환 확인

**Step 18-3: NDJSON 스트림에 HIL 이벤트 추가** (복잡도: Medium)

- **무엇**: ReAct 스트림에서 `needs_user_input` 이벤트 발행
- **위치**: `services/oracle/app/api/text2sql.py` (react 엔드포인트)
- **방법**:
  - 파이프라인 결과가 `ask_user`일 때:
    ```python
    yield json.dumps({
        "event": "needs_user_input",
        "data": {
            "question_to_user": result.question_to_user,
            "session_state": result.session_state,
            "partial_sql": result.final_sql or None,
        }
    }) + "\n"
    ```
  - `user_response` + `session_state` 수신 시: 세션 복원 후 파이프라인 재실행
- **검증**: NDJSON 스트림에서 `needs_user_input` 이벤트 수신 확인

**Step 18-4: 프론트엔드 HumanInTheLoopInput 컴포넌트** (복잡도: Medium)

- **무엇**: KAIR `ReactInput.vue`를 React로 변환
- **위치**: `features/nl2sql/components/HumanInTheLoopInput.tsx`
- **Props**:
  ```typescript
  interface HumanInTheLoopInputProps {
    // 일반 모드
    loading: boolean;
    onSubmitQuestion: (question: string, options: ReactStartOptions) => void;
    onCancel: () => void;
    currentQuestion: string;
    // HIL 모드
    waitingForUser: boolean;
    questionToUser: string | null;
    onSubmitResponse: (answer: string) => void;
  }

  interface ReactStartOptions {
    maxToolCalls: number;
    maxSqlSeconds: number;
  }
  ```
- **UI 구조** (KAIR 동일):
  - 일반 모드: textarea + 실행 버튼 + 고급 설정 (maxToolCalls, maxSqlSeconds)
  - HIL 모드: 에이전트 질문 카드 (경고 스타일) + 답변 textarea + 답변 전송/중단 버튼
  - 전환: `waitingForUser` prop에 따라 자동 전환
- **스타일**: KAIR SCSS를 Tailwind/CSS Modules로 변환. 경고 카드에 `amber` 색상
- **검증**: HIL 모드 전환 + 답변 전송 이벤트 발행 확인

**Step 18-5: Nl2SqlPage NDJSON 핸들러에 HIL 로직 통합** (복잡도: Medium)

- **무엇**: Nl2SqlPage에서 `needs_user_input` 이벤트 처리 + HumanInTheLoopInput 연결
- **위치**: `pages/nl2sql/Nl2SqlPage.tsx`
- **변경 사항**:
  ```typescript
  // 상태 추가
  const [hilState, setHilState] = useState<{
    waiting: boolean;
    question: string | null;
    sessionState: string | null;
  }>({ waiting: false, question: null, sessionState: null });

  // NDJSON 핸들러에 추가
  onMessage: (step) => {
    if (step.data?.event === 'needs_user_input') {
      setHilState({
        waiting: true,
        question: step.data.question_to_user as string,
        sessionState: step.data.session_state as string,
      });
      return;
    }
    // ... 기존 핸들러
  }

  // 사용자 응답 전송
  const handleUserResponse = (answer: string) => {
    setHilState({ waiting: false, question: null, sessionState: null });
    postReactStream(answer, datasourceId, callbacks, {
      session_state: hilState.sessionState,
      user_response: answer,
    });
  };
  ```
- **postReactStream 수정**: `session_state`, `user_response` 파라미터 추가
  ```typescript
  // oracleNl2sqlApi.ts
  export function postReactStream(
    question: string,
    datasourceId: string,
    callbacks: {...},
    options?: { case_id?: string; row_limit?: number; session_state?: string; user_response?: string }
  ): Promise<AbortController>
  ```
- **검증**: 전체 플로우 E2E — 질문 → SQL 실패 → ask_user → 사용자 답변 → SQL 재생성

**Step 18-6: 세션 상태 관리 + 대화 히스토리 표시** (복잡도: Low)

- **무엇**: HIL 대화 히스토리를 MessageBubble로 표시
- **위치**: `pages/nl2sql/Nl2SqlPage.tsx`
- **방법**:
  - HIL 대화를 기존 메시지 목록에 추가:
    - 에이전트 질문 → AI 메시지 버블 (경고 스타일)
    - 사용자 답변 → 사용자 메시지 버블
  - 세션 상태 토큰을 메모리에 유지 (페이지 이탈 시 소멸 — 의도적)
- **검증**: 다중 HIL 라운드 시 대화 히스토리 누적 확인

---

### #19 Driver 계층 추가 (4계층 -> 5계층 온톨로지)

#### 2.19.1 영향 범위

```
변경 필요 파일:
  [프론트엔드]
  features/ontology/types/ontology.ts       -- OntologyLayer 타입 확장
  features/ontology/store/useOntologyStore.ts -- 필터/색상 맵 확장
  features/ontology/hooks/useOntologyData.ts  -- 레이어 필터 확장
  features/insight/types/insight.ts           -- Driver 노드 지원
  features/insight/components/DriverRankingPanel.tsx -- Driver 계층 연동

  [백엔드]
  services/synapse/app/services/ontology_service.py -- 레이어 상수, 라벨 매핑

  [Neo4j]
  시드 데이터 / 마이그레이션 -- Driver 라벨 + 관계 타입 추가
```

#### 2.19.2 구현 단계

**Step 19-1: 프론트엔드 타입 + 상수 확장** (복잡도: Low)

- **무엇**: OntologyLayer에 `'driver'` 추가, 관계 타입 확장
- **위치**: `features/ontology/types/ontology.ts`
- **변경**:
  ```typescript
  // 변경 전
  export type OntologyLayer = 'kpi' | 'measure' | 'process' | 'resource';
  export type OntologyRelation = '달성' | '측정' | '참여' | '매핑';

  // 변경 후
  export type OntologyLayer = 'kpi' | 'measure' | 'driver' | 'process' | 'resource';
  export type OntologyRelation =
    | '달성'      // KPI 달성
    | '측정'      // Measure -> KPI
    | '참여'      // Resource -> Process
    | '매핑'      // 데이터 매핑
    | '인과'      // CAUSES: Driver -> Measure -> KPI
    | '영향'      // INFLUENCES: Driver -> Process
    | '생산'      // PRODUCES: Process -> Measure
    | '사용';     // USED_WHEN: Resource -> Process
  ```
- **레이어 메타 상수** (새 파일 또는 기존 확장):
  ```typescript
  // features/ontology/types/layerConfig.ts (신규)
  export const LAYER_CONFIG: Record<OntologyLayer, { label: string; color: string; icon: string }> = {
    kpi:      { label: 'KPI',      color: '#ef4444', icon: 'BarChart3' },
    measure:  { label: 'Measure',  color: '#f97316', icon: 'Calculator' },
    driver:   { label: 'Driver',   color: '#eab308', icon: 'TrendingUp' },
    process:  { label: 'Process',  color: '#22c55e', icon: 'Cog' },
    resource: { label: 'Resource', color: '#3b82f6', icon: 'Server' },
  };
  ```
- **검증**: 타입 컴파일 통과, 기존 4계층 코드에서 빌드 에러 없음

**Step 19-2: Synapse 온톨로지 서비스 확장** (복잡도: Low)

- **무엇**: Driver 레이어 인식 + Neo4j 라벨 매핑
- **위치**: `services/synapse/app/services/ontology_service.py`
- **변경**:
  ```python
  # _normalize_node 메서드에서 유효 레이어 검증 추가
  VALID_LAYERS = {'kpi', 'measure', 'driver', 'process', 'resource'}

  def _normalize_node(self, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
      ...
      layer = str(payload.get("layer") or "resource").lower()
      if layer not in VALID_LAYERS:
          layer = "resource"  # 기본값 유지
      ...
  ```
  - `get_case_ontology`의 `by_layer` 카운트에 driver 자동 포함 (이미 동적이므로 변경 불필요)
- **검증**: driver 레이어 노드 생성 → get_case_ontology에서 driver 카운트 확인

**Step 19-3: Neo4j 관계 타입 확장** (복잡도: Medium)

- **무엇**: KAIR의 Driver 관련 관계 타입을 Synapse에 추가
- **위치**: `services/synapse/app/services/ontology_service.py`
- **방법**:
  - 유효 관계 타입 상수 추가 (문서화 목적):
    ```python
    VALID_RELATION_TYPES = {
        'RELATED_TO',    # 기본
        'ACHIEVES',      # 달성
        'MEASURES',      # 측정
        'PARTICIPATES',  # 참여
        'MAPS_TO',       # 매핑
        # Driver 계층 관계 (신규)
        'CAUSES',        # 인과: Driver -> Measure -> KPI
        'INFLUENCES',    # 영향: Driver -> Process
        'PRODUCES',      # 생산: Process -> Measure
        'USED_WHEN',     # 사용: Resource -> Process
        'MEASURED_AS',   # KPI 정의: Measure -> KPI
        'EXECUTES',      # 실행: Resource -> Process
    }
    ```
  - `_normalize_relation`에서 type 유효성 검증 (경고만, reject하지 않음)
- **검증**: CAUSES, INFLUENCES 관계 생성 → get_neighbors에서 조회 확인

**Step 19-4: 프론트엔드 시각화 업데이트** (복잡도: Medium)

- **무엇**: 온톨로지 그래프, 필터 UI, Insight 패널에 Driver 계층 반영
- **위치**: 다수 파일
- **변경 목록**:
  1. `useOntologyStore.ts` — 필터 초기값에 `driver` 추가:
     ```typescript
     layers: new Set<OntologyLayer>(['kpi', 'measure', 'driver', 'process', 'resource'])
     ```
  2. 온톨로지 그래프 시각화 컴포넌트 — `LAYER_CONFIG`에서 색상/아이콘 참조
  3. 필터 UI 체크박스 — Driver 체크박스 추가 (노란색 아이콘)
  4. `DriverRankingPanel.tsx` — Driver 계층 노드를 직접 표시 (현재는 그래프에서 파생)
  5. `InsightPage.tsx` — 5계층 범례(legend) 업데이트
- **검증**: 온톨로지 페이지에서 Driver 레이어 토글 → 노드 표시/숨김

**Step 19-5: 시드 데이터 + 문서 업데이트** (복잡도: Low)

- **무엇**: 테스트용 Driver 노드 시드 데이터, 아키텍처 문서 업데이트
- **위치**: 시드 스크립트, 관련 문서
- **방법**:
  - Driver 노드 예시 3-5개 생성 (예: "환율 변동", "원자재 가격", "계절 요인", "정책 변경", "경쟁사 가격")
  - CAUSES 관계 예시: "환율 변동" -[CAUSES]-> "수입 원가" (Measure)
  - INFLUENCES 관계 예시: "정책 변경" -[INFLUENCES]-> "심사 프로세스" (Process)
- **검증**: 시드 데이터 로드 후 온톨로지 그래프에서 5계층 표시 확인

---

### #20 LLM 리랭킹 + PRF (Pseudo-Relevance Feedback)

#### 2.20.1 아키텍처

```
현재 Axiom Oracle 파이프라인:
  질문 → LLM SQL 생성 → Guard → 실행

목표:
  질문 → 임베딩 → [다축 벡터 검색] → [PRF 재검색] → [LLM 리랭킹] → 스키마 선택 → SQL 생성 → Guard → 실행
                      ↑                    ↑                ↑
                   Step 20-2           Step 20-4         Step 20-5

KAIR build_sql_context 파이프라인 단계:
  1. embedding (질문 임베딩)
  2. enrich (HyDE + similar queries/value mappings) — 병렬
  3. table_search (다축 벡터 검색 + PRF + FK/sibling expansion + LLM rerank)
  4. column_search (테이블별 컬럼 선택)
  5. schema_xml (선택된 스키마 XML 생성)
  6. fk_relationships
  7. resolved_values
  8. suggestions
  9. light_queries (가벼운 검증 쿼리)
```

#### 2.20.2 구현 단계

**Step 20-1: 임베딩 클라이언트 모듈** (복잡도: Medium)

- **무엇**: 텍스트 임베딩 생성 클라이언트 (KAIR `create_embedding_client` 포팅)
- **위치**: `services/oracle/app/core/embedding.py` (신규)
- **방법**:
  ```python
  class EmbeddingClient:
      """텍스트 -> 벡터 변환 클라이언트"""
      def __init__(self, model_name: str = "multilingual-e5-large"):
          # 옵션 1: 로컬 모델 (sentence-transformers)
          # 옵션 2: 외부 API (OpenAI embeddings / HuggingFace Inference)
          # 옵션 3: Synapse 경유 (이미 Neo4j에 벡터 인덱스 있음)
          ...

      async def embed_text(self, text: str) -> list[float]:
          """단일 텍스트 임베딩"""
          ...

      async def embed_batch(self, texts: list[str]) -> list[list[float]]:
          """배치 임베딩"""
          ...
  ```
- **의존**: Synapse의 Neo4j 벡터 인덱스와 동일 차원 사용 필수
- **설정**: `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` 환경변수
- **검증**: 짧은 텍스트/긴 텍스트 임베딩 생성, 차원 일치 확인

**Step 20-2: 다축 벡터 검색 모듈** (복잡도: High)

- **무엇**: KAIR `table_search_flow.py`의 다축 검색 로직 포팅
- **위치**: `services/oracle/app/pipelines/table_search.py` (신규)
- **방법**: KAIR 로직 간소화 포팅:
  ```python
  @dataclass
  class TableCandidate:
      schema: str
      name: str
      description: str | None
      score: float
      fqn: str  # schema.name

  @dataclass
  class TableSearchResult:
      candidates: list[TableCandidate]
      selected: list[TableCandidate]
      mode: str

  async def multi_axis_table_search(
      question: str,
      question_embedding: list[float],
      *,
      neo4j_client,
      embedder: EmbeddingClient,
      schema_filter: list[str] | None = None,
      per_axis_top_k: int = 20,
      rerank_top_k: int = 20,
  ) -> TableSearchResult:
      """
      다축 벡터 검색 (KAIR 간소화):
      1. question axis (weight 0.35)
      2. regex axis (weight 0.5) — 질문에서 추출한 키워드 임베딩
      3. 가중 합산 → 후보 테이블 목록
      """
  ```
- **Neo4j 쿼리**: Synapse의 `graph_search.py` 기존 벡터 검색 함수 활용/확장
  ```cypher
  CALL db.index.vector.queryNodes('table_embedding_index', $k, $embedding)
  YIELD node, score
  WHERE node.schema IN $schemas
  RETURN node.schema AS schema, node.name AS name, node.description AS description, score
  ```
- **검증**: 질문 → 테이블 후보 목록 반환 (score 내림차순)

**Step 20-3: HyDE (Hypothetical Document Embeddings)** (복잡도: Medium)

- **무엇**: 질문에서 가상 SQL/스키마를 생성하고 임베딩하여 검색 정확도 향상
- **위치**: `services/oracle/app/pipelines/hyde.py` (신규)
- **방법**: KAIR `hyde_flow.py` 간소화:
  ```python
  async def generate_hyde(
      question: str,
      llm_client,
      embedder: EmbeddingClient,
  ) -> HydeResult:
      """
      1. LLM에게 가상 SQL/스키마 키워드 생성 요청
      2. 생성된 텍스트 임베딩 → schema_embedding
      3. 키워드(테이블명, 컬럼명) 추출
      """
      # LLM 프롬프트: "다음 질문에 답하기 위한 SQL에서 사용할 테이블/컬럼을 추측하세요"
      # 출력: {"tables": [...], "columns": [...], "summary": "..."}
  ```
- **검증**: 자연어 질문 → HyDE 키워드 + 임베딩 생성

**Step 20-4: PRF (Pseudo-Relevance Feedback) 구현** (복잡도: Medium)

- **무엇**: 1차 검색 상위 테이블의 설명 텍스트를 질문에 결합하여 재검색
- **위치**: `services/oracle/app/pipelines/table_search.py` (Step 20-2에 통합)
- **방법**: KAIR PRF 로직 포팅:
  ```python
  async def prf_refine(
      question: str,
      top_tables: list[TableCandidate],
      *,
      neo4j_client,
      embedder: EmbeddingClient,
      prf_top_a: int = 20,      # 상위 A개 테이블 텍스트 사용
      prf_top_k: int = 300,     # PRF 검색 결과 수
      prf_weight: float = 0.8,  # PRF 점수 가중치
      prf_max_chars: int = 2500,  # 텍스트 결합 최대 길이
  ) -> list[TableCandidate]:
      """
      PRF 재검색:
      1. 상위 A개 테이블의 embedding_text 조회
      2. (질문 + 테이블 텍스트) 결합 → 새 임베딩 생성
      3. 새 임베딩으로 벡터 검색 → prf_weight 가중하여 점수 합산
      """
  ```
- **핵심**: KAIR에서 `_neo4j_fetch_table_embedding_texts` → Axiom Synapse의 Neo4j에서 동일 함수 구현
- **검증**: PRF 전후 테이블 순위 변화 비교 (상위 테이블이 더 관련성 높아야 함)

**Step 20-5: LLM 리랭킹 모듈** (복잡도: High)

- **무엇**: 벡터 검색 후보를 LLM으로 최종 재정렬
- **위치**: `services/oracle/app/pipelines/table_rerank.py` (신규)
- **방법**: KAIR `table_rerank_generator.py` 간소화:
  ```python
  @dataclass
  class RerankCandidate:
      index: int
      schema: str
      name: str
      description: str

  async def llm_rerank_tables(
      question: str,
      candidates: list[RerankCandidate],
      *,
      llm_client,
      top_k: int = 20,
      hyde_summary: str = "",
  ) -> list[int] | None:
      """
      LLM 리랭킹:
      1. 후보 테이블 목록 + 질문을 LLM에 전달
      2. LLM이 관련도 순으로 인덱스 정렬 반환
      3. 실패 시 None → fallback (벡터 점수 순)

      프롬프트:
      "다음 질문에 답하기 위해 가장 관련 있는 테이블을 순서대로 선택하세요.
       질문: {question}
       HyDE: {hyde_summary}
       후보: [0] schema.table — description ..."
      """
  ```
- **LLM**: 기존 `llm_factory` 활용 (같은 모델 또는 별도 경량 모델)
- **Fallback**: LLM 호출 실패 시 벡터 점수 순서 유지 (KAIR 동일)
- **검증**: LLM 응답 파싱 (인덱스 배열), fallback 동작 확인

**Step 20-6: 파이프라인 통합 + 설정** (복잡도: Medium)

- **무엇**: 모든 검색 모듈을 NL2SQL 파이프라인에 통합
- **위치**: `services/oracle/app/pipelines/nl2sql_pipeline.py`
- **변경**: `NL2SQLPipeline._generate_sql` 메서드 리팩터링:
  ```python
  async def _enhanced_schema_retrieval(self, question: str, datasource_id: str) -> list[TableSchema]:
      """개선된 스키마 검색 (벡터 + PRF + LLM 리랭킹)"""
      # 1. 질문 임베딩
      embedding = await self.embedder.embed_text(question)

      # 2. HyDE 생성
      hyde = await generate_hyde(question, self.llm, self.embedder)

      # 3. 다축 벡터 검색
      search_result = await multi_axis_table_search(
          question, embedding,
          neo4j_client=self.neo4j,
          embedder=self.embedder,
      )

      # 4. PRF 재검색
      prf_candidates = await prf_refine(
          question, search_result.candidates,
          neo4j_client=self.neo4j,
          embedder=self.embedder,
      )

      # 5. LLM 리랭킹
      reranked = await llm_rerank_tables(
          question, prf_candidates,
          llm_client=self.llm,
          hyde_summary=hyde.rerank_text,
      )

      # 6. 컬럼 선택 (상위 테이블)
      return self._fetch_columns_for_tables(reranked[:self.rerank_top_k])
  ```
- **Feature Flag**: `ENABLE_ENHANCED_RETRIEVAL=true/false` 환경변수로 on/off
- **NDJSON 스테이지 이벤트**:
  ```python
  # 프론트엔드 ReactProgressTimeline에 단계 표시
  yield {"event": "pipeline_stage", "stage": "embedding", "status": "done", "elapsed_ms": ...}
  yield {"event": "pipeline_stage", "stage": "hyde", "status": "done", ...}
  yield {"event": "pipeline_stage", "stage": "table_search", "status": "done", "counts": {"candidates": N}}
  yield {"event": "pipeline_stage", "stage": "prf", "status": "done", ...}
  yield {"event": "pipeline_stage", "stage": "rerank", "status": "done", "counts": {"selected": K}}
  ```
- **검증**: Feature flag on/off 전환, 기존 파이프라인 호환, 성능 프로파일링

**Step 20-7: 프론트엔드 진행 표시 업데이트** (복잡도: Low)

- **무엇**: ReactProgressTimeline에 새 파이프라인 단계 표시
- **위치**: `pages/nl2sql/components/ReactProgressTimeline.tsx`
- **변경**: `pipeline_stage` 이벤트 처리 추가
  ```typescript
  const STAGE_LABELS: Record<string, string> = {
    embedding: '질문 분석 중...',
    hyde: '가상 스키마 생성 중...',
    table_search: '관련 테이블 검색 중...',
    prf: '검색 결과 개선 중...',
    rerank: 'AI 순위 재정렬 중...',
    column_search: '컬럼 선택 중...',
    sql_generate: 'SQL 생성 중...',
    sql_validate: 'SQL 검증 중...',
    sql_execute: 'SQL 실행 중...',
  };
  ```
- **검증**: 스트림 진행 시 각 단계 타임라인 표시

---

## 3. 프론트엔드 컴포넌트 설계 종합

### 3.1 파일 구조 전체

```
canvas/src/
  features/
    datasource/
      components/
        ERDiagramPanel.tsx         # #16 ERD 메인 컨테이너
        ERDToolbar.tsx             # #16 ERD 툴바
        MermaidERDRenderer.tsx     # #16 Mermaid 렌더러
        SchemaExplorer.tsx         # 기존
        SyncProgress.tsx           # 기존
      hooks/
        useERDData.ts              # #16 ERD 데이터 훅
        useDatasources.ts          # 기존
      types/
        erd.ts                     # #16 ERD 타입
      utils/
        mermaidCodeGen.ts          # #16 Mermaid 코드 생성
      api/
        weaverDatasourceApi.ts     # 기존
      schemas/
        datasourceFormSchema.ts    # 기존

    feedback/                      # #17 신규 feature slice
      api/
        feedbackApi.ts
      components/
        FeedbackDashboard.tsx
        FeedbackSummaryCards.tsx
        FeedbackTrendChart.tsx
        FailurePatternTable.tsx
        DatasourceBreakdown.tsx
      hooks/
        useFeedbackStats.ts
      types/
        feedbackStats.ts

    nl2sql/
      components/
        HumanInTheLoopInput.tsx    # #18 HIL 입력 컴포넌트
        QueryHistoryPanel.tsx      # 기존
      api/
        oracleNl2sqlApi.ts         # 기존 (수정: session_state, user_response 추가)
      hooks/
        useQueryHistory.ts         # 기존
      types/
        nl2sql.ts                  # 기존 (수정: HIL 이벤트 타입 추가)

    ontology/
      types/
        ontology.ts                # 기존 (수정: driver 레이어 + 관계 타입 추가)
        layerConfig.ts             # #19 신규 — 5계층 메타 상수
      store/
        useOntologyStore.ts        # 기존 (수정: driver 필터)
      hooks/
        useOntologyData.ts         # 기존 (수정: driver 레이어)
      api/
        ontologyApi.ts             # 기존

  pages/
    nl2sql/
      Nl2SqlPage.tsx               # 기존 (수정: HIL 상태 관리)
      components/
        ReactProgressTimeline.tsx  # 기존 (수정: 파이프라인 단계 표시)
    settings/
      FeedbackStatsPage.tsx        # #17 신규 페이지

  lib/routes/
    routes.ts                      # 수정: SETTINGS_FEEDBACK 추가
    routeConfig.tsx                # 수정: FeedbackStatsPage lazy import
```

### 3.2 주요 컴포넌트 Props/State 명세

#### ERDiagramPanel
```typescript
interface ERDiagramPanelProps {
  datasourceId: string;
}
// 내부 상태:
// - filter: ERDFilter (searchQuery, showConnectedOnly, maxTables)
// - mermaidCode: string (generateMermaidERCode 결과)
// - stats: ERDStats
// - isRendering: boolean
```

#### HumanInTheLoopInput
```typescript
interface HumanInTheLoopInputProps {
  loading: boolean;
  onSubmitQuestion: (question: string, options: ReactStartOptions) => void;
  onCancel: () => void;
  currentQuestion: string;
  waitingForUser: boolean;
  questionToUser: string | null;
  onSubmitResponse: (answer: string) => void;
}
// 내부 상태:
// - question: string (textarea 값)
// - userResponse: string (HIL 답변)
// - showSettings: boolean (고급 설정 토글)
// - maxToolCalls: number (기본 30)
// - maxSqlSeconds: number (기본 60)
```

#### FeedbackDashboard
```typescript
interface FeedbackDashboardProps {
  // 없음 — 내부에서 라우트 쿼리 파라미터로 기간 관리
}
// 내부 상태:
// - dateRange: { from: Date; to: Date }
// - granularity: 'day' | 'week'
// TanStack Query:
// - useFeedbackSummary(dateRange)
// - useFeedbackTrend(dateRange, granularity)
// - useFeedbackFailures(dateRange)
// - useFeedbackByDatasource(dateRange)
```

---

## 4. 테스트 계획

### 4.1 단위 테스트

| 대상 | 테스트 내용 | 위치 |
|------|------------|------|
| `mermaidCodeGen.ts` | 빈 테이블, FK 추론, 타입 매핑, 특수문자 정규화, 컬럼 제한 | `features/datasource/utils/__tests__/mermaidCodeGen.test.ts` |
| `feedback_analytics.py` | 날짜 범위 필터, granularity별 집계, 빈 데이터 처리 | `services/oracle/tests/test_feedback_analytics.py` |
| `table_search.py` | 다축 점수 합산, PRF 가중치, 빈 결과 fallback | `services/oracle/tests/test_table_search.py` |
| `table_rerank.py` | LLM 응답 파싱, 인덱스 범위 검증, fallback 동작 | `services/oracle/tests/test_table_rerank.py` |
| `hyde.py` | LLM 응답 파싱, 키워드 추출, 임베딩 생성 | `services/oracle/tests/test_hyde.py` |
| `nl2sql_pipeline.py` (HIL) | ask_user 상태 반환, 세션 직렬화/복원, user_response 처리 | `services/oracle/tests/test_nl2sql_hil.py` |
| `layerConfig.ts` | 5계층 색상/아이콘 매핑 완전성 | `features/ontology/types/__tests__/layerConfig.test.ts` |

### 4.2 통합 테스트

| 시나리오 | 검증 내용 |
|---------|----------|
| ERD E2E | 데이터소스 선택 → 테이블 로드 → ERD 렌더링 → 검색 → SVG 다운로드 |
| 피드백 대시보드 E2E | 피드백 제출 → 통계 API 호출 → 차트 렌더링 → 기간 변경 |
| HIL E2E | 질문 입력 → SQL 실패 → needs_user_input → 답변 입력 → SQL 재생성 → 결과 표시 |
| Driver 계층 E2E | Driver 노드 생성 → 온톨로지 그래프에 표시 → CAUSES 관계 → Insight 패널 연동 |
| PRF + Rerank E2E | 질문 → 벡터 검색 → PRF → LLM 리랭킹 → SQL 생성 (기존 대비 정확도 향상 검증) |

### 4.3 성능 테스트

| 항목 | 기준 |
|------|------|
| ERD 렌더링 | 50개 테이블 기준 2초 이내 |
| 피드백 통계 쿼리 | 10만건 기준 500ms 이내 |
| PRF 전체 파이프라인 | 추가 latency 800ms 이내 (임베딩 + Neo4j 검색 + LLM 리랭킹) |
| HIL 세션 복원 | 200ms 이내 |

---

## 5. 리스크 평가

| # | 리스크 | 심각도 | 완화 전략 |
|---|--------|--------|----------|
| R1 | Mermaid.js 대규모 ERD 렌더링 성능 | Medium | maxTables 제한 (기본 50), lazy rendering |
| R2 | LLM 리랭킹 호출 latency (1-3초 추가) | High | Feature flag로 on/off, 캐싱, 타임아웃 설정 (2초), fallback |
| R3 | PRF 임베딩 차원 불일치 | High | Synapse Neo4j 벡터 인덱스와 동일 모델/차원 강제 |
| R4 | HIL 세션 상태 크기 | Low | Base64 인코딩, 최대 크기 제한 (32KB) |
| R5 | 피드백 통계 쿼리 성능 (대량 데이터) | Medium | 인덱스 추가 (rating, created_at), 캐싱 (5분 TTL) |
| R6 | Driver 계층 추가 시 기존 4계층 코드 호환성 | Low | OntologyLayer union type이므로 기존 값 유지, 점진적 마이그레이션 |
| R7 | HIL 백엔드 복잡도 (KAIR 전체 포팅 vs 간소화) | Medium | Phase 1은 간소화 버전 (단일 라운드), Phase 2에서 multi-round + context_refresh |

---

## 6. 구현 순서 + 일정 (권장)

| 스프린트 | 항목 | 이유 |
|---------|------|------|
| Sprint 1 (5d) | #19 Driver 계층 | 가장 작은 변경, 다른 항목과 독립적, 즉시 효과 |
| Sprint 2 (5d) | #16 ERD 시각화 (Step 16-1~16-4) | 프론트엔드 단독, 백엔드 변경 없음 |
| Sprint 3 (5d) | #16 ERD 완성 + #17 백엔드 | ERD 고급 기능 + 피드백 통계 백엔드 |
| Sprint 4 (5d) | #17 프론트엔드 | 피드백 대시보드 UI |
| Sprint 5-6 (10d) | #20 LLM 리랭킹 + PRF | 백엔드 집중 (임베딩, 벡터 검색, PRF, LLM 리랭킹) |
| Sprint 7-8 (10d) | #18 HIL | 백엔드 + 프론트엔드 동시 작업 (가장 복잡) |
| Sprint 9 (5d) | 통합 테스트 + 버그 수정 | 전체 E2E 검증 |

**총 예상 공수**: 45일 (9 스프린트)

---

## 7. 의존 관계 다이어그램

```
#19 Driver 계층 ──────────────────────────────────┐
  (독립)                                            │
                                                    ▼
#16 ERD 시각화 ─────────────────────── 통합 테스트 ──► 릴리스
  (독립)                                   ▲
                                           │
#17 피드백 대시보드 ──────────────────────┤
  (독립)                                   │
                                           │
#20 LLM 리랭킹 + PRF ──► #18 HIL ────────┘
  (임베딩 클라이언트 필요)   (ReAct 파이프라인 위에 구축)
```

- #16, #17, #19 는 상호 독립 → 병렬 작업 가능
- #20 은 임베딩 클라이언트 + Neo4j 벡터 인덱스가 선행 조건
- #18 은 #20의 enhanced 파이프라인 위에 HIL 판단 로직이 올라가므로, #20 이후 또는 동시 진행 (단, Feature flag로 분리)
