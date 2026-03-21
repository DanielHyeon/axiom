# ADR-033: 통합 스키마 네비게이션 구현 — 구현 완료 문서

<!-- affects: canvas, services/synapse, services/weaver -->
<!-- last-updated: 2026-03-21 -->
<!-- revision: v3 (구현 완료 — 실제 코드 기반 현행화) -->

## 이 문서가 답하는 질문
- robo 모드와 text2sql 모드의 스키마 캔버스를 어떻게 통합 설계했는가?
- 공통 related-tables API를 어떤 서비스에, 어떤 구조로 구현했는가?
- Column 레벨 FK_TO 관계를 테이블 레벨 FK_TO_TABLE로 어떻게 승격했는가?
- 빈 상태(Empty State)를 어떻게 사용자 친화적으로 처리했는가?
- 가중치 스코어링, 허브 테이블 감지, Multi-hop 탐색은 어떻게 동작하는가?
- nodeKey 기반 고유 식별로 동명 테이블(다른 schema/datasource) 충돌을 어떻게 방지하는가?
- 프로젝트/데이터소스 전환 시 상태를 어떻게 리셋하는가?
- tenant_id 기반 멀티테넌트 격리는 어떻게 적용되는가?

---

## 상태
**Implemented** (2026-03-21)

---

## 1. 배경 및 현재 상태

### 1.1 아키텍처

스키마 네비게이션은 `robo`(코드 분석 기반)와 `text2sql`(DB 메타데이터 기반) 두 모드를 하나의 API 계약으로 통합한다.

| 항목 | robo 모드 | text2sql 모드 |
|------|-----------|---------------|
| 데이터 원천 | `:Table` 노드 (`datasource_name` 없음) | `:Table` 노드 (`datasource_name` 있음) |
| API 경로 | `POST /api/v3/synapse/schema-nav/related-tables` (mode=ROBO) | 동일 API (mode=TEXT2SQL) |
| FK 관계 (테이블 레벨) | `(:Table)-[:FK_TO_TABLE]->(:Table)` | 동일 |
| FK 관계 (컬럼 레벨) | 해당 없음 | `(:Column)-[:FK_TO]->(:Column)` (폴백) |
| 관계 생성 시점 | 코드 분석 시 | Weaver metadata 인제스천 시 (`metadata_graph_service.py`) |

### 1.2 Neo4j 스키마 (실제 구현)

```
(:DataSource) -[:HAS_SCHEMA]-> (:Schema) -[:HAS_TABLE]-> (:Table) -[:HAS_COLUMN]-> (:Column)
```

**노드 프로퍼티**:

| 노드 | 프로퍼티 |
|------|----------|
| `:Table` | `tenant_id`, `datasource_name`, `schema_name`, `name` |
| `:Column` | `tenant_id`, `datasource_name`, `schema_name`, `table_name`, `name`, `dtype`, `nullable` |

**관계**:

| 관계 | 레벨 | 설명 |
|------|------|------|
| `FK_TO_TABLE` | Table → Table | Weaver 인제스천 시 자동 생성 (테이블 레벨 FK) |
| `FK_TO` | Column → Column | Weaver 인제스천 시 자동 생성 (컬럼 레벨 FK) |

**모드 구분 기준**: `:Table` 노드의 `datasource_name` 프로퍼티 유무
- ROBO: `datasource_name IS NULL OR datasource_name = ''`
- TEXT2SQL: `datasource_name IS NOT NULL AND datasource_name <> ''`

### 1.3 해결한 문제점

1. **text2sql 모드에서 FK 자동 로드 불가** → 공통 API로 두 모드 통합
2. **컬럼 레벨 FK만 존재 시 테이블 레벨 탐색 불가** → 컬럼 레벨 FK_TO 폴백 로직 구현
3. **빈 상태 UX 부재** → SchemaEmptyState 컴포넌트 구현
4. **모드 선택 정책 부재** → S1-S4 상태 전이 정책 구현
5. **node.id 충돌 위험** → nodeKey 기반 고유 식별자 도입
6. **scope 없는 쿼리** → datasource_name + tenant_id 스코프 필터링
7. **프로젝트 전환 시 잔존 데이터** → 스코프 변경 시 자동 리셋

---

## 2. 요구사항 정리

### 2.1 기능 요구사항 (구현 완료)

| # | 요구사항 | 구현 파일 | 상태 |
|---|---------|----------|------|
| FR-1 | robo/text2sql 모드 역할 명확 분리 | `related_tables_service.py` — `SchemaMode` enum | 구현 완료 |
| FR-2 | 두 모드에서 동일한 탐색 경험 | `schema_navigation.py` — 단일 엔드포인트 | 구현 완료 |
| FR-3 | 내부 라벨 차이를 백엔드가 숨김 | `related_tables_service.py` — Strategy 패턴 | 구현 완료 |
| FR-4 | 빈 상태에 맥락적 안내 메시지 표시 | `SchemaEmptyState.tsx` | 구현 완료 |
| FR-5 | S1-S4 상태 전이 정책 | `useSchemaNavigation.ts` | 구현 완료 |
| FR-6 | `POST /api/v3/synapse/schema-nav/related-tables` | `schema_navigation.py` | 구현 완료 |
| FR-7 | text2sql 모드에서 FK 기반 관련 테이블 자동 로드 | `useSchemaNavigation.ts` — `loadRelatedTables()` | 구현 완료 |
| FR-8 | 테이블 레벨 FK_TO_TABLE 관계 (Weaver 인제스천 시 생성) | `metadata_graph_service.py` | 구현 완료 |
| FR-9 | nodeKey 기반 고유 식별 | `nodeKey.ts` — `buildNodeKey`/`parseNodeKey` | 구현 완료 |
| FR-10 | availability/related-tables API에 datasource/tenant 스코프 | `related_tables_service.py` — `tenant_id` 파라미터 | 구현 완료 |
| FR-11 | 데이터소스 전환 시 store 리셋 | `useSchemaNavigation.ts` — `prevDatasourceRef` 감지 | 구현 완료 |
| FR-12 | 가중치 스코어링 + 허브 감지 + Multi-hop | `related_tables_service.py` — Step 4-1~4-3 | 구현 완료 |

### 2.2 비기능 요구사항 (구현 완료)

