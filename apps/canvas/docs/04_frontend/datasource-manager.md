# 데이터소스 관리 UI

<!-- affects: frontend, api -->
<!-- requires-update: 02_api/api-contracts.md (Weaver API) -->

## 이 문서가 답하는 질문

- 데이터소스 관리 UI의 화면 구성은 어떻게 되는가?
- 데이터소스 연결/테스트/동기화 흐름은?
- SSE 기반 동기화 진행률은 어떻게 표시하는가?
- K-AIR robo-data-fabric/frontend에서 무엇이 달라지는가?

---

## 1. 화면 와이어프레임

```
┌──────────────────────────────────────────────────────────────────────┐
│ 🔌 데이터소스 관리                                  [+ 새 데이터소스]│
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─── 데이터소스 목록 ──────────────────────────────────────────┐   │
│  │                                                               │   │
│  │  ┌─ 운영 PostgreSQL ───────────────────────── ● 연결됨 ──┐  │   │
│  │  │  호스트: db-prod.axiom.kr:5432                          │  │   │
│  │  │  DB: axiom_prod │ 테이블: 45 │ 컬럼: 890               │  │   │
│  │  │  최종 동기화: 2024-03-10 14:30                          │  │   │
│  │  │  [스키마 보기] [동기화] [편집] [삭제]                   │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  ┌─ 레거시 Oracle ─────────────────────────── ◐ 동기화중 ─┐  │   │
│  │  │  호스트: oracle-legacy.axiom.kr:1521                    │  │   │
│  │  │  DB: LEGACY_DB │ 테이블: 120 │ 컬럼: 2,340             │  │   │
│  │  │  동기화 진행: ████████░░░░░░░░░ 52% (테이블)           │  │   │
│  │  │  [스키마 보기] [동기화 취소] [편집]                     │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  │  ┌─ 개발 MySQL ────────────────────────────── ✖ 오류 ─────┐  │   │
│  │  │  호스트: mysql-dev.axiom.kr:3306                        │  │   │
│  │  │  오류: Connection refused                               │  │   │
│  │  │  [재연결] [편집] [삭제]                                 │  │   │
│  │  └──────────────────────────────────────────────────────────┘  │   │
│  │                                                               │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─── 스키마 탐색기 (선택된 데이터소스) ────────────────────────┐   │
│  │                                                               │   │
│  │  📁 public                                                    │   │
│  │  ├── 📋 cases (12 컬럼)                                      │   │
│  │  │   ├── id: uuid (PK)                                       │   │
│  │  │   ├── case_number: varchar(50) (NOT NULL, UNIQUE)          │   │
│  │  │   ├── title: varchar(200) (NOT NULL)                       │   │
│  │  │   ├── type: varchar(20) (NOT NULL)                         │   │
│  │  │   ├── status: varchar(20) (NOT NULL)                       │   │
│  │  │   └── ... (7 more)                                        │   │
│  │  ├── 📋 documents (15 컬럼)                                   │   │
│  │  ├── 📋 financial_statements (22 컬럼)                        │   │
│  │  └── 📋 ... (42 more tables)                                 │   │
│  │                                                               │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. 연결 폼

```
┌──── 새 데이터소스 연결 ──────────────────────────────┐
│                                                       │
│  데이터소스 이름 *                                    │
│  [                                               ]   │
│                                                       │
│  데이터베이스 유형 *                                  │
│  [PostgreSQL ▼]                                      │
│                                                       │
│  호스트 *                        포트 *               │
│  [db.example.com          ]     [5432       ]        │
│                                                       │
│  데이터베이스 *                                       │
│  [my_database                                    ]   │
│                                                       │
│  사용자명 *                      비밀번호 *           │
│  [admin                   ]     [••••••••••]         │
│                                                       │
│  스키마 (선택)                                        │
│  [public                                         ]   │
│                                                       │
│  ▼ 고급 옵션                                         │
│    SSL 모드: [prefer ▼]                              │
│    연결 타임아웃: [30] 초                             │
│                                                       │
│         [연결 테스트]  [취소]  [연결 저장]            │
│                                                       │
│  ✓ 연결 테스트 성공 (응답시간: 45ms)                 │
│                                                       │
└───────────────────────────────────────────────────────┘
```

---

## 3. SSE 동기화 진행률

```
동기화 중...

단계 1/3: 테이블 스캔
████████████████████████████████░░░░░░░░  78% (35/45)

단계 2/3: 컬럼 분석
대기 중...

단계 3/3: 인덱스 수집
대기 중...

예상 소요 시간: 약 2분
[동기화 취소]
```

### SSE 이벤트 처리

```typescript
// hooks/useMetadataSync.ts

