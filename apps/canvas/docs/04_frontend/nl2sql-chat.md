# NL2SQL 대화형 쿼리 UI

<!-- affects: frontend, api -->
<!-- requires-update: 02_api/api-contracts.md (Oracle API) -->

## 이 문서가 답하는 질문

- NL2SQL 대화형 쿼리 UI의 화면 구성은 어떻게 되는가?
- SSE 스트리밍으로 "생각 중 -> SQL 생성 -> 결과" 흐름을 어떻게 표현하는가?
- 결과 테이블과 차트 자동 추천은 어떻게 동작하는가?
- K-AIR NaturalQuery에서 무엇이 달라지는가?

---

## 1. 화면 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────┐
│ 💬 자연어 쿼리                                    [히스토리] [저장됨]│
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──── 대화 영역 ─────────────────────────────────────────────────┐ │
│  │                                                                 │ │
│  │  ┌─ 사용자 ─────────────────────────────────────────────────┐  │ │
│  │  │ "지난 분기 부채비율 상위 10개 기업을 알려줘"              │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                 │ │
│  │  ┌─ AI 응답 ───────────────────────────────────────────────┐   │ │
│  │  │                                                          │   │ │
│  │  │  💭 질문을 분석하고 있습니다...                          │   │ │
│  │  │  ✓ 관련 테이블을 찾았습니다: financial_statements         │   │ │
│  │  │                                                          │   │ │
│  │  │  ┌─ SQL ─────────────────────────────────────────────┐  │   │ │
│  │  │  │ SELECT company_name,                               │  │   │ │
│  │  │  │        total_debt / total_equity AS debt_ratio     │  │   │ │
│  │  │  │ FROM financial_statements                          │  │   │ │
│  │  │  │ WHERE quarter = '2024Q3'                           │  │   │ │
│  │  │  │ ORDER BY debt_ratio DESC                           │  │   │ │
│  │  │  │ LIMIT 10;                                          │  │   │ │
│  │  │  │                                   [복사] [수정]    │  │   │ │
│  │  │  └────────────────────────────────────────────────────┘  │   │ │
│  │  │                                                          │   │ │
│  │  │  ┌─ 결과 (10건, 1.2초) ─────────────────────────────┐  │   │ │
│  │  │  │                                                    │  │   │ │
│  │  │  │  [테이블●] [바 차트] [내보내기]                    │  │   │ │
│  │  │  │                                                    │  │   │ │
│  │  │  │  ┌────┬────────────┬──────────┐                   │  │   │ │
│  │  │  │  │ #  │ 기업명      │ 부채비율  │                   │  │   │ │
│  │  │  │  ├────┼────────────┼──────────┤                   │  │   │ │
│  │  │  │  │ 1  │ (주)한진    │  482.3%  │                   │  │   │ │
│  │  │  │  │ 2  │ 두산인프라  │  385.1%  │                   │  │   │ │
│  │  │  │  │ 3  │ 삼성바이오  │  312.7%  │                   │  │   │ │
│  │  │  │  │ .. │ ...        │  ...     │                   │  │   │ │
│  │  │  │  └────┴────────────┴──────────┘                   │  │   │ │
│  │  │  │                                                    │  │   │ │
│  │  │  │  💡 추천: "바 차트로 시각화하면 비교가 쉽습니다"  │  │   │ │
│  │  │  │                                                    │  │   │ │
│  │  │  └────────────────────────────────────────────────────┘  │   │ │
│  │  └──────────────────────────────────────────────────────────┘   │ │
│  │                                                                 │ │
│  │  ┌─ 사용자 ─────────────────────────────────────────────────┐  │ │
│  │  │ "이 중에서 최적화 프로젝트 진행 중인 기업만 필터링해줘"  │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                 │ │
│  │  ┌─ AI 응답 (스트리밍 중...) ──────────────────────────────┐  │ │
│  │  │  ⟳ 이전 쿼리를 기반으로 필터를 추가하고 있습니다...      │  │ │
│  │  └──────────────────────────────────────────────────────────┘  │ │
│  │                                                                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌──── 입력 영역 ────────────────────────────────────────────────┐  │
│  │  데이터소스: [운영 PostgreSQL ▼]                                │  │
│  │                                                                 │  │
│  │  [                                                          📤] │  │
│  │   질문을 입력하세요... (예: "올해 분석 완료된 프로젝트 수는?")  │  │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. API 연동

### 2.1 백엔드 엔드포인트

NL2SQL UI는 Oracle 서비스의 Text2SQL API를 사용한다. 두 가지 모드를 지원한다.