| # | 요구사항 | 구현 방식 |
|---|---------|----------|
| NFR-1 | related-tables API 응답 500ms 이내 | Cypher 파라미터 바인딩, 결과 limit |
| NFR-2 | Cypher 인젝션 방지 | 모든 쿼리에 `$` 파라미터 바인딩 사용 |
| NFR-3 | 기존 robo 모드 동작 하위 호환 | 모드별 리졸버 분리 (`_resolve_robo`/`_resolve_text2sql`) |
| NFR-4 | 프론트엔드가 내부 Neo4j 라벨을 직접 참조하지 않음 | API가 `mode: 'ROBO' | 'TEXT2SQL'`만 수용 |
| NFR-5 | 멀티테넌트 격리 | 모든 Cypher 쿼리에 `tenant_id` 조건 |

---

## 3. 아키텍처 개요

### 3.1 서비스 구조

```
Canvas (React SPA — SchemaCanvas.tsx)
    |
    | useSchemaNavigation 훅
    |   → schemaNavigationApi.ts (Synapse API 클라이언트)
    |
    | GET  /api/v3/synapse/schema-nav/availability?datasourceName=...
    | POST /api/v3/synapse/schema-nav/related-tables {
    |   mode, tableName, schemaName, datasourceName, nodeKey,
    |   alreadyLoadedTableIds, limit, depth
    | }
    v
services/synapse (schema_navigation.py 라우터)
    |
    +-- _require_tenant(request)  → tenant_id 추출
    |
    +-- related_tables_service.py (공통 오케스트레이터)
            |
            +-- fetch_schema_availability()
            |       → ROBO/TEXT2SQL 각각 :Table COUNT 쿼리
            |
            +-- fetch_related_tables_unified()
                    |
                    +-- _resolve_robo()
                    |       depth=1: 나가는/들어오는 FK_TO_TABLE 쿼리
                    |       depth>1: [:FK_TO_TABLE*1..N] 가변 경로
                    |
                    +-- _resolve_text2sql()
                    |       1차: _resolve_text2sql_table_level() (FK_TO_TABLE)
                    |       2차: _resolve_text2sql_column_level() (FK_TO 폴백)
                    |
                    +-- _detect_hub_tables()
                    |       HUB_FK_THRESHOLD=10 이상 → autoAddRecommended=false
                    |
                    +-- _compute_score()
                            base_score + fk_bonus - hop_penalty
    v
Neo4j (공유 인스턴스 — neo4j_client)
```

### 3.2 핵심 설계 결정

| 결정 | 선택 | 근거 |
|------|------|------|
| API 호스트 | services/synapse | Neo4j 그래프 데이터의 단일 소유 서비스 |
| API 경로 접두사 | `/api/v3/synapse/schema-nav` | Synapse v3 API 네임스페이스 |
| 모드 분기 | Strategy/Resolver 패턴 | 각 모드의 Cypher 쿼리가 완전히 다름 |
| FK 관계 생성 | Weaver 인제스천 시점 | 쿼리 시 매번 승격 연산 불필요 |
| Empty State | React 컴포넌트 (SchemaEmptyState.tsx) | 서버 왕복 없이 즉각 표시 |
| 노드 식별자 | `nodeKey = ${mode}:${datasource}:${schema}:${table}` | tableName만으로는 동명 테이블 구분 불가 |
| 상태 머신 | `InitialModeStatus: 'idle' | 'loading' | 'resolved' | 'failed'` | 네트워크 오류 시 재시도 가능 |
| 스코프 리셋 | datasourceId 변경 감지 → useEffect | 데이터소스 전환 시 이전 데이터 잔존 방지 |
| 멀티테넌트 | `tenant_id` Cypher 조건 + `_require_tenant()` 가드 | 테넌트 간 데이터 격리 |

---

### 3.3 nodeKey 규격

프론트엔드 node.id와 백엔드 tableId의 공통 계약:

```
nodeKey = ${mode}:${datasource}:${schema}:${table}

예시:
  robo::public:ORDERS              (robo 모드, datasource 없음)
  text2sql:robo_postgres:public:ORDERS
  text2sql:analytics_db:audit:users
```

**프론트엔드 유틸리티** (`canvas/src/shared/utils/nodeKey.ts`):

```typescript
export type SchemaMode = 'robo' | 'text2sql';

export function buildNodeKey(
  mode: SchemaMode,
  datasource: string,
  schema: string,
  tableName: string,
): string {
  return `${mode}:${datasource || ''}:${schema || 'public'}:${tableName}`;
}

export function parseNodeKey(nodeKey: string): {
  mode: SchemaMode;
  datasource: string;
  schema: string;
  tableName: string;
} {
  const parts = nodeKey.split(':');
  const mode = (parts[0] as SchemaMode) || 'text2sql';
  const datasource = parts[1] || '';
  const schema = parts[2] || 'public';
  // 세 번째 콜론 이후 전부가 테이블명 (콜론이 포함될 수 있음)
  const tableName = parts.slice(3).join(':') || '';
  return { mode, datasource, schema, tableName };
}
```

**백엔드 유틸리티** (`services/synapse/app/services/related_tables_service.py`):

```python
def build_node_key(mode: str, datasource: str | None, schema: str | None, table: str) -> str:
    ds = datasource or ""
    sc = schema or "public"
    return f"{mode.lower()}:{ds}:{sc}:{table}"
```

---

## 4. 구현 단계

모든 단계가 구현 완료 상태이다. 각 단계별 실제 구현 파일과 핵심 코드를 기술한다.

---

### 1단계: 모드 분리 + 초기 선택 + Empty State (구현 완료)

---

#### Step 1-1: 스키마 가용성 확인 API (구현 완료)

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `fetch_schema_availability()`
- **API**: `GET /api/v3/synapse/schema-nav/availability?datasourceName=...`
- **라우터**: `services/synapse/app/api/schema_navigation.py` — `get_availability()`

```python
async def fetch_schema_availability(
    datasource_name: str | None = None,
    tenant_id: str = "",
) -> SchemaAvailabilityResponse:
    """Neo4j에서 :Table 노드 개수를 모드별로 세서 돌려준다.

    ROBO 모드: datasource_name이 비어있는 Table 노드 (코드 분석 결과)
    TEXT2SQL 모드: datasource_name이 있는 Table 노드 (DB 메타데이터)
    """
    tid_clause = "AND t.tenant_id = $tid" if tenant_id else ""

    # ROBO: datasource_name이 없는 Table
    robo_query = f"""
    MATCH (t:Table)
    WHERE (t.datasource_name IS NULL OR t.datasource_name = '')
    {tid_clause}
    RETURN count(t) AS cnt
    """

    # TEXT2SQL: datasource_name이 있는 Table (선택적 필터)
    if datasource_name:
        fabric_query = f"""
        MATCH (t:Table)
        WHERE t.datasource_name = $ds AND t.datasource_name <> ''
        {tid_clause}
        RETURN count(t) AS cnt
        """
    else:
        fabric_query = f"""
        MATCH (t:Table)
        WHERE t.datasource_name IS NOT NULL AND t.datasource_name <> ''
        {tid_clause}
        RETURN count(t) AS cnt
        """
```