function useMetadataSync(datasourceId: string) {
  const [progress, setProgress] = useState<SyncProgress | null>(null);

  const startSync = useCallback(() => {
    const cleanup = createSSEConnection({
      url: `${WEAVER_URL}/api/v1/datasources/${datasourceId}/sync`,
      onMessage: (type, data) => {
        if (type === 'progress') {
          setProgress({
            stage: data.stage,
            current: data.current,
            total: data.total,
            percent: data.percent,
          });
        } else if (type === 'complete') {
          setProgress(null);
          queryClient.invalidateQueries({
            queryKey: ['datasources', datasourceId]
          });
          toast.success('메타데이터 동기화가 완료되었습니다.');
        } else if (type === 'error') {
          toast.error(`동기화 오류: ${data.message}`);
        }
      },
    });

    return cleanup;
  }, [datasourceId]);

  return { progress, startSync };
}
```

---

## 4. 컴포넌트 분해

```
DatasourcePage
├── DatasourceList
│   ├── DatasourceCard (x N)
│   │   ├── StatusIndicator (●/◐/✖)
│   │   ├── ConnectionInfo
│   │   ├── SyncProgress (SSE 진행률)
│   │   └── ActionButtons
│   └── AddButton
├── ConnectionForm (Dialog)
│   ├── shared/ui/Input (x 필드)
│   ├── shared/ui/Select (DB 유형)
│   ├── TestConnectionButton
│   └── FormActions (취소/저장)
├── SchemaExplorer (선택 시 표시)
│   └── MetadataTree
│       ├── SchemaNode (📁)
│       ├── TableNode (📋)
│       └── ColumnNode (필드 상세)
└── SyncProgress (SSE 연동)
    └── ProgressBar + 단계 표시
```

---

## 5. 타입 정의

```typescript
// features/datasource/types/datasource.ts

/** 데이터소스 연결 상태 */
type DatasourceStatus = 'connected' | 'syncing' | 'error' | 'disconnected';

/** 지원하는 데이터베이스 유형 */
type DatabaseType = 'postgresql' | 'mysql' | 'oracle' | 'mssql';

/** 동기화 진행 상태 — SSE 이벤트로 수신 */
interface SyncProgress {
  datasource_id: string;
  stage: 'tables' | 'columns' | 'indexes';   // 현재 동기화 단계
  stage_number: number;                        // 1, 2, 3
  total_stages: number;                        // 3
  current: number;                             // 현재 항목 인덱스
  total: number;                               // 해당 단계 전체 항목 수
  percent: number;                             // 0-100
  estimated_seconds?: number;                  // 예상 남은 시간
}

/** 데이터소스 객체 — Weaver API GET /datasources 응답 항목 */
interface Datasource {
  id: string;
  name: string;
  db_type: DatabaseType;
  host: string;
  port: number;
  database: string;
  schema?: string;
  status: DatasourceStatus;
  table_count: number;
  column_count: number;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}
