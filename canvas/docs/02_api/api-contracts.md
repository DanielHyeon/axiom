# API 호출 규약 (Core / Vision / Oracle / Synapse / Weaver)

<!-- affects: frontend, backend, api -->
<!-- requires-update: 04_frontend/, 06_data/state-schema.md -->

## 이 문서가 답하는 질문

- 각 백엔드 서비스의 주요 엔드포인트는 무엇인가?
- 요청/응답 형식은 어떻게 정의되는가?
- 어떤 필드가 nullable이고, 어떤 필드가 required인가?
- 에러 코드와 그 의미는 무엇인가?

---

## 1. 공통 규약

### 1.1 요청 형식

```
Base URL: {SERVICE_URL}/api/v1
Content-Type: application/json
Authorization: Bearer {accessToken}
X-Tenant-Id: {tenantId}
```

### 1.2 페이지네이션

```
# Query Parameters
?page=1&pageSize=20&sort=createdAt&order=desc

# 응답 meta
{
  "meta": {
    "page": 1,
    "pageSize": 20,
    "total": 142,
    "totalPages": 8
  }
}
```

### 1.3 공통 에러 코드

| HTTP | 코드 | 의미 |
|------|------|------|
| 400 | `BAD_REQUEST` | 요청 형식 오류 |
| 401 | `UNAUTHORIZED` | 인증 필요 |
| 403 | `FORBIDDEN` | 권한 부족 |
| 404 | `NOT_FOUND` | 리소스 없음 |
| 409 | `CONFLICT` | 데이터 충돌 (동시 수정) |
| 422 | `VALIDATION_ERROR` | 입력 검증 실패 |
| 429 | `RATE_LIMITED` | 요청 한도 초과 |
| 500 | `INTERNAL_ERROR` | 서버 내부 오류 |

---

## 2. Core 서비스 API

### 2.1 케이스 (Cases)

#### GET /cases - 케이스 목록 조회

```typescript
// Request
GET /api/v1/cases?page=1&pageSize=20&status=active&search=프로젝트A

// Response 200
interface CaseListResponse {
  success: true;
  data: Case[];
  meta: PaginationMeta;
}

interface Case {
  id: string;                    // required, UUID
  caseNumber: string;            // required, "2024-PRJ-100123"
  title: string;                 // required
  type: 'analysis' | 'optimization';  // required
  status: CaseStatus;           // required
  department: string;           // required, 담당 부서
  filingDate: string;           // required, ISO 8601
  closingDate: string | null;   // nullable, 종결일
  assignedTo: string | null;    // nullable, 담당자 ID
  organizationName: string;     // required, 대상 조직명
  totalBudget: number;          // required, 총 예산 (원)
  stakeholderCount: number;     // required, 이해관계자 수
  documentCount: number;        // required, 문서 수
  completionRate: number;       // required, 0-100
  tags: string[];               // required, 빈 배열 가능
  createdAt: string;            // required, ISO 8601
  updatedAt: string;            // required, ISO 8601
}

type CaseStatus =
  | 'draft'          // 초안
  | 'filed'          // 접수됨
  | 'in_progress'    // 진행 중
  | 'review'         // 검토 중
  | 'approved'       // 승인됨
  | 'closed'         // 종결
  | 'archived';      // 보관
```

#### GET /cases/:id - 케이스 상세

```typescript
// Response 200
interface CaseDetailResponse {
  success: true;
  data: CaseDetail;
}

interface CaseDetail extends Case {
  description: string | null;           // nullable
  assignee: UserSummary | null;         // nullable
  timeline: TimelineEvent[];            // required, 빈 배열 가능
  relatedCases: string[];               // related case IDs
  metadata: Record<string, unknown>;    // 확장 필드
}
```

#### POST /cases - 케이스 생성