**라우터 엔드포인트**:

```python
@router.get("/availability")
async def get_availability(
    request: Request,
    datasource_name: str | None = Query(None, alias="datasourceName"),
):
    tenant_id = _require_tenant(request)
    result = await fetch_schema_availability(datasource_name, tenant_id=tenant_id)
    return {"success": True, "data": result.model_dump(by_alias=True)}
```

---

#### Step 1-2: 프론트엔드 가용성 API 클라이언트 (구현 완료)

- **구현 파일**: `canvas/src/shared/api/schemaNavigationApi.ts` — `getSchemaAvailability()`

```typescript
import { synapseApi } from '@/lib/api/clients';
import type { SchemaAvailability } from '@/shared/types/schemaNavigation';

export async function getSchemaAvailability(
  datasourceName?: string,
): Promise<SchemaAvailability> {
  const params: Record<string, string> = {};
  if (datasourceName) params.datasourceName = datasourceName;
  const res = await synapseApi.get('/api/v3/synapse/schema-nav/availability', { params });
  const body = res as unknown as { success: boolean; data?: SchemaAvailability };
  return body.data ?? { robo: { table_count: 0 }, text2sql: { table_count: 0 } };
}
```

---

#### Step 1-3: 상태 전이 정책 (S1-S4) (구현 완료)

- **구현 파일**: `canvas/src/features/nl2sql/hooks/useSchemaNavigation.ts`

TanStack Query로 가용성을 조회하고, 결과에 따라 S1-S4 정책을 적용한다:

```typescript
// --- 가용성 쿼리 (TanStack Query) ---
const { data: availabilityData, error: queryError } = useQuery({
  queryKey: ['schema-nav', 'availability', datasourceId],
  queryFn: () => getSchemaAvailability(datasourceId || undefined),
  enabled: !!datasourceId && modeStatus !== 'resolved',
  staleTime: 5 * 60 * 1000, // 5분 캐시
});

// --- 초기 모드 판정 (S1-S4 정책) ---
useEffect(() => {
  if (!availabilityData || modeStatus === 'resolved') return;

  const roboCount = availabilityData.robo.table_count;
  const text2sqlCount = availabilityData.text2sql.table_count;

  let resolvedMode: SchemaMode;

  if (roboCount === 0 && text2sqlCount > 0) {
    resolvedMode = 'text2sql';       // S1: text2sql만 존재
  } else if (roboCount > 0 && text2sqlCount === 0) {
    resolvedMode = 'robo';           // S2: robo만 존재
  } else if (roboCount > 0 && text2sqlCount > 0) {
    // S3: 둘 다 존재 — localStorage에서 마지막 선택값 복원
    const stored = localStorage.getItem(`${LS_MODE_PREFIX}${datasourceId}`);
    resolvedMode = stored === 'robo' ? 'robo' : 'text2sql';
  } else {
    resolvedMode = 'text2sql';       // S4: 둘 다 0 — 빈 상태 표시
  }

  setModeInternal(resolvedMode);
  setModeStatus('resolved');
}, [availabilityData, modeStatus, datasourceId]);
```

**상태 머신**: `InitialModeStatus = 'idle' | 'loading' | 'resolved' | 'failed'`
- `idle` → `loading`: datasourceId가 존재하면 자동 전이
- `loading` → `resolved`: 가용성 데이터 도착 + 모드 판정 성공
- `loading` → `failed`: TanStack Query 에러 또는 판정 실패
- `failed` → `idle`: datasourceId 변경 시 리셋 (재시도 가능)

---

#### Step 1-3b: 데이터소스 전환 시 스코프 리셋 (구현 완료)

- **구현 파일**: `canvas/src/features/nl2sql/hooks/useSchemaNavigation.ts`

```typescript
const prevDatasourceRef = useRef<string | null>(datasourceId);

useEffect(() => {
  if (prevDatasourceRef.current !== datasourceId) {
    prevDatasourceRef.current = datasourceId;
    // 모드 상태를 초기화하여 가용성을 다시 로드하도록 한다
    setModeStatus('idle');
    setModeInternal('text2sql');
    setError(null);
  }
}, [datasourceId]);
```

TanStack Query의 `queryKey`에 `datasourceId`가 포함되어 있으므로, 데이터소스 변경 시 자동으로 새 가용성 데이터를 가져온다.

---

#### Step 1-4: Empty State 컴포넌트 (구현 완료)

- **구현 파일**: `canvas/src/features/nl2sql/components/SchemaEmptyState.tsx`

```typescript
interface SchemaEmptyStateProps {
  mode: 'robo' | 'text2sql' | 'none';
  availability: {
    robo: { table_count: number };
    text2sql: { table_count: number };
  } | null;
  onNavigateDatasource?: () => void;
  onSwitchToText2sql?: () => void;
  onSwitchToRobo?: () => void;
}
```

모드별 설정:

| mode | 아이콘 | 제목 | 설명 |
|------|--------|------|------|
| `robo` | `Code2` | "분석된 코드 객체가 아직 없습니다" | "소스 코드를 분석하면 테이블 구조를 자동으로 추출합니다" |
| `text2sql` | `Database` | "연결된 데이터소스 스키마가 없습니다" | "데이터소스를 연결하면 테이블과 관계가 자동으로 표시됩니다" |
| `none` | `Table2` | "아직 탐색할 스키마가 없습니다" | "데이터소스를 연결하거나 소스 코드를 분석하여 시작하세요" |

CTA 동작:
- "데이터소스 연결하기" 버튼 → `onNavigateDatasource()` 콜백
- "데이터소스 스키마에서 보기 →" → `onSwitchToText2sql()` 콜백 (robo 모드에서 text2sql 데이터가 있을 때)
- "코드 분석 스키마에서 보기 →" → `onSwitchToRobo()` 콜백 (text2sql 모드에서 robo 데이터가 있을 때)

---

#### Step 1-5: 모드 전환 UI (구현 완료)

- **구현 파일**: `canvas/src/features/nl2sql/components/SchemaCanvas.tsx`

캔버스 상단에 모드 탭 UI를 표시한다:

```typescript
{mode && onModeChange && (
  <div className="flex items-center gap-0.5 mr-3 shrink-0">
    <button onClick={() => onModeChange('robo')}
      className={cn(
        'px-2 py-0.5 rounded text-[10px] font-[IBM_Plex_Mono]',
        mode === 'robo' ? 'bg-foreground/10 text-foreground/70 font-medium'
                         : 'text-foreground/30 hover:text-foreground/50'
      )}>
      코드분석
      {availability && <span className="ml-1 text-[9px] opacity-60">
        {availability.robo.table_count}
      </span>}
    </button>
    <button onClick={() => onModeChange('text2sql')} ...>
      데이터소스
      {availability && <span ...>{availability.text2sql.table_count}</span>}
    </button>
  </div>
)}
```

빈 상태 시 SchemaEmptyState로 위임:

```typescript
if (tables.length === 0) {
  return (
    <SchemaEmptyState
      mode={mode || 'text2sql'}
      availability={availability ?? null}
      onNavigateDatasource={onNavigateDatasource}
      onSwitchToText2sql={onModeChange ? () => onModeChange('text2sql') : undefined}
      onSwitchToRobo={onModeChange ? () => onModeChange('robo') : undefined}
    />
  );
}
```

---

#### Step 1-6: nodeKey 유틸리티 (구현 완료)

- **구현 파일**: `canvas/src/shared/utils/nodeKey.ts`

`buildNodeKey()`와 `parseNodeKey()` 유틸리티로 프론트엔드/백엔드 간 테이블 식별자 계약을 보장한다. `parseNodeKey`는 테이블명에 콜론이 포함된 경우에도 안전하게 처리한다 (`parts.slice(3).join(':')`).

---

### 2단계: 공통 related-tables API + text2sql FK 자동 로드 (구현 완료)

---

#### Step 2-1: RelatedTablesService 공통 오케스트레이터 (구현 완료)

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `fetch_related_tables_unified()`

```python
async def fetch_related_tables_unified(
    request: RelatedTableRequest,
    tenant_id: str = "",
) -> RelatedTableResponse:
    """모드에 따라 적절한 리졸버를 호출하고, 결과를 통합해서 돌려준다.

    1) 모드별 리졸버로 후보 테이블 목록을 가져온다 (multi-hop 지원).
    2) 허브 테이블을 감지하여 autoAddRecommended=false 처리한다.
    3) 이미 로드된 테이블을 제외한다.
    4) 점수 내림차순 정렬 후 limit만큼 잘라낸다.
    """
    # 모드별 분기 — Strategy 패턴
    if request.mode == SchemaMode.ROBO:
        candidates = await _resolve_robo(
            request.table_name, request.schema_name,
            depth=request.depth, tenant_id=tenant_id,
        )
    else:
        candidates = await _resolve_text2sql(
            request.table_name, request.schema_name, request.datasource_name,
            depth=request.depth, tenant_id=tenant_id,
        )

    # Step 4-2: 허브 테이블 감지
    if candidates:
        hub_set = await _detect_hub_tables(
            [c.table_name for c in candidates], tenant_id=tenant_id,
        )
        for item in candidates:
            if item.table_name in hub_set:
                item.auto_add_recommended = False

    # 이미 로드된 테이블 제외
    already_set = set(request.already_loaded_table_ids)
    filtered = [item for item in candidates if item.table_id not in already_set]

    # 점수 내림차순 정렬 후 limit 적용
    filtered.sort(key=lambda x: x.score, reverse=True)
    result_items = filtered[: request.limit]

    return RelatedTableResponse(
        sourceTable={...},
        relatedTables=result_items,
        meta={...},
    )
```

**요청/응답 모델**:

```python
class RelatedTableRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: SchemaMode
    table_name: str = Field(alias="tableName")
    schema_name: str = Field(default="public", alias="schemaName")
    datasource_name: str = Field(default="", alias="datasourceName")
    node_key: str | None = Field(default=None, alias="nodeKey")
    already_loaded_table_ids: list[str] = Field(default_factory=list, alias="alreadyLoadedTableIds")
    limit: int = Field(default=5, ge=1, le=20)
    depth: int = Field(default=1, ge=1, le=3)


class RelatedTableItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_id: str = Field(alias="tableId")          # nodeKey 형식
    table_name: str = Field(alias="tableName")
    schema_name: str = Field(default="public", alias="schemaName")
    datasource_name: str = Field(default="", alias="datasourceName")
    relation_type: str = Field(alias="relationType")  # FK_OUT, FK_IN
    score: float = 1.0
    fk_count: int = Field(default=0, alias="fkCount")
    source_columns: list[str] = Field(default_factory=list, alias="sourceColumns")
    target_columns: list[str] = Field(default_factory=list, alias="targetColumns")
    hop_distance: int = Field(default=1, alias="hopDistance")
    auto_add_recommended: bool = Field(default=True, alias="autoAddRecommended")
```

---

#### Step 2-2: ROBO 모드 리졸버 (구현 완료)

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `_resolve_robo()`

`:Table` 노드 중 `datasource_name`이 없는 것들에서 `FK_TO_TABLE` 관계를 찾는다.

**1홉 조회 (depth=1)**:
```cypher
-- 나가는 FK
MATCH (t1:Table)-[r:FK_TO_TABLE]->(t2:Table)
WHERE t1.name = $table_name
  AND COALESCE(t1.schema_name, 'public') = $schema_name
  AND (t1.datasource_name IS NULL OR t1.datasource_name = '')
  AND t1.tenant_id = $tid
RETURN t2.name AS related_table,
       COALESCE(t2.schema_name, 'public') AS related_schema,
       count(r) AS fk_count,
       1 AS hop_distance
```

나가는 FK의 base_score=1.0, 들어오는 FK의 base_score=0.85.

**Multi-hop (depth>1)**:
```cypher
MATCH (start:Table {name: $table_name})
WHERE ...
MATCH path = (start)-[:FK_TO_TABLE*1..{depth}]-(related:Table)
WHERE related <> start
RETURN DISTINCT related.name AS related_table, ... , length(path) AS hop_distance
ORDER BY hop_distance ASC
```

---

#### Step 2-3: TEXT2SQL 모드 리졸버 (구현 완료)

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `_resolve_text2sql()`

2단계 폴백 전략:

1. **1차 — 테이블 레벨 FK_TO_TABLE** (`_resolve_text2sql_table_level()`):
   - `(:Table)-[r:FK_TO_TABLE]->(:Table)` 관계 조회
   - `datasource_name` 스코프 필터링
   - 나가는 FK base_score=0.9, 들어오는 FK base_score=0.85

2. **2차 — 컬럼 레벨 FK_TO 폴백** (`_resolve_text2sql_column_level()`):
   - 1차에서 결과가 없을 때만 실행
   - `(:Table)-[:HAS_COLUMN]->(:Column)-[:FK_TO]->(:Column)<-[:HAS_COLUMN]-(:Table)` 경로 탐색
   - 양방향 조회 후 중복 제거 (table_id 기반)