```

---

## 6. API 연동

### 6.1 백엔드 엔드포인트

데이터소스 관리 UI는 Weaver 서비스의 API를 사용한다.

| 기능 | Method | Path | 설명 |
|------|--------|------|------|
| 목록 조회 | GET | `/api/v1/datasources` | 전체 데이터소스 목록 |
| 상세 조회 | GET | `/api/v1/datasources/{id}` | 데이터소스 상세 정보 |
| 연결 생성 | POST | `/api/v1/datasources` | 새 데이터소스 연결 |
| 연결 수정 | PUT | `/api/v1/datasources/{id}` | 연결 정보 수정 |
| 연결 삭제 | DELETE | `/api/v1/datasources/{id}` | 데이터소스 삭제 |
| 연결 테스트 | POST | `/api/v1/datasources/{id}/test` | 연결 유효성 확인 |
| 스키마 동기화 | POST | `/api/v1/datasources/{id}/sync` | SSE 스트림으로 진행률 반환 |
| 스키마 조회 | GET | `/api/v1/datasources/{id}/schema` | 테이블/컬럼 메타데이터 |

- **라우팅**: Core API Gateway를 통해 Weaver 서비스로 프록시됨
- **SSE 동기화**: `/sync`는 `text/event-stream`으로 `progress`, `complete`, `error` 이벤트를 발행

> **백엔드 협의 필요**: 위 엔드포인트 목록은 프론트엔드 요구사항 기반 설계이다. Weaver API의 실제 스펙이 확정되면 경로/필드를 동기화해야 한다.

---

## 7. UX 상태 설계 (에러/빈 상태/로딩)

### 7.1 에러 상태

| 시나리오 | UI 표시 | 액션 |
|---------|---------|------|
| 데이터소스 목록 조회 실패 | ErrorFallback + "다시 시도" 버튼 | `queryClient.invalidateQueries(['datasources'])` |
| 연결 테스트 실패 | 인라인 에러 "연결에 실패했습니다: {message}" | 설정 수정 유도 |
| 동기화 중 오류 | 카드에 `✖ 오류` 배지 + 에러 메시지 | "재동기화" 버튼 |
| 연결 삭제 실패 | 토스트 에러 | 재시도 유도 |

### 7.2 빈 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 데이터소스 없음 | EmptyState: 아이콘 + "등록된 데이터소스가 없습니다" + [+ 새 데이터소스] 버튼 |
| 스키마 탐색 — 테이블 없음 | "이 데이터소스에 접근 가능한 테이블이 없습니다. 스키마 설정을 확인하세요." |
| 검색 결과 없음 | "'{query}'에 해당하는 데이터소스가 없습니다." |

### 7.3 로딩 상태

| 시나리오 | UI 표시 |
|---------|---------|
| 목록 조회 중 | DatasourceCardSkeleton x 3 (카드 레이아웃 유지) |
| 연결 테스트 중 | 버튼 스피너 + "테스트 중..." + 버튼 비활성 |
| 스키마 동기화 중 | ProgressBar (3단계) + 예상 시간 + "동기화 취소" 버튼 |
| 스키마 트리 조회 중 | Skeleton 트리 3단 (스키마/테이블/컬럼) |

---

## 8. 역할별 접근 제어 (RBAC)

### 8.1 기능별 역할 권한

| 기능 | 필요 권한 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------|----------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| 데이터소스 목록/상세 조회 | `datasource:read` | O | O | O | O | O | O | O |
| 스키마 탐색 (읽기) | `schema:read` | O | O | O | O | O | O | O |
| 데이터소스 생성/수정 | `datasource:manage` | O | X | X | X | O | X | X |
| 데이터소스 삭제 | `datasource:manage` | O | X | X | X | O | X | X |
| 연결 테스트 | `datasource:manage` | O | X | X | X | O | X | X |
| 스키마 동기화 | `datasource:manage` | O | X | X | X | O | X | X |
| 스키마 편집 | `schema:edit` | O | X | X | X | O | X | X |

### 8.2 프론트엔드 가드

```typescript
// 데이터소스 목록은 모든 역할이 조회 가능 (datasource:read)
// 생성/수정/삭제 버튼은 datasource:manage 권한이 있는 역할에만 표시
const { hasPermission } = usePermission();
const canManage = hasPermission('datasource:manage');

{canManage && <Button onClick={openConnectionForm}>+ 새 데이터소스</Button>}

// DatasourceCard 내 버튼
<Button onClick={onSync} disabled={!canManage}>동기화</Button>
<Button onClick={onEdit} disabled={!canManage}>편집</Button>
{canManage && <Button variant="destructive" onClick={onDelete}>삭제</Button>}
```

> **설계 원칙**: 읽기 권한(`datasource:read`, `schema:read`)은 모든 역할에 부여한다. analyst와 attorney가 쿼리 대상 테이블 구조를 확인할 수 있어야 NL2SQL/OLAP 분석이 원활하다. 관리 권한은 admin과 engineer에만 부여하여 데이터 인프라 안정성을 보장한다.
> **SSOT**: `services/core/docs/07_security/auth-model.md` §2.3

---

## 9. K-AIR 전환 노트

| K-AIR (robo-data-fabric/frontend) | Canvas | 전환 노트 |
|-----------------------------------|--------|-----------|
| `DataSources.vue` | DatasourceList + DatasourceCard | Headless UI -> Shadcn/ui |
| `Dashboard.vue` | DatasourcePage 통합 | 별도 대시보드 불필요 |
| Pinia `useDatasourcesStore` | TanStack Query `useDatasources()` | 서버 상태 분리 |
| Axios `datasourcesApi` | Weaver API 클라이언트 | createApiClient 활용 |
| MindsDB 직접 연동 | Weaver API 뒤에 숨김 | 보안 강화 |
| SSE: 없음 (폴링) | SSE 진행률 스트리밍 | UX 개선 |

---

## 결정 사항 (Decisions)

- 비밀번호는 연결 저장 시 Weaver API에서 암호화, 프론트엔드에서 재표시하지 않음
- 스키마 탐색기는 Lazy 로딩 (테이블 클릭 시 컬럼 조회)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 2.1 | Axiom Team | RBAC 역할별 접근 제어(§8) 추가 |
| 2026-02-20 | 2.0 | Axiom Team | 타입 정의(§5), API 연동(§6), UX 상태 설계(§7) 추가 |
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