```typescript
// Request Body
interface CreateCaseRequest {
  title: string;                // required, 1-200자
  type: 'analysis' | 'optimization';  // required
  department: string;           // required
  filingDate: string;           // required, ISO 8601
  organizationName: string;     // required
  description?: string;         // optional
  tags?: string[];              // optional
}

// Response 201
// 에러: VALIDATION_ERROR (422), CONFLICT (409 - 중복 케이스 번호)
```

### 2.2 문서 (Documents)

#### GET /cases/:caseId/documents - 케이스별 문서 목록

```typescript
interface Document {
  id: string;                    // required
  caseId: string;                // required
  title: string;                 // required
  type: DocumentType;            // required
  status: DocumentStatus;        // required
  version: number;               // required, 1부터 시작
  aiGenerated: boolean;          // required, AI 생성 여부
  content: string | null;        // nullable (목록에서는 null)
  reviewStatus: ReviewStatus | null;  // nullable
  createdBy: string;             // required, 생성자 ID
  createdAt: string;             // required
  updatedAt: string;             // required
}

type DocumentType =
  | 'petition'           // 신청서
  | 'stakeholder_list'   // 이해관계자 목록
  | 'asset_report'       // 자산 보고서
  | 'execution_plan'     // 실행 계획서
  | 'decision_order'     // 의사결정 지시서
  | 'meeting_minutes'    // 회의록
  | 'analysis_report'    // 분석 보고서
  | 'other';

type DocumentStatus = 'draft' | 'in_review' | 'approved' | 'rejected' | 'archived';
type ReviewStatus = 'pending' | 'in_progress' | 'completed' | 'changes_requested';
```

### 2.3 리뷰 (Reviews) - HITL

#### POST /documents/:docId/reviews - 리뷰 시작

```typescript
// Request Body
interface CreateReviewRequest {
  reviewerIds: string[];     // required, 1명 이상
  dueDate?: string;          // optional, ISO 8601
  instructions?: string;     // optional, 리뷰 지침
}

// Response 201
interface Review {
  id: string;
  documentId: string;
  status: 'pending' | 'in_progress' | 'completed';
  reviewers: ReviewerInfo[];
  comments: ReviewComment[];
  createdAt: string;
}
```

#### POST /reviews/:reviewId/comments - 인라인 코멘트 추가

```typescript
interface CreateCommentRequest {
  content: string;           // required, 코멘트 내용
  lineStart: number;         // required, 시작 줄 번호
  lineEnd: number;           // required, 끝 줄 번호
  type: 'comment' | 'suggestion' | 'issue';  // required
  severity?: 'info' | 'warning' | 'critical';  // optional
}
```

### 2.4 사용자 (Users)

#### GET /users/me - 현재 사용자 정보

```typescript
interface CurrentUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  tenantId: string;
  avatar: string | null;        // nullable
  permissions: string[];        // required
  preferences: UserPreferences; // required
  createdAt: string;
}

type UserRole = 'admin' | 'manager' | 'legal' | 'analyst' | 'engineer' | 'viewer';
```

---

## 3. Vision 서비스 API

### 3.1 시나리오 (Scenarios) - What-if

#### POST /scenarios/analyze - What-if 분석 실행

```typescript
// Request Body
interface AnalyzeScenarioRequest {
  caseId: string;                    // required
  baseScenarioId?: string;           // optional, 기준 시나리오
  parameters: ScenarioParameter[];   // required, 1개 이상
}

interface ScenarioParameter {
  name: string;              // required, "비용배분율", "달성률"
  baseValue: number;         // required, 기준값
  adjustedValue: number;     // required, 변경값
  unit: string;              // required, "%", "원", "건"
  min: number;               // required, 슬라이더 최솟값
  max: number;               // required, 슬라이더 최댓값
  step: number;              // required, 슬라이더 단위
}

// Response 200
interface ScenarioResult {
  id: string;
  caseId: string;
  parameters: ScenarioParameter[];
  outcomes: ScenarioOutcome[];       // 결과 지표들
  sensitivity: SensitivityData[];    // 토네이도 차트 데이터
  createdAt: string;
}

interface ScenarioOutcome {
  metric: string;            // "총 비용절감액", "이해관계자 만족도"
  baseValue: number;
  adjustedValue: number;
  changePercent: number;
  unit: string;
}

interface SensitivityData {
  parameterName: string;
  lowValue: number;          // 최소 변동 시 결과
  highValue: number;         // 최대 변동 시 결과
  baseValue: number;
  impact: number;            // 영향도 (정렬 기준)
}
```