```python
async def _resolve_text2sql(
    table_name, schema_name, datasource_name, depth=1, tenant_id="",
) -> list[RelatedTableItem]:
    # 1단계: 테이블 레벨 FK_TO_TABLE 조회
    table_items = await _resolve_text2sql_table_level(...)
    if table_items:
        return table_items

    # 2단계: 컬럼 레벨 FK_TO 폴백 (depth=1에서만)
    col_items = await _resolve_text2sql_column_level(...)
    return col_items
```

---

#### Step 2-4: API 엔드포인트 등록 (구현 완료)

- **구현 파일**: `services/synapse/app/api/schema_navigation.py`

```python
router = APIRouter(
    prefix="/api/v3/synapse/schema-nav",
    tags=["Schema Navigation"],
)

@router.post("/related-tables")
async def post_related_tables(request_body: RelatedTableRequest, request: Request):
    tenant_id = _require_tenant(request)
    result = await fetch_related_tables_unified(request_body, tenant_id=tenant_id)
    return {"success": True, "data": result.model_dump(by_alias=True)}
```

`_require_tenant()` 가드가 `request.state.tenant_id`가 없으면 401을 반환한다.

---

#### Step 2-5: 프론트엔드 related-tables API 클라이언트 (구현 완료)

- **구현 파일**: `canvas/src/shared/api/schemaNavigationApi.ts` — `getRelatedTables()`

```typescript
export async function getRelatedTables(
  request: RelatedTableRequest,
): Promise<RelatedTableResponse> {
  const res = await synapseApi.post('/api/v3/synapse/schema-nav/related-tables', {
    mode: request.mode,
    tableName: request.tableName,
    schemaName: request.schemaName || 'public',
    datasourceName: request.datasourceName || '',
    nodeKey: request.nodeKey,
    alreadyLoadedTableIds: request.alreadyLoadedTableIds || [],
    limit: request.limit || 5,
    depth: request.depth || 1,
  });
  const body = res as unknown as { success: boolean; data?: RelatedTableResponse };
  if (!body.data) {
    throw new Error('Invalid response from related-tables API');
  }
  return body.data;
}
```

---

#### Step 2-6: text2sql 모드 FK 자동 로드 활성화 (구현 완료)

- **구현 파일**: `canvas/src/features/nl2sql/hooks/useSchemaNavigation.ts` — `loadRelatedTables()`

```typescript
const loadRelatedTables = useCallback(
  async (params: {
    tableName: string;
    schemaName?: string;
    datasourceName?: string;
    alreadyLoadedNodeKeys: string[];
  }): Promise<RelatedTableItem[]> => {
    setLoadingRelated(true);

    const apiMode = mode === 'robo' ? 'ROBO' as const : 'TEXT2SQL' as const;
    const nodeKey = buildNodeKey(
      mode,
      params.datasourceName || datasourceId || '',
      params.schemaName || 'public',
      params.tableName,
    );

    const result = await getRelatedTables({
      mode: apiMode,
      tableName: params.tableName,
      schemaName: params.schemaName || 'public',
      datasourceName: params.datasourceName || datasourceId || undefined,
      nodeKey,
      alreadyLoadedTableIds: params.alreadyLoadedNodeKeys,
    });

    return result.relatedTables;
  },
  [mode, datasourceId],
);
```

---

### 3단계: TEXT2SQL 리졸버 최적화 (구현 완료)

#### Step 3-1: 테이블 레벨 FK 우선 조회 + 컬럼 레벨 폴백

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `_resolve_text2sql()`

`_resolve_text2sql()`이 테이블 레벨 FK_TO_TABLE을 먼저 시도하고, 결과가 없으면 컬럼 레벨 FK_TO로 폴백한다. 이 로직은 Step 2-3에서 이미 통합 구현되었다.

---

### 4단계: 스코어링, 허브 감지, Multi-hop (구현 완료)

---

#### Step 4-1: 가중치 기반 스코어링 (구현 완료)

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `_compute_score()`

```python
def _compute_score(base_score: float, fk_count: int, hop_distance: int = 1) -> float:
    """관련도 점수를 계산한다.

    가중치 요소:
      - base_score: 관계 방향에 따른 기본 점수 (FK_OUT=1.0/0.9, FK_IN=0.85)
      - fk_count: FK 컬럼 수가 많을수록 가산 (최대 +0.09)
      - hop_distance: 홉 거리가 멀수록 감점 (2홉=-0.15, 3홉=-0.30)
    """
    fk_bonus = min(fk_count * 0.02, 0.09)         # 최대 0.09
    hop_penalty = max(0, (hop_distance - 1)) * 0.15  # 1홉=0, 2홉=0.15, 3홉=0.30
    return round(base_score + fk_bonus - hop_penalty, 3)
```

**기본 점수 표**:

| 모드 | 방향 | base_score |
|------|------|-----------|
| ROBO | FK_OUT | 1.0 |
| ROBO | FK_IN | 0.85 |
| TEXT2SQL | FK_OUT | 0.9 |
| TEXT2SQL | FK_IN | 0.85 |

**점수 예시**:
- FK_OUT(1.0) + 3 FK 컬럼(+0.06) + 1홉(-0.00) = **1.06**
- FK_IN(0.85) + 1 FK 컬럼(+0.02) + 2홉(-0.15) = **0.72**

---

#### Step 4-2: 허브 테이블 감지 (구현 완료)

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `_detect_hub_tables()`
- **임계값**: `HUB_FK_THRESHOLD = 10`

```python
async def _detect_hub_tables(
    table_names: list[str], tenant_id: str = "",
) -> set[str]:
    """FK_TO_TABLE 관계가 HUB_FK_THRESHOLD개 이상인 테이블을 찾는다."""
    query = f"""
    UNWIND $names AS table_name
    MATCH (t:Table {{name: table_name}})
    WHERE true {tid_clause}
    OPTIONAL MATCH (t)-[:FK_TO_TABLE]-()
    WITH t.name AS name, count(*) AS fk_degree
    WHERE fk_degree >= $threshold
    RETURN name
    """
```

허브로 감지된 테이블은 `autoAddRecommended=false`로 표시되어, 프론트엔드에서 자동 추가하지 않고 사용자 판단에 맡긴다.

---

#### Step 4-3: Multi-hop 탐색 (구현 완료)

- **구현 파일**: `services/synapse/app/services/related_tables_service.py` — `_resolve_robo()`, `_resolve_text2sql_table_level()`
- **파라미터**: `depth: int = Field(default=1, ge=1, le=3)`

depth>1일 때 Cypher 가변 길이 경로를 사용한다:

```cypher
MATCH (start:Table {name: $table_name})
WHERE ...
MATCH path = (start)-[:FK_TO_TABLE*1..{min(depth, 3)}]-(related:Table)
WHERE related <> start
  AND ($ds = '' OR related.datasource_name = $ds)
RETURN DISTINCT related.name AS related_table,
       COALESCE(related.schema_name, 'public') AS related_schema,
       related.datasource_name AS related_ds,
       length(path) AS hop_distance
ORDER BY hop_distance ASC
```

Multi-hop 결과에서 중복은 `seen` set으로 제거하며, 가장 짧은 경로만 남긴다.

---

## 5. 파일 구성

### 백엔드 (services/synapse)

| 파일 | 용도 | LOC |
|------|------|-----|
| `services/synapse/app/services/related_tables_service.py` | 통합 서비스: availability, related-tables, hub 감지, multi-hop, 스코어링, nodeKey 유틸리티 | 606 |
| `services/synapse/app/api/schema_navigation.py` | REST API 라우터: GET /availability, POST /related-tables | 82 |

### 프론트엔드 (canvas)

| 파일 | 용도 | LOC |
|------|------|-----|
| `canvas/src/shared/utils/nodeKey.ts` | `buildNodeKey`/`parseNodeKey` 유틸리티 | 36 |
| `canvas/src/shared/types/schemaNavigation.ts` | TypeScript 타입 (SchemaAvailability, RelatedTableItem, RelatedTableResponse, RelatedTableRequest, InitialModeStatus) | 57 |
| `canvas/src/shared/api/schemaNavigationApi.ts` | Synapse API 클라이언트 (`getSchemaAvailability`, `getRelatedTables`) | 45 |
| `canvas/src/features/nl2sql/hooks/useSchemaNavigation.ts` | 네비게이션 훅: S1-S4 판정, 스코프 리셋, 관련 테이블 로딩 | 201 |
| `canvas/src/features/nl2sql/components/SchemaEmptyState.tsx` | 빈 상태 UI (모드별 아이콘, 메시지, CTA) | 123 |
| `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` | ERD 캔버스: 모드 탭, 테이블 칩, Mermaid 렌더링, Empty State 위임 | 232 |

---

## 6. 테스트 커버리지

### 6.1 백엔드 단위 테스트

| 파일 | 테스트 수 | 주요 검증 항목 |
|------|-----------|---------------|
| `services/synapse/tests/unit/test_related_tables_service.py` | 22건 | build_node_key 대소문자/기본값/라운드트립, RelatedTableRequest alias 파싱/get_node_key 자동생성/명시적 키, fetch_schema_availability 필터/무필터/빈결과, fetch_related_tables_unified ROBO/TEXT2SQL 모드 분기/허브감지/이미 로드 제외/limit/multi-hop |

### 6.2 백엔드 API 통합 테스트

| 파일 | 테스트 수 | 주요 검증 항목 |
|------|-----------|---------------|
| `services/synapse/tests/unit/test_schema_navigation_api.py` | 8건 | GET /availability 성공/파라미터전달/서버에러, POST /related-tables 성공/서버에러/요청로깅, 인증 실패 시 401 |

### 6.3 프론트엔드 단위 테스트

| 파일 | 테스트 수 | 주요 검증 항목 |
|------|-----------|---------------|
| `canvas/src/shared/utils/nodeKey.test.ts` | 9건 | buildNodeKey 기본형/빈값기본/full, parseNodeKey 기본형/빈부분기본/콜론포함 테이블명, 라운드트립 일치 |
| `canvas/src/features/nl2sql/hooks/useSchemaNavigation.test.ts` | 11건 | S1-S4 초기모드판정, localStorage 복원, 모드수동변경+저장, datasource 변경 시 리셋, loadRelatedTables 성공/실패, modeStatus 전이 |
| `canvas/src/features/nl2sql/components/SchemaEmptyState.test.tsx` | 11건 | 모드별 제목/설명 렌더링, CTA 버튼 표시조건/클릭핸들러, 모드전환 링크 조건부 표시, availability=null 처리 |

### 6.4 테스트 합계

| 카테고리 | 테스트 파일 수 | 테스트 케이스 수 |
|----------|---------------|-----------------|
| 백엔드 | 2 | 30 |
| 프론트엔드 | 3 | 31 |
| **합계** | **5** | **61** |

### 6.5 엣지 케이스 커버리지

| 시나리오 | 테스트 위치 |
|----------|-----------|
| 동명 테이블 (다른 schema) — `public.users` vs `audit.users` | `nodeKey.test.ts`, `test_related_tables_service.py` |
| 동명 테이블 (다른 datasource) — `erp_db.orders` vs `analytics.orders` | `nodeKey.test.ts` |
| 테이블명에 콜론 포함 — `parseNodeKey` 안전 처리 | `nodeKey.test.ts` |
| 허브 테이블 자동추가 비추천 | `test_related_tables_service.py` |
| 이미 로드된 테이블 제외 | `test_related_tables_service.py` |
| availability API 실패 → `modeStatus='failed'` | `useSchemaNavigation.test.ts` |
| datasource 전환 시 스코프 리셋 | `useSchemaNavigation.test.ts` |
| tenant_id 필터링 | `test_related_tables_service.py` |
| TEXT2SQL 컬럼 레벨 FK_TO 폴백 | `test_related_tables_service.py` |

---

## 7. 위험 평가

| 위험 | 영향 | 확률 | 완화 전략 |
|------|------|------|----------|
| Neo4j 연결 실패 시 캔버스 작동 불가 | text2sql FK 자동 로드 실패 | 중 | try-catch + 에러 상태 표시, `modeStatus='failed'` 재시도 가능 |
| 허브 테이블 임계값(10)이 도메인에 부적합 | 중요 테이블이 자동 추가 안 됨 | 저 | `HUB_FK_THRESHOLD` 상수로 분리, 향후 설정값으로 변경 가능 |
| Multi-hop(depth=3) 시 결과 폭발 | 응답 시간 증가 | 중 | limit 파라미터 (max=20), 가변 경로 최대 depth=3 제한 |
| nodeKey 형식 변경으로 기존 참조 깨짐 | 기존 `table-${name}` 패턴 코드와 비호환 | 저 | 신규 구현이므로 레거시 코드 없음 |
| tenant_id 누락 시 데이터 유출 | 다른 테넌트 데이터 노출 | 저 | `_require_tenant()` 가드로 401 반환, 개발환경에서는 빈 tenant_id 허용 |
| TanStack Query staleTime(5분) 동안 가용성 변경 미반영 | 새 테이블 추가 후 카운트 갱신 지연 | 저 | 데이터소스 변경 시 queryKey가 바뀌어 자동 재조회 |

