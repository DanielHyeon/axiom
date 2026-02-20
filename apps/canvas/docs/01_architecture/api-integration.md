# 5개 백엔드 서비스 API 통합 구조

<!-- affects: api, frontend, backend -->
<!-- requires-update: 02_api/api-client.md, 02_api/api-contracts.md -->

## 이 문서가 답하는 질문

- Canvas는 5개 백엔드 서비스와 어떻게 통신하는가?
- 각 서비스의 책임 경계는 어디인가?
- 서비스 간 데이터 흐름은 어떤 패턴을 따르는가?
- K-AIR의 BackendFactory 패턴은 어떻게 단순화되는가?

---

## 1. 서비스 토폴로지

### 1.1 Canvas -> 백엔드 서비스 관계도

```
                        ┌─────────────────────┐
                        │    Axiom Canvas      │
                        │    (React SPA)       │
                        └──┬──┬──┬──┬──┬──────┘
                           │  │  │  │  │
              ┌────────────┘  │  │  │  └────────────┐
              │     ┌─────────┘  │  └─────────┐     │
              │     │            │             │     │
              ▼     ▼            ▼             ▼     ▼
        ┌──────┐ ┌──────┐ ┌──────────┐ ┌────────┐ ┌──────┐
        │ Core │ │Vision│ │  Oracle  │ │Synapse │ │Weaver│
        │      │ │      │ │          │ │        │ │      │
        │ REST │ │ REST │ │ REST+SSE │ │  REST  │ │REST  │
        │ + WS │ │      │ │          │ │        │ │+SSE  │
        └──┬───┘ └──┬───┘ └────┬─────┘ └───┬────┘ └──┬───┘
           │        │          │            │         │
           ▼        ▼          ▼            ▼         ▼
        ┌──────────────────────────────────────────────┐
        │              공유 인프라                       │
        │  PostgreSQL │ Neo4j │ Redis │ Object Store   │
        └──────────────────────────────────────────────┘

                        ┌─────────────────────┐
                        │    Axiom Canvas      │
                        └──────────┬──────────┘
                                   │
                                   ▼
                        ┌──────────────────────┐
                        │  Yjs WebSocket Server │
                        │  (y-websocket)        │
                        │  CRDT 문서 동기화     │
                        │  + Awareness 프로토콜 │
                        └──────────────────────┘
```

### 1.2 서비스별 상세

| 서비스 | 기본 URL | 프로토콜 | 역할 | K-AIR 대응 |
|--------|----------|----------|------|-----------|
| **Core** | `{CORE_URL}/api/v1` | REST + WebSocket | 케이스, 문서, 사용자, 인증, 알림 | CompleteService + Memento |
| **Vision** | `{VISION_URL}/api/v1` | REST | 시나리오 분석, OLAP 큐브/쿼리 | data-platform-olap 백엔드 |
| **Oracle** | `{ORACLE_URL}/api/v1` | REST + SSE | NL2SQL 변환, 쿼리 실행/스트리밍 | robo-data-text2sql |
| **Synapse** | `{SYNAPSE_URL}/api/v1` | REST | 온톨로지 CRUD, 그래프 탐색, 프로세스 마이닝 | Neo4j 직접 연동 + pm4py |
| **Weaver** | `{WEAVER_URL}/api/v1` | REST + SSE | 데이터소스 연결, 메타데이터 동기화 | robo-data-fabric 백엔드 |

---

## 2. K-AIR BackendFactory -> Canvas 통합 클라이언트

### 2.1 K-AIR의 문제: BackendFactory 패턴

```
// K-AIR: 런타임에 백엔드 선택 (3종 혼재)
const backend = BackendFactory.create(config.backend);
// 'ProcessGPT' | 'uEngine' | 'Pal'

// 문제점:
// 1. 런타임 분기 -> 타입 안전성 약화
// 2. 3개 백엔드의 API 차이 -> 어댑터 복잡
// 3. 프론트엔드가 백엔드 구현을 알아야 함
```

### 2.2 Canvas의 해결: 단일 API 계층

```typescript
// Canvas: 서비스별 전용 Axios 인스턴스 (컴파일 타임 확정)
//
// 각 인스턴스는 baseURL만 다르고, 인터셉터는 공유
//
// lib/api/clients.ts

import { createApiClient } from './createApiClient';

export const coreApi    = createApiClient(import.meta.env.VITE_CORE_URL);
export const visionApi  = createApiClient(import.meta.env.VITE_VISION_URL);
export const oracleApi  = createApiClient(import.meta.env.VITE_ORACLE_URL);
export const synapseApi = createApiClient(import.meta.env.VITE_SYNAPSE_URL);
export const weaverApi  = createApiClient(import.meta.env.VITE_WEAVER_URL);
```

---

## 3. API 호출 흐름

### 3.1 표준 REST 호출