| 모드 | 엔드포인트 | 응답 형식 | 용도 |
|------|-----------|----------|------|
| 단일 변환 | `POST /api/v1/text2sql/ask` | JSON (단일 응답) | 간단한 질문, 빠른 응답 |
| ReAct 추론 | `POST /api/v1/text2sql/react` | NDJSON 스트림 | 복잡한 질문, 다단계 추론 과정 표시 |

- **API 스펙**: Oracle [text2sql-api.md](../../../services/oracle/docs/02_api/text2sql-api.md)
- **라우팅**: Core API Gateway를 통해 Oracle 서비스로 프록시됨

### 2.2 타입 정의

```typescript
// features/nl2sql/types/nl2sql.ts

/** 차트 유형 — Oracle API visualization.chart_type과 일치 */
type ChartType = 'bar' | 'line' | 'pie' | 'scatter' | 'kpi_card' | 'table';

/** 결과 컬럼 정보 */
interface ResultColumn {
  name: string;
  type: string;   // 'varchar' | 'numeric' | 'bigint' | 'date' | ...
}

/** /text2sql/ask 응답의 data.visualization */
interface ChartConfig {
  chart_type: ChartType;
  config: {
    x_column: string;
    y_column: string;
    x_label: string;
    y_label: string;
  };
}

/** ReAct 스트림 단계 유형 — text2sql-api.md §3.3 step과 일치 */
type ReactStepType =
  | 'select'    // 테이블 선택
  | 'generate'  // SQL 생성
  | 'validate'  // SQL 검증
  | 'fix'       // SQL 수정 (validate 실패 시)
  | 'execute'   // SQL 실행
  | 'quality'   // 품질 점검
  | 'triage'    // 결과 분류/라우팅
  | 'result'    // 최종 결과
  | 'error';    // 에러 발생
```

### 2.3 메시지 상태 전이 (단일 모드)

```
[입력 전송] ──→ [thinking] ──→ [sql_generated] ──→ [executing] ──→ [result] ──→ [done]
                    │                 │                  │              │
                 "분석 중..."      SQL 표시         "실행 중..."    테이블 표시
                 스피너 표시      복사/수정 버튼      스피너        차트 추천
```

### 2.4 SSE 메시지 처리 (단일 모드: /text2sql/ask)

```typescript
// hooks/useNl2sql.ts

interface Nl2SqlState {
  status: 'idle' | 'thinking' | 'sql_generated' | 'executing' | 'result' | 'error';
  thinkingText: string;
  sql: string | null;
  explanation: string | null;
  columns: ResultColumn[];
  rows: (string | number | null)[][];
  rowCount: number;
  queryTime: number;
  chartRecommendation: ChartConfig | null;
}

function useNl2sql() {
  const [state, setState] = useState<Nl2SqlState>(initialState);

  const ask = useCallback(async (question: string, datasourceId: string) => {
    setState({ ...initialState, status: 'thinking', thinkingText: '질문을 분석하고 있습니다...' });

    const cleanup = createSSEConnection({
      url: `/api/v1/text2sql/ask`,
      body: { question, datasource_id: datasourceId },
      onMessage: (type, data) => {
        switch (type) {
          case 'thinking':
            setState(prev => ({ ...prev, thinkingText: data.content }));
            break;
          case 'sql_generated':
            setState(prev => ({
              ...prev,
              status: 'sql_generated',
              sql: data.sql,
              explanation: data.explanation,
            }));
            break;
          case 'executing':
            setState(prev => ({ ...prev, status: 'executing' }));
            break;
          case 'result':
            setState(prev => ({
              ...prev,
              status: 'result',
              columns: data.result.columns,
              rows: data.result.rows,
              rowCount: data.result.row_count,
              queryTime: data.metadata.execution_time_ms,
              chartRecommendation: data.visualization ?? null,
            }));
            break;
        }
      },
      onComplete: () => { /* SSE 종료 */ },
      onError: () => {
        setState(prev => ({ ...prev, status: 'error' }));
      },
    });

    return cleanup;
  }, []);

  return { ...state, ask };
}
```

### 2.5 NDJSON 스트림 처리 (ReAct 모드: /text2sql/react)

복잡한 질문은 ReAct 다단계 추론을 사용한다. 각 추론 단계가 NDJSON으로 실시간 전송된다.

```typescript
// hooks/useNl2sqlReact.ts

interface ReactStep {
  step: ReactStepType;
  iteration: number;
  data: Record<string, unknown>;
}

interface ReactState {
  status: 'idle' | 'streaming' | 'completed' | 'error';
  steps: ReactStep[];
  currentStep: ReactStepType | null;
  iteration: number;
  finalResult: Nl2SqlState | null;
}

function useNl2sqlReact() {
  const [state, setState] = useState<ReactState>(initialReactState);

  const askReact = useCallback(async (question: string, datasourceId: string) => {
    setState({ ...initialReactState, status: 'streaming' });

    // NDJSON 스트림 — Content-Type: application/x-ndjson
    const response = await fetch('/api/v1/text2sql/react', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ question, datasource_id: datasourceId }),
    });

    const reader = response.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.trim()) continue;
        const step: ReactStep = JSON.parse(line);

        setState(prev => ({
          ...prev,
          steps: [...prev.steps, step],
          currentStep: step.step,
          iteration: step.iteration,
          ...(step.step === 'result' ? { status: 'completed', finalResult: step.data } : {}),
          ...(step.step === 'error' ? { status: 'error' } : {}),
        }));
      }
    }
  }, []);

  return { ...state, askReact };
}
```