---

## 8. 의존 관계 다이어그램

```
1단계 (모드 분리 + Empty State)          2단계 (통합 API)              4단계 (고급 기능)

┌──────────────────────┐
│ Step 1-1 (구현 완료) │
│ 가용성 API           │
│ fetch_schema_        │
│ availability()       │
└──────┬───────────────┘
       │
┌──────▼───────────────┐
│ Step 1-2 (구현 완료) │
│ getSchemaAvailability│
│ (schemaNavigationApi)│
└──────┬───────────────┘
       │                    ┌─────────────────────────┐
┌──────▼───────────────┐    │ Step 2-1 (구현 완료)    │
│ Step 1-3 (구현 완료) │    │ fetch_related_tables_   │
│ useSchemaNavigation  │    │ unified()               │
│ S1-S4 정책+상태머신  │    │ + Strategy 패턴         │
└──┬─────────┬─────────┘    └──┬──────────┬───────────┘
   │         │                 │          │
┌──▼────┐  ┌▼───────────┐     │          │
│Step   │  │Step 1-6    │     │          │
│1-3b   │  │nodeKey.ts  │     │          │
│스코프 │  │buildNodeKey│     │          │
│리셋   │  │parseNodeKey│     │          │
└───────┘  └────────────┘     │          │
       │                 ┌────▼───┐  ┌───▼──────────┐
┌──────▼───────────────┐ │Step2-2 │  │Step 2-3      │
│ Step 1-4 (구현 완료) │ │_resolve│  │_resolve_     │
│ SchemaEmptyState.tsx │ │_robo() │  │text2sql()    │
└──────┬───────────────┘ └────┬───┘  └───┬──────────┘
       │                      │          │
┌──────▼───────────────┐ ┌────▼──────────▼──────────┐
│ Step 1-5 (구현 완료) │ │ Step 2-4 (구현 완료)     │    ┌──────────────────────┐
│ SchemaCanvas.tsx     │ │ schema_navigation.py     │    │ Step 4-1 (구현 완료) │
│ 모드 탭 + ERD 캔버스 │ │ POST /related-tables     │    │ _compute_score()     │
└──────────────────────┘ └────────┬────────────────┘    │ 가중치 스코어링       │
                                  │                      └──────────────────────┘
                         ┌────────▼────────────────┐    ┌──────────────────────┐
                         │ Step 2-5 (구현 완료)     │    │ Step 4-2 (구현 완료) │
                         │ getRelatedTables()       │    │ _detect_hub_tables() │
                         │ (schemaNavigationApi)    │    │ HUB_FK_THRESHOLD=10  │
                         └────────┬────────────────┘    └──────────────────────┘
                                  │                      ┌──────────────────────┐
                         ┌────────▼────────────────┐    │ Step 4-3 (구현 완료) │
                         │ Step 2-6 (구현 완료)     │    │ Multi-hop *1..3      │
                         │ loadRelatedTables()      │    │ 가변 길이 Cypher     │
                         │ (useSchemaNavigation)    │    └──────────────────────┘
                         └─────────────────────────┘
```

---

## 부록 A: 실제 코드 참조 경로

| 항목 | 파일 경로 |
|------|----------|
| 통합 서비스 | `services/synapse/app/services/related_tables_service.py` |
| API 라우터 | `services/synapse/app/api/schema_navigation.py` |
| Neo4j 클라이언트 | `services/synapse/app/core/neo4j_client.py` |
| nodeKey 유틸리티 (프론트) | `canvas/src/shared/utils/nodeKey.ts` |
| 타입 정의 | `canvas/src/shared/types/schemaNavigation.ts` |
| API 클라이언트 | `canvas/src/shared/api/schemaNavigationApi.ts` |
| 네비게이션 훅 | `canvas/src/features/nl2sql/hooks/useSchemaNavigation.ts` |
| Empty State 컴포넌트 | `canvas/src/features/nl2sql/components/SchemaEmptyState.tsx` |
| ERD 캔버스 컴포넌트 | `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` |
| Weaver 메타데이터 그래프 | `services/weaver/app/services/metadata_graph_service.py` |
| 백엔드 단위 테스트 | `services/synapse/tests/unit/test_related_tables_service.py` |
| 백엔드 API 테스트 | `services/synapse/tests/unit/test_schema_navigation_api.py` |
| nodeKey 테스트 | `canvas/src/shared/utils/nodeKey.test.ts` |
| 훅 테스트 | `canvas/src/features/nl2sql/hooks/useSchemaNavigation.test.ts` |
| Empty State 테스트 | `canvas/src/features/nl2sql/components/SchemaEmptyState.test.tsx` |

---

## 부록 B: API 계약 요약

### GET /api/v3/synapse/schema-nav/availability

**Query Parameters**:

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| `datasourceName` | string | 아니오 | 특정 데이터소스만 필터 |

**응답 예시**:

```json
{
  "success": true,
  "data": {
    "robo": { "table_count": 0 },
    "text2sql": { "table_count": 13 }
  }
}
```

### POST /api/v3/synapse/schema-nav/related-tables

**Request Body**:

```json
{
  "mode": "TEXT2SQL",
  "tableName": "orders",
  "schemaName": "public",
  "datasourceName": "erp_db",
  "nodeKey": "text2sql:erp_db:public:orders",
  "alreadyLoadedTableIds": ["text2sql:erp_db:public:customers"],
  "limit": 5,
  "depth": 1
}
```

**응답 예시**:

```json
{
  "success": true,
  "data": {
    "sourceTable": {
      "tableId": "text2sql:erp_db:public:orders",
      "tableName": "orders",
      "schemaName": "public",
      "datasourceName": "erp_db"
    },
    "relatedTables": [
      {
        "tableId": "text2sql:erp_db:public:order_items",
        "tableName": "order_items",
        "schemaName": "public",
        "datasourceName": "erp_db",
        "relationType": "FK_IN",
        "score": 0.87,
        "fkCount": 1,
        "sourceColumns": ["order_id"],
        "targetColumns": ["id"],
        "columnPairs": [
          { "sourceColumn": "order_id", "targetColumn": "id" }
        ],
        "hopDistance": 1,
        "autoAddRecommended": true
      }
    ],
    "meta": {
      "mode": "TEXT2SQL",
      "limitApplied": 5,
      "excludedAlreadyLoaded": 1,
      "depthUsed": 1
    }
  }
}
```

**필수 헤더**: `Authorization: Bearer <token>`, `X-Tenant-Id: <tenant_id>`

---

## 부록 C: 갭 기능 (G1-G8) 구현 현황