```
Component                Hook                  API Service          Backend
   │                       │                       │                   │
   │  useQuery(key, fn)    │                       │                   │
   │──────────────────────▶│                       │                   │
   │                       │  apiService.getList()  │                   │
   │                       │──────────────────────▶│                   │
   │                       │                       │  GET /api/v1/res  │
   │                       │                       │──────────────────▶│
   │                       │                       │                   │
   │                       │                       │  200 { data: [] } │
   │                       │                       │◀──────────────────│
   │                       │  return data           │                   │
   │                       │◀──────────────────────│                   │
   │  { data, isLoading }  │                       │                   │
   │◀──────────────────────│                       │                   │
   │                       │                       │                   │
   │  렌더링               │                       │                   │
```

### 3.2 SSE 스트리밍 호출 (NL2SQL, 데이터 동기화)

```
Component                Hook                  SSE Manager          Oracle
   │                       │                       │                   │
   │  useNl2sql(question)  │                       │                   │
   │──────────────────────▶│                       │                   │
   │                       │  sseManager.connect()  │                   │
   │                       │──────────────────────▶│                   │
   │                       │                       │  POST /nl2sql/ask │
   │                       │                       │──────────────────▶│
   │                       │                       │                   │
   │                       │                       │  SSE: thinking... │
   │                       │                       │◀──────────────────│
   │  status: 'thinking'   │◀─────────────────────│                   │
   │                       │                       │                   │
   │                       │                       │  SSE: sql_ready   │
   │                       │                       │◀──────────────────│
   │  status: 'sql_ready'  │◀─────────────────────│                   │
   │  sql: SELECT ...      │                       │                   │
   │                       │                       │                   │
   │                       │                       │  SSE: result      │
   │                       │                       │◀──────────────────│
   │  status: 'complete'   │◀─────────────────────│                   │
   │  data: [rows...]      │                       │                   │
   │                       │                       │  SSE: [DONE]      │
   │  렌더링 완료          │                       │◀──────────────────│
```

### 3.3 WebSocket 실시간 이벤트 (Watch 알림)

```
Canvas App               WS Manager             Core WS              Core
   │                       │                       │                   │
   │  앱 초기화 시          │                       │                   │
   │  useWebSocketSync()   │                       │                   │
   │──────────────────────▶│                       │                   │
   │                       │  ws.connect(token)    │                   │
   │                       │──────────────────────▶│                   │
   │                       │                       │  인증 + 구독      │
   │                       │                       │──────────────────▶│
   │                       │                       │                   │
   │                       │        ... 시간 경과 ...                  │
   │                       │                       │                   │
   │                       │                       │  case:updated     │
   │                       │                       │◀──────────────────│
   │                       │  event: case:updated  │                   │
   │                       │◀──────────────────────│                   │
   │                       │                       │                   │
   │  invalidateQueries    │                       │                   │
   │◀──────────────────────│                       │                   │
   │                       │                       │                   │
   │  자동 refetch         │                       │                   │
   │  UI 갱신              │                       │                   │
```

---

## 4. 서비스 간 데이터 흐름

### 4.1 Canvas 관점의 Cross-Service 시나리오

#### 시나리오 1: 케이스 상세 페이지

```
케이스 상세 페이지 로드 시 (병렬 호출):

Canvas ──→ Core:    GET /cases/{id}           # 케이스 기본 정보
Canvas ──→ Core:    GET /cases/{id}/documents  # 관련 문서 목록
Canvas ──→ Core:    GET /cases/{id}/timeline   # 이벤트 타임라인
Canvas ──→ Vision:  GET /scenarios?caseId={id}  # 관련 시나리오
Canvas ──→ Synapse: GET /ontology/nodes?caseId={id}  # 관련 온톨로지
```

#### 시나리오 2: NL2SQL 질의 -> OLAP 전환

```
1. Canvas ──→ Oracle:  POST /nl2sql/ask        # "지난 분기 부채비율은?"
2. Oracle ──→ Canvas:  SSE 스트리밍 (SQL + 결과)
3. 사용자가 "피벗 분석으로 보기" 클릭
4. Canvas ──→ Vision:  POST /olap/query         # 동일 데이터를 피벗으로
5. Vision ──→ Canvas:  피벗 결과 반환
```

#### 시나리오 3: 비즈니스 프로세스 디자이너 프로세스 마이닝 연동

```
1. Canvas ──→ Core:     GET /boards/{id}               # 보드 메타데이터 조회
2. Canvas ◄──► Yjs WS:  y-websocket (CRDT 동기화)       # 캔버스 데이터 실시간 협업
3. 사용자가 이벤트 로그를 바인딩
4. Canvas ──→ Synapse:  POST /process-mining/discover    # pm4py 프로세스 발견
5. Synapse ──→ Canvas:  프로세스 모델 + 적합도 결과 반환
6. Canvas:   프로세스 마이닝 결과 캔버스 오버레이 (병목 빨간색, 이탈 점선)
7. Canvas ──→ Synapse:  GET /process-mining/conformance  # 적합도 검사
8. Canvas ──→ Synapse:  GET /process-mining/bottlenecks   # 병목 분석
```