ReAct 모드 UI에서는 각 단계를 타임라인 형태로 표시한다:
```
  ✓ 테이블 선택: process_metrics, organizations (1단계)
  ✓ SQL 생성: SELECT o.org_name, COUNT(CASE WHEN ...) (1단계)
  ✓ SQL 검증: PASS (1단계)
  ✓ SQL 실행: 15건 (1단계)
  ⟳ 품질 점검: "2023년 데이터도 필요합니다" (1단계)
  ... 2단계 진행 중 ...
```

---

## 3. 차트 자동 추천

Oracle API가 쿼리 결과와 함께 적합한 차트 타입을 추천한다.

| 결과 특성 | 추천 차트 | 근거 |
|-----------|----------|------|
| 1개 범주 + 1개 수치 | 바 차트 | 항목 간 크기 비교 |
| 시계열 + 수치 | 라인 차트 | 시간 흐름 추이 |
| 비율/비중 (합계=100%) | 파이 차트 | 구성비 |
| 2개 수치 | 산점도 | 상관관계 |
| 기타 | 테이블 (기본) | 범용 |

---

## 4. 컴포넌트 분해

```
Nl2SqlPage
├── ChatInterface
│   ├── MessageBubble (x N)
│   │   ├── UserMessage
│   │   └── AiResponse
│   │       ├── ThinkingIndicator (⟳ 스피너 + 텍스트)
│   │       ├── SqlPreview (구문 강조 코드 블록)
│   │       │   ├── 복사 버튼
│   │       │   └── 수정 버튼 (SQL 직접 편집)
│   │       ├── ResultTable (TanStack Table)
│   │       ├── ChartRecommender
│   │       │   ├── shared/Chart/BarChart
│   │       │   ├── shared/Chart/LineChart
│   │       │   └── shared/Chart/PieChart
│   │       └── ExportButton (CSV)
│   └── AutoScrollAnchor
├── ChatInput
│   ├── DatasourceSelector (shared/ui/Select)
│   ├── TextInput (shared/ui/Textarea, auto-resize)
│   └── SendButton
└── Sidebar (시트 패널)
    ├── QueryHistory (최근 쿼리 목록)
    └── SavedQueries (저장된 쿼리)
```

---

## 5. 대화 컨텍스트 관리

NL2SQL은 **이전 대화를 컨텍스트로 활용**하여 후속 질문을 처리한다.

```
질문 1: "지난 분기 부채비율 상위 10개 기업은?"
→ SQL: SELECT ... FROM financial_statements WHERE quarter = '2024Q3' ...

질문 2: "이 중에서 최적화 프로젝트 진행 중인 기업만 필터링해줘"
→ context: [질문1의 SQL]을 Oracle API에 전달
→ SQL: SELECT ... FROM financial_statements fs
       JOIN cases c ON fs.company_id = c.org_id
       WHERE quarter = '2024Q3' AND c.type = 'optimization' ...
```

```typescript
// 대화 히스토리를 context로 전달
const ask = (question: string) => {
  const context = messages
    .filter(m => m.type === 'ai' && m.sql)
    .map(m => m.sql!);

  // text2sql/ask API 호출 (API 스펙에 context 필드 추가 필요 — 백엔드 협의 사항)
  oracleApi.text2sqlAsk({
    question,
    datasource_id: selectedDatasource,
    context,       // 이전 SQL 배열 (대화형 NL2SQL 지원 시)
    options: {
      row_limit: 100,
      include_viz: true,
    },
  });
};
```

> **백엔드 협의 필요**: `context` 필드는 현재 text2sql-api.md `/ask` 요청 스펙에 정의되어 있지 않다. 대화형 NL2SQL을 지원하려면 백엔드에 `context: string[]` (이전 SQL 배열) 필드 추가를 요청해야 한다.

---

## 6. UX 상태 설계 (에러/빈 상태/로딩)

### 6.1 에러 상태