> ADR-033 기본 구현 완료 후 KAIR 레퍼런스와 비교 분석한 8개 추가 기능.

### 구현 현황 요약

| Gap | 기능명 | 우선순위 | 상태 | 핵심 파일 |
|-----|--------|----------|------|----------|
| G1 | FK 가시성 토글 (소스별) | P1 | **구현 완료** | `useFkVisibility.ts`, `FkVisibilityToolbar.tsx` |
| G2 | 사용자 관계 편집 모달 | P1 | **구현 완료** | `CardinalityModal.tsx` |
| G3 | 스키마 편집 API 연동 | P1 | **구현 완료** | `schemaEditApi.ts`, `useSchemaEdit.ts` |
| G4 | column_pairs 구조 | P1 | **구현 완료** | `related_tables_service.py` (ColumnPair), `schemaNavigation.ts` |
| G5 | 실시간 캔버스 업데이트 | P2 | **구현 완료** | `useCanvasPolling.ts` |
| G6 | 시맨틱 검색 (벡터) | P2 | **구현 완료** | `useSemanticSearch.ts` |
| G7 | 논리명/물리명 토글 | P2 | **구현 완료** | `useDisplayMode.ts` |
| G8 | 테이블 데이터 프리뷰 | P2 | **구현 완료** | `DataPreviewPanel.tsx` |

### G1: FK 가시성 토글

**소스 타입별 관계선 색상/스타일 구분 + 토글**:
- DDL: `#22C55E` (초록 실선) — DB 스키마에서 파생된 FK
- User: `#F97316` (주황 실선) — 사용자가 수동 추가한 FK
- Fabric: `#3B82F6` (파랑 점선) — Fabric 추론 FK
- `useFkVisibility` 훅: `visibility` 상태 + `toggle(source)` + `isVisible(source)`
- `FkVisibilityToolbar`: 3개 색상 칩 토글 버튼

### G2: CardinalityModal

**FK 관계 생성/편집 모달**:
- 소스/타겟 테이블 + 컬럼 드롭다운 선택
- Cardinality 라디오: N:1, 1:1, 1:N, N:M
- 복수 컬럼 매핑 (column_pairs) 지원
- `useSchemaEdit.createRel` mutation으로 Synapse API에 저장

### G3: 스키마 편집 API 연동

**프론트엔드 API 클라이언트 + TanStack Query 훅**:
- `schemaEditApi.ts`: 7개 함수 (listTables, updateTableDescription, updateColumnDescription, listRelationships, createRelationship, deleteRelationship, rebuildTableEmbedding)
- `useSchemaEdit.ts`: 1개 쿼리 + 5개 mutation, 성공 시 관련 캐시 자동 무효화

### G4: column_pairs 구조

**백엔드 + 프론트엔드 타입 동기화**:
- BE: `ColumnPair(sourceColumn, targetColumn)` Pydantic 모델 → `RelatedTableItem.column_pairs`
- FE: `ColumnPair` 인터페이스 → `RelatedTableItem.columnPairs`, `SchemaRelationship.columnPairs`
- `_row_to_item()`에서 `source_cols`/`target_cols`를 zip하여 자동 생성

### G5: 실시간 캔버스 업데이트

**폴링 기반 변경 감지**:
- `useCanvasPolling`: `schema-edit/last-modified` 엔드포인트를 5초 간격으로 폴링
- 타임스탬프 변경 감지 시 `onUpdate` 콜백 호출
- 엔드포인트 미구현 시 조용히 실패 (graceful degradation)

### G6: 시맨틱 검색

**벡터 기반 자연어 테이블/컬럼 검색**:
- `useSemanticSearch`: `POST /api/v3/synapse/graph/vector-search` 호출
- `VectorSearchHit` → `SchemaSearchResult` 변환
- 검색어 2자 이상 시 활성화, node_types: Table/Column 필터

### G7: 논리명/물리명 토글

**ERD 표시 모드 전환**:
- `useDisplayMode`: `physical` (DB 이름) ↔ `logical` (description 필드)
- `getDisplayName(name, description)`: logical 모드에서 description 우선, 없으면 name 폴백
- SchemaCanvas 상단 바에 토글 버튼 배치

### G8: 데이터 프리뷰 패널

**테이블 칩 클릭 → 실제 데이터 미리보기**:
- `DataPreviewPanel`: 슬라이드 패널 (400px)
- Oracle `/text2sql/execute` API로 `SELECT * FROM {table} LIMIT 10` 실행
- 로딩/에러/빈 데이터/재시도 상태 처리

### 신규 파일 목록 (G1-G8)

| 파일 | Gap | 용도 |
|------|-----|------|
| `canvas/src/features/nl2sql/hooks/useFkVisibility.ts` | G1 | FK 소스별 가시성 상태 관리 |
| `canvas/src/features/nl2sql/components/FkVisibilityToolbar.tsx` | G1 | 소스별 토글 칩 UI |
| `canvas/src/features/nl2sql/components/CardinalityModal.tsx` | G2 | FK 관계 편집 모달 |
| `canvas/src/shared/api/schemaEditApi.ts` | G3 | Synapse schema-edit API 클라이언트 |
| `canvas/src/features/nl2sql/hooks/useSchemaEdit.ts` | G3 | TanStack Query CRUD 훅 |
| `canvas/src/features/nl2sql/hooks/useCanvasPolling.ts` | G5 | 폴링 기반 변경 감지 |
| `canvas/src/features/nl2sql/hooks/useSemanticSearch.ts` | G6 | 벡터 검색 훅 |
| `canvas/src/features/nl2sql/hooks/useDisplayMode.ts` | G7 | 논리명/물리명 전환 훅 |
| `canvas/src/features/nl2sql/components/DataPreviewPanel.tsx` | G8 | 데이터 프리뷰 슬라이드 패널 |

### 수정 파일 목록 (G1-G8)

| 파일 | Gap | 변경 내용 |
|------|-----|----------|
| `services/synapse/app/services/related_tables_service.py` | G4 | `ColumnPair` 모델, `_compute_score()`, `_detect_hub_tables()`, multi-hop, tenant_id |
| `canvas/src/shared/types/schemaNavigation.ts` | G4 | `ColumnPair` 인터페이스, `RelatedTableItem.columnPairs` |
| `canvas/src/features/nl2sql/types/schema.ts` | G1,G4 | `FkSource` 타입, `SchemaRelationship.source`, `columnPairs` |
| `canvas/src/features/nl2sql/components/SchemaCanvas.tsx` | G1-G8 | 훅/컴포넌트 통합, 도구 버튼 바, 프리뷰 패널 |