### 3.2 OLAP

#### GET /olap/cubes - 사용 가능한 큐브 목록

```typescript
interface OlapCube {
  id: string;
  name: string;                   // "재무제표 분석", "비용 현황"
  description: string;
  dimensions: CubeDimension[];    // 사용 가능한 차원
  measures: CubeMeasure[];        // 사용 가능한 측정값
  updatedAt: string;
}

interface CubeDimension {
  id: string;
  name: string;              // "기간", "프로세스 유형", "부서"
  type: 'time' | 'category' | 'hierarchy';
  levels?: string[];         // 계층: ["년", "분기", "월"]
}

interface CubeMeasure {
  id: string;
  name: string;              // "비용 합계", "이해관계자 수"
  aggregation: 'sum' | 'avg' | 'count' | 'min' | 'max';
  format: 'number' | 'currency' | 'percent';
}
```

#### POST /olap/query - OLAP 쿼리 실행

```typescript
// Request Body
interface OlapQueryRequest {
  cubeId: string;                    // required
  rows: string[];                    // required, 차원 ID 배열
  columns: string[];                 // required, 차원 ID 배열
  measures: string[];                // required, 측정값 ID 배열
  filters: OlapFilter[];             // required, 빈 배열 가능
  drilldownPath?: string[];          // optional, 드릴다운 경로
  limit?: number;                    // optional, 기본 1000
}

interface OlapFilter {
  dimensionId: string;
  operator: 'eq' | 'in' | 'between' | 'gt' | 'lt';
  value: unknown;
}

// Response 200
interface OlapQueryResult {
  headers: { rows: string[]; columns: string[]; measures: string[] };
  data: OlapCell[][];
  totals: { row: number[]; column: number[]; grand: number[] };
  rowCount: number;
  queryTime: number;                 // ms
}

interface OlapCell {
  value: number | null;
  formatted: string;                 // "1,234,567원"
}
```

---

## 4. Oracle 서비스 API

### 4.1 NL2SQL

#### POST /nl2sql/ask - 자연어 질의 (SSE 스트리밍)

```typescript
// Request Body
interface Nl2SqlRequest {
  question: string;              // required, 자연어 질문
  datasourceId?: string;         // optional, 특정 데이터소스
  context?: string[];            // optional, 이전 대화 컨텍스트
  maxRows?: number;              // optional, 기본 100
}

// Response: SSE Stream
// event: thinking
data: { "type": "thinking", "content": "질문을 분석하고 있습니다..." }

// event: sql_generated
data: { "type": "sql_generated", "sql": "SELECT ...", "explanation": "..." }

// event: executing
data: { "type": "executing", "content": "쿼리를 실행하고 있습니다..." }

// event: result
data: {
  "type": "result",
  "columns": ["조직명", "비용효율", "자산총계"],
  "rows": [["삼성전자", 42.3, 3800000000], ...],
  "rowCount": 10,
  "queryTime": 1234,
  "chartRecommendation": "bar"
}

// event: done
data: [DONE]
```

#### GET /nl2sql/history - 쿼리 히스토리

```typescript
interface QueryHistoryItem {
  id: string;
  question: string;
  sql: string;
  rowCount: number;
  executedAt: string;
  isSaved: boolean;              // 사용자가 저장 표시
  datasourceId: string;
}
```

---

## 5. Synapse 서비스 API

### 5.1 온톨로지

#### GET /ontology/graph - 온톨로지 그래프 조회