#### 시나리오 4: 데이터소스 등록 -> 온톨로지 반영

```
1. Canvas ──→ Weaver:  POST /datasources       # 새 DB 연결
2. Weaver ──→ Canvas:  SSE (메타데이터 동기화 진행률)
3. 동기화 완료 이벤트 수신
4. Canvas ──→ Synapse: POST /ontology/sync      # 온톨로지 갱신 트리거
5. Canvas:   invalidateQueries(['ontology'])    # 그래프 새로고침
```

### 4.2 API 응답 표준 형식

```typescript
// 모든 서비스가 따르는 응답 형식
interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta?: {
    page?: number;
    pageSize?: number;
    total?: number;
    totalPages?: number;
  };
  error?: {
    code: string;         // 'CASE_NOT_FOUND', 'VALIDATION_ERROR'
    message: string;      // 사용자 표시용 메시지
    details?: Record<string, string[]>;  // 필드별 에러
  };
}
```

---

## 5. 환경 설정

### 5.1 환경 변수

> 포트/엔드포인트 기준: [`docs/service-endpoints-ssot.md`](../../../../docs/service-endpoints-ssot.md)

```bash
# .env.development
VITE_CORE_URL=http://localhost:8000
VITE_VISION_URL=http://localhost:8400
VITE_ORACLE_URL=http://localhost:8002
VITE_SYNAPSE_URL=http://localhost:8003
VITE_WEAVER_URL=http://localhost:8001
VITE_WS_URL=ws://localhost:8000/ws
VITE_YJS_WS_URL=ws://localhost:1234              # Yjs WebSocket (y-websocket)

# .env.staging
VITE_CORE_URL=https://api-staging.axiom.kr/core
VITE_VISION_URL=https://api-staging.axiom.kr/vision
VITE_ORACLE_URL=https://api-staging.axiom.kr/oracle
VITE_SYNAPSE_URL=https://api-staging.axiom.kr/synapse
VITE_WEAVER_URL=https://api-staging.axiom.kr/weaver
VITE_WS_URL=wss://api-staging.axiom.kr/ws
VITE_YJS_WS_URL=wss://yjs-staging.axiom.kr       # Yjs WebSocket (y-websocket)

# .env.production
VITE_CORE_URL=https://api.axiom.kr/core
VITE_VISION_URL=https://api.axiom.kr/vision
VITE_ORACLE_URL=https://api.axiom.kr/oracle
VITE_SYNAPSE_URL=https://api.axiom.kr/synapse
VITE_WEAVER_URL=https://api.axiom.kr/weaver
VITE_WS_URL=wss://api.axiom.kr/ws
VITE_YJS_WS_URL=wss://yjs.axiom.kr               # Yjs WebSocket (y-websocket)
```

### 5.2 K-AIR 환경 설정 차이

| K-AIR | Canvas |
|-------|--------|
| `BackendFactory.create(config.backend)` 런타임 선택 | 환경 변수로 컴파일 타임 확정 |
| Keycloak URL 설정 | JWT 토큰 기반 (Core 서비스 위임) |
| Socket.io 서버 URL 별도 | WebSocket URL 환경 변수 통합 |
| MindsDB URL 직접 노출 | Weaver API 뒤에 숨김 |

---

## 결정 사항 (Decisions)

- 5개 서비스에 직접 연결 (API Gateway 없음)
  - 근거: 각 서비스가 독립적 관심사를 가지며, 프론트엔드에서 병렬 호출 가능
  - 재평가 조건: CORS 관리 복잡도 증가 시 API Gateway 도입 검토

- 환경 변수로 서비스 URL 관리 (런타임 설정 아님)
  - 근거: K-AIR BackendFactory의 런타임 분기 복잡도 제거, 빌드 타임 타입 안전성 확보

## 금지됨 (Forbidden)

- 프론트엔드에서 서비스 간 직접 조합 (3개 이상 서비스 결과를 합치는 BFF 로직을 프론트엔드에 구현 금지)
- 환경 변수 없이 하드코딩된 URL 사용

## 필수 (Required)

- 모든 API 호출은 `createApiClient`로 생성된 인스턴스를 통해야 함
- 각 서비스의 API 응답은 `ApiResponse<T>` 형식을 따라야 함
- 크로스 서비스 시나리오는 문서화 필수 (이 문서의 섹션 4 참조)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.1 | Axiom Team | Synapse 프로세스 마이닝 API 통합, Yjs WebSocket Provider 추가, 비즈니스 프로세스 디자이너 시나리오 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