| 시나리오 | UI 표시 | 액션 |
|---------|---------|------|
| 페이지 로드 실패 | ErrorFallback (implementation-guide.md §1.2) | "다시 시도" 버튼 |
| SQL 생성 실패 (API 에러) | AiResponse 내 에러 메시지 "쿼리를 생성하지 못했습니다. 다른 표현으로 다시 시도해 주세요." | 입력 필드 포커스 유지 |
| SQL 실행 실패 (쿼리 에러) | 에러 코드 + 메시지 표시 (SQL 블록 아래) + "SQL을 수정하시겠습니까?" | SQL 수정 모드 진입 |
| SSE/NDJSON 스트림 중단 | "응답이 중단되었습니다" + "재시도" 버튼 | AbortController 정리 + 재요청 |
| 데이터소스 연결 실패 | 인라인 경고 "선택한 데이터소스에 연결할 수 없습니다" | DatasourceSelector 강조 |

### 6.2 빈 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 첫 진입 (대화 없음) | 중앙 EmptyState: 💬 아이콘 + "자연어로 데이터를 분석하세요" + 예시 질문 3개 (클릭 시 자동 입력) |
| 쿼리 결과 0건 | "조건에 맞는 데이터가 없습니다. 조건을 변경하여 다시 질문해 보세요." |
| 데이터소스 없음 | "사용 가능한 데이터소스가 없습니다." + [데이터소스 관리] 링크 (/data/datasources) |
| 히스토리 없음 | "아직 질문 기록이 없습니다." |

### 6.3 로딩 상태

| 시나리오 | UI 표시 |
|---------|---------|
| AI 응답 중 (thinking) | ThinkingIndicator: ⟳ 스피너 + 단계별 텍스트 ("분석 중...", "테이블 찾는 중...") |
| SQL 실행 중 | 스피너 + "쿼리 실행 중..." |
| ReAct 다단계 진행 | 단계 타임라인 (✓ 완료 단계 / ⟳ 진행 중 단계) |
| 결과 차트 렌더링 | ChartSkeleton (차트 영역 크기 유지) |
| 히스토리 조회 중 | Sidebar 내 Skeleton 3줄 |

---

## 7. 역할별 접근 제어 (RBAC)

### 7.1 기능별 역할 권한

| 기능 | 필요 권한 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------|----------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| 페이지 접근 | `nl2sql:query` | O | O | O | O | O | O | X |
| 쿼리 실행 (ask/react) | `nl2sql:query` | O | O | O | O | O | O | X |
| SQL 직접 수정 실행 | `nl2sql:query` | O | O | O | O | O | O | X |
| 쿼리 히스토리 조회 | `nl2sql:query` | O | O | O | O | O | O | X |
| 데이터소스 선택 | `datasource:read` | O | O | O | O | O | O | O |

### 7.2 프론트엔드 가드

```typescript
// 라우트 가드: viewer는 NL2SQL 페이지 접근 불가
<RoleGuard requiredPermission="nl2sql:query" fallback={<NoAccessPage />}>
  <Nl2SqlPage />
</RoleGuard>
```

> **SSOT**: 권한 매트릭스는 `services/core/docs/07_security/auth-model.md` §2.3을 따른다.
> **프론트엔드 구현**: `apps/canvas/docs/07_security/auth-flow.md`의 `RoleGuard`, `usePermission` 훅 참조.

---

## 8. K-AIR 전환 노트

| K-AIR (NaturalQuery.vue) | Canvas | 전환 노트 |
|--------------------------|--------|-----------|
| 단일 입력 필드 | 채팅 대화 인터페이스 | 컨텍스트 유지 대화형 |
| 결과: 테이블만 | 테이블 + 차트 자동 추천 | chartRecommendation |
| ReAct 에이전트 (백엔드) | Oracle API SSE 스트리밍 | 중간 상태 표시 |
| i18n (5개 언어) | ko/en 2개 언어 | 불필요 언어 제거 |
| 데이터소스: 고정 | 데이터소스 선택 가능 | DatasourceSelector |

---

## 결정 사항 (Decisions)

- viewer 역할은 NL2SQL 접근 불가 (nl2sql:query 권한 없음)
  - 근거: viewer는 읽기 전용, 데이터 쿼리 실행은 분석 행위에 해당

- 채팅 인터페이스 (단일 입력이 아닌 대화형)
  - 근거: 후속 질문으로 결과를 정제하는 UX가 자연스러움
  - K-AIR는 매번 독립 질문으로 컨텍스트 소실

- SQL 미리보기에서 사용자 수정 허용
  - 근거: AI 생성 SQL이 불완전할 수 있음, 전문 사용자는 직접 수정 가능
  - HITL 원칙 적용

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 2.1 | Axiom Team | RBAC 역할별 접근 제어(§7) 추가 |
| 2026-02-20 | 2.0 | Axiom Team | API 연동(§2) 전면 개편 (text2sql 경로, ReAct NDJSON, 타입 정의), UX 상태 설계(§6) 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