```typescript
// Query: ?depth=2&rootNodeId=xxx&layers=kpi,measure,process,resource

interface OntologyGraph {
  nodes: OntologyNode[];
  edges: OntologyEdge[];
  stats: {
    totalNodes: number;
    totalEdges: number;
    layerCounts: Record<OntologyLayer, number>;
  };
}

interface OntologyNode {
  id: string;
  label: string;                     // 표시 이름
  layer: OntologyLayer;              // 계층
  type: string;                      // 세부 유형
  properties: Record<string, unknown>;
  x?: number;                        // nullable, 저장된 위치
  y?: number;                        // nullable
}

type OntologyLayer = 'kpi' | 'measure' | 'process' | 'resource';

interface OntologyEdge {
  id: string;
  source: string;                    // source node ID
  target: string;                    // target node ID
  relationship: string;              // "참여", "측정", "달성"
  weight?: number;                   // nullable, 관계 강도
}
```

#### GET /ontology/paths - 노드 간 경로 탐색

```typescript
// Query: ?from=nodeA&to=nodeB&maxHops=3
interface PathResult {
  paths: OntologyPath[];
  shortestPathLength: number;
}

interface OntologyPath {
  nodes: string[];                   // 노드 ID 배열 (경로 순서)
  edges: string[];                   // 엣지 ID 배열
  length: number;                    // 홉 수
}
```

---

## 6. Weaver 서비스 API

### 6.1 데이터소스

#### GET /datasources - 데이터소스 목록

```typescript
interface DataSource {
  id: string;
  name: string;                      // "운영 PostgreSQL", "레거시 Oracle"
  type: 'postgresql' | 'mysql' | 'oracle' | 'mssql';
  host: string;
  port: number;
  database: string;
  status: 'connected' | 'disconnected' | 'syncing' | 'error';
  lastSyncAt: string | null;         // nullable
  tableCount: number;
  columnCount: number;
  createdAt: string;
}
```

#### POST /datasources - 데이터소스 등록

```typescript
interface CreateDatasourceRequest {
  name: string;                      // required
  type: 'postgresql' | 'mysql' | 'oracle' | 'mssql';  // required
  host: string;                      // required
  port: number;                      // required
  database: string;                  // required
  username: string;                  // required
  password: string;                  // required (전송 후 저장 시 암호화)
  schema?: string;                   // optional
  options?: Record<string, string>;  // optional, SSL 등
}

// Response 201
// 에러: VALIDATION_ERROR (422), CONNECTION_FAILED (400 - 연결 실패)
```

#### POST /datasources/:id/sync - 메타데이터 동기화 (SSE)

```typescript
// Response: SSE Stream
// event: progress
data: { "type": "progress", "stage": "tables", "current": 12, "total": 45, "percent": 26.7 }
data: { "type": "progress", "stage": "columns", "current": 156, "total": 890, "percent": 17.5 }
data: { "type": "progress", "stage": "indexes", "current": 30, "total": 120, "percent": 25.0 }

// event: complete
data: { "type": "complete", "summary": { "tables": 45, "columns": 890, "indexes": 120 } }

// event: error
data: { "type": "error", "message": "테이블 접근 권한 부족: public.sensitive_data" }
```

---

## 결정 사항 (Decisions)

- 모든 API는 `ApiResponse<T>` 래퍼 형식을 따름
  - 근거: 일관된 에러 처리, TanStack Query 통합 단순화
  - K-AIR는 각 서비스가 다른 응답 형식 사용 -> 어댑터 복잡

- nullable 필드를 `null`로 표현 (undefined 아님)
  - 근거: JSON 직렬화 일관성, TypeScript strict null check 활용

## 사실 (Facts)

- 5개 서비스 합계 약 50+ 엔드포인트 예상
- SSE 스트리밍은 Oracle, Weaver 2개 서비스만 사용
- WebSocket은 Core 서비스만 제공

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
