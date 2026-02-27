# Insight 갭 구현 계획

> **작성일**: 2026-02-27
> **개정**: v2 — 코드 검증 후 설계 오류 보강 (10개 항목)
> **근거 문서**: `docs/insight-view-implementation.md` (v3.1), `docs/gap-analysis-insight-frontend-verified.md`
> **현황**: 프론트엔드 Phase 1·2 완료 (~2,900 LOC), 백엔드 API 3개 + Oracle 자동 인제스트 미구현

---

## 1. 현황 요약

### 완료 — 변경 불필요

| 레이어 | 상태 |
|--------|------|
| Canvas 라우트 / Sidebar | ✅ `/analysis/insight` 등록, 메뉴 존재 |
| `features/insight/` 전체 (15개 파일) | ✅ types, api, store, hooks, components, utils |
| `pages/insight/` (3개 파일) | ✅ InsightPage, InsightHeader, InsightSidebar |
| NL2SQL Graph 탭 통합 | ✅ QueryGraphPanel + ResultPanel 완료 |
| `POST /api/insight/impact` (200/202) | ✅ Redis 캐시 + 비동기 job |
| `GET /api/insight/jobs/{job_id}` | ✅ 폴링 엔드포인트 |
| `POST /api/insight/query-subgraph` | ✅ SQL → 서브그래프 |
| `POST /api/insight/logs` + `:ingest` | ✅ 배치/실시간 인제스트 |

### 미구현 갭 — 이번 계획의 대상

| ID | 항목 | 위치 | 현재 workaround |
| ---- | ------ | ------ | ---------------- |
| **P0-A** | `GET /api/insight/kpis` | Weaver 백엔드 + Canvas | KpiSelector 하드코딩 샘플 5개 |
| **P0-B** | `GET /api/insight/drivers` | Weaver 백엔드 | DriverRankingPanel 클라이언트 파생 |
| **P1-A** | `GET /api/insight/drivers/{driver_key}` | Weaver 백엔드 + Canvas | useDriverDetail 스텁 |
| **P1-B** | Oracle→Weaver 자동 인제스트 | Oracle 백엔드 | 수동 `/logs` POST만 가능 |
| **P2-A** | `useKpiTimeseries` + `KpiMiniChart` | Weaver 백엔드 + Canvas | 없음 (Phase 3) |
| **P2-B** | `useNodeDataPreview` (Ontology) | Canvas | 없음 (Phase 3) |

---

## 2. 코드 검증으로 발견된 설계 전제 오류

v1 계획 작성 후 실제 코드를 검증해 확인된 오류 10개. 각 작업 블록에 반영됨.

| # | 발견 내용 | 영향 작업 |
| --- | ----------- | --------- |
| **E1** | `/kpis`의 SQL이 `datasource_id` 집계만 함 → KPI 아이템(`id/name/fingerprint`) 생성 불가 | P0-A |
| **E2** | `time_range: "30d"` → `"30d days"` SQL 오류 — 서버 정규화 누락 | P0-A, P0-B, P1-A |
| **E3** | `total: len(rows)` = 현재 페이지 수 ≠ 전체 후보 수 → pagination 오작동 | P0-A, P0-B |
| **E4** | `impact_task.py`는 `insight_driver_scores` 테이블에 **전혀 쓰지 않음** → `/drivers`의 데이터 원천 없음 | P0-B |
| **E5** | `driver_id`의 정체 미정의 — `column_key`에 `.` `:` 포함 시 URL path 오염 | P1-A |
| **E6** | evidence를 `normalized_sql LIKE '%driver_id%'`로 추출 → 짧은 컬럼명 오탐 多 | P1-A |
| **E7** | Oracle `access_token`을 Weaver에 그대로 전달 → issuer/audience 불일치, tenant 전파 계약 미정 | P1-B |
| **E8** | `asyncio.create_task()` 무제한 — QPS 상승 시 task backlog + 메모리 증가 | P1-B |
| **E9** | `/kpi/timeseries`의 "KPI 값" 원천 미정 — 로그에 값 없음, 별도 쿼리 실행 필요 | P2-A |
| **E10** | P2-B가 Synapse 서비스 신규 개발에 의존 → 일정 리스크 과소평가 | P2-B |

---

## 3. 작업 블록별 구현 상세

---

### [P0-A] `GET /api/insight/kpis` — KPI 목록 API

**목적**: `KpiSelector`의 하드코딩 샘플을 서버 기반 KPI 목록으로 전환.

#### 3.1 KPI 아이템 생성 전략 (E1 해결)

`insight_query_logs`에는 KPI 아이템을 만들 정보가 없다. 두 옵션 중 하나를 선택해야 한다.

##### 옵션 A (권장) — 로그 스키마 확장

`/logs` ingest entry에 `kpi_fingerprint` 필드를 추가. Oracle 자동 인제스트(P1-B)와 함께 진행하면 P1-B 구현 시 entry에 필드를 포함시키면 됨. `/kpis`는 단순 집계.

```
insight_query_logs 확장:
  kpi_fingerprint TEXT  -- NL2SQL 시 감지된 KPI fingerprint (nullable)
  kpi_name TEXT         -- fingerprint 없을 때 alias 저장
```

```sql
-- /kpis 쿼리 (옵션 A)
SELECT
    kpi_fingerprint                                  AS fingerprint,
    COALESCE(MIN(kpi_name), kpi_fingerprint)        AS name,
    datasource_id,
    COUNT(*)                                         AS query_count,
    MAX(executed_at)                                 AS last_seen,
    COUNT(*) OVER()                                  AS total_count   -- E3 해결
FROM weaver.insight_query_logs
WHERE tenant_id = $1
  AND kpi_fingerprint IS NOT NULL
  AND ($2::text IS NULL OR datasource_id = $2)
  AND executed_at >= NOW() - _parse_time_range($3)  -- E2 해결
GROUP BY kpi_fingerprint, datasource_id
ORDER BY query_count DESC
LIMIT $4 OFFSET $5
```

##### 옵션 B — SQL AST 기반 metric 추출

`query_log_analyzer.py`의 기존 파이프라인을 재사용. SELECT의 aggregate expression(`SUM(col)`, `COUNT(*)`)을 KPI 후보로 추출. 이미 `query_subgraph` 엔드포인트에서 유사 파이프라인이 동작 중이므로 재사용 가능.

> **결정 필요**: P0-A와 P1-B를 함께 진행한다면 옵션 A가 구조적으로 단순. P1-B를 나중에 한다면 옵션 B로 독립 구현.

#### 3.2 time_range 정규화 유틸 (E2 해결)

모든 DB 쿼리에서 공통 사용. `insight_query_store.py`에 추가.

```python
_ALLOWED_RANGES = {"7d": 7, "30d": 30, "90d": 90}

def parse_time_range_days(time_range: str) -> int:
    """'30d' → 30. 미허용 값은 ValueError."""
    days = _ALLOWED_RANGES.get(time_range)
    if days is None:
        raise ValueError(f"Invalid time_range: {time_range!r}. Allowed: {list(_ALLOWED_RANGES)}")
    return days
```

엔드포인트에서:

```python
from fastapi import HTTPException
try:
    days = parse_time_range_days(time_range)
except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e))
```

DB 쿼리에는 `INTERVAL '{days} days'` 리터럴을 사용하거나 Python `timedelta`로 변환 후 전달.

#### 3.3 백엔드 구현

**파일**: `services/weaver/app/api/insight.py`

```python
@router.get("/kpis")
async def list_kpis(
    datasource: str | None = None,
    time_range: str = "30d",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, le=200),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    try:
        days = parse_time_range_days(time_range)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))

    pool = await insight_store.get_pool()
    async with rls_session(pool, tenant_id) as conn:
        rows, total = await fetch_kpis(
            conn, tenant_id, datasource, days, offset, limit
        )
    return {
        "kpis": rows,
        "total": total,           # E3: 전체 후보 수
        "pagination": {
            "offset": offset,
            "limit": limit,
            "has_more": (offset + limit) < total,
        },
    }
```

**응답 스펙**:

```json
{
  "kpis": [
    {
      "id": "sha256:a1b2c3d4",
      "name": "AR Balance",
      "source": "query_log",
      "primary": false,
      "fingerprint": "sha256:a1b2c3d4",
      "datasource": "insolvency_pg",
      "query_count": 45,
      "last_seen": "2026-02-26T10:00:00Z",
      "trend": null,
      "aliases": []
    }
  ],
  "total": 12,
  "pagination": { "offset": 0, "limit": 50, "has_more": false }
}
```

#### 3.4 프론트엔드 수정

**파일**: [features/insight/api/insightApi.ts](apps/canvas/src/features/insight/api/insightApi.ts)

```typescript
export async function fetchKpis(params?: {
  datasource?: string;
  time_range?: TimeRange;
  offset?: number;
  limit?: number;
}): Promise<KpiListResponse>
```

**파일**: [features/insight/components/KpiSelector.tsx](apps/canvas/src/features/insight/components/KpiSelector.tsx)

```
변경:
  - SAMPLE_KPIS 상수 제거
  - useEffect → fetchKpis() 호출, 결과로 빠른선택 버튼 렌더링
  - API 응답이 빈 배열이면 "KPI 없음, 직접 입력하세요" 안내 표시
  - input 직접 입력 fallback 유지 (API 오류 시에도 동작)
```

**파일**: [features/insight/types/insight.ts](apps/canvas/src/features/insight/types/insight.ts)

```typescript
export interface KpiListItem {
  id: string;
  name: string;
  source: 'ontology' | 'query_log' | 'merged';
  primary: boolean;
  fingerprint: string;
  datasource: string;
  query_count: number;
  last_seen: string | null;
  trend: 'up' | 'down' | 'flat' | null;
  aliases: string[];
}

export interface KpiListResponse {
  kpis: KpiListItem[];
  total: number;
  pagination: { offset: number; limit: number; has_more: boolean };
}
```

---

### [P0-B] `GET /api/insight/drivers` — Driver 랭킹 API

**목적**: Insight 페이지 Sidebar에 KPI 선택 전에도 상위 Driver 목록 제공.

#### 3.5 데이터 원천 확정 (E4 해결)

코드 검증 결과: **`impact_task.py`는 `insight_driver_scores` 테이블에 쓰지 않는다.** 점수는 Redis job result에만 저장됨.

따라서 두 가지 선택지:

##### 옵션 A (권장) — impact_task에 DB 쓰기 추가

`impact_task.py` Step 5에 `insight_driver_scores` INSERT 추가. 이후 `/drivers`는 DB 조회로 충분.

```python
# impact_task.py Step 5 (기존 cache_key set 직후)
await _persist_driver_scores(
    conn, tenant_id, datasource_id, kpi_fingerprint,
    time_range, drivers + dimensions
)
```

`_persist_driver_scores`는 `ScoredCandidate` 리스트를 `insight_driver_scores`에 upsert.

##### 옵션 B — Redis cache에서 derive (지연 없이 빠름)

완료된 job의 Redis result에서 graph nodes를 읽어 DRIVER/DIMENSION 필터링. 상태(캐시 TTL) 의존.

> **결정**: DB 쓰기 비용이 미미하고 영속성이 중요하므로 옵션 A 권장. `impact_task.py`에 1개 함수 추가로 해결.

#### 3.6 fallback 계약 명시 (응답에 source 필드)

```json
{
  "drivers": [ ... ],
  "total": 30,
  "pagination": { "offset": 0, "limit": 30, "has_more": false },
  "meta": {
    "source": "driver_scores",       // "driver_scores" | "empty"
    "kpi_fingerprint": "sha256:...", // 요청 echo
    "datasource": "insolvency_pg",
    "generated_at": "2026-02-26T10:00:00Z"
  }
}
```

`source: "empty"` 시 프론트는 기존 클라이언트 파생 방식을 유지 (graceful fallback).

#### 3.7 백엔드 구현

**파일**: `services/weaver/app/api/insight.py`

```python
@router.get("/drivers")
async def list_drivers(
    datasource: str | None = None,
    kpi_fingerprint: str | None = None,
    time_range: str = "30d",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, le=100),
    tenant_id: str = Depends(get_effective_tenant_id),
):
    try:
        days = parse_time_range_days(time_range)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))

    pool = await insight_store.get_pool()
    async with rls_session(pool, tenant_id) as conn:
        drivers, total = await fetch_drivers(
            conn, tenant_id, datasource, kpi_fingerprint, days, offset, limit
        )
    source = "driver_scores" if drivers else "empty"
    return {
        "drivers": drivers,
        "total": total,
        "pagination": {"offset": offset, "limit": limit, "has_more": (offset + limit) < total},
        "meta": {
            "source": source,
            "kpi_fingerprint": kpi_fingerprint,
            "datasource": datasource,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }
```

**SQL** (`insight_query_store.py` `fetch_drivers` 함수):

```sql
SELECT
    column_key,
    role,
    score,
    breakdown,
    cardinality_est,
    sample_size,
    kpi_fingerprint,
    created_at,
    COUNT(*) OVER() AS total_count     -- E3 해결
FROM weaver.insight_driver_scores
WHERE tenant_id = $1
  AND ($2::text IS NULL OR datasource_id = $2)
  AND ($3::text IS NULL OR kpi_fingerprint = $3)
ORDER BY score DESC, created_at DESC
LIMIT $4 OFFSET $5
```

> `column_key` 형식 예: `customers.region`. 응답에 포함해 프론트가 driver_key로 사용 가능하게 함.

#### 3.8 프론트엔드 수정 (선택적)

`DriverRankingPanel`의 클라이언트 파생 방식은 그래프 로드 후 즉시 표시되어 UX상 충분. `/drivers` API는 **그래프 없이 Sidebar를 미리 채우는 시나리오**에서 유용.

프론트 변경은 P0-B 백엔드 완료 후 별도 PR에서 선택적으로 진행.

---

### [P1-A] `GET /api/insight/drivers/{driver_key}` — Driver 상세 + Evidence

**목적**: 특정 Driver의 점수 breakdown + 근거 쿼리 + 값 분포 반환. `useDriverDetail` 스텁 교체.

#### 3.9 driver_key 식별자 정의 (E5 해결)

`column_key`는 `customers.region` 처럼 `.`을 포함한다. URL path parameter로 쓰면 라우터 오작동 가능.

##### 결정: query parameter 방식 사용

```
GET /api/insight/drivers/detail?driver_key=customers.region&time_range=30d
```

또는 path parameter를 쓰되 서버에서 `urllib.parse.unquote` 처리 + 클라이언트에서 `encodeURIComponent` 강제.

> 권장: query parameter. FastAPI는 Query()로 받으면 자동 디코딩 처리.

#### 3.10 evidence 품질 보강 (E6 해결)

단순 LIKE 검색(`normalized_sql LIKE '%customers.region%'`)은 짧은 컬럼명에서 오탐이 많다.

**개선된 evidence 추출 전략**:

1. `normalized_sql`에서 `table_name`과 `column_name`을 **동시** 패턴 매칭:

   ```sql
   WHERE normalized_sql ~* '\bcustomers\b.*\bregion\b|\bregion\b.*\bcustomers\b'
   ```

2. (더 정확) `query_log_analyzer.py`의 AST column reference 추출 결과를 별도 컬럼으로 저장.
   - `insight_query_logs`에 `column_refs JSONB` 추가 → ingest 시 파싱
   - evidence는 `column_refs @> '[{"table":"customers","column":"region"}]'`

P1에서는 방식 1(정규식)로 최소 구현. 품질이 문제가 되면 방식 2로 마이그레이션.

#### 3.11 driver score 없을 때 fallback 계약

`driver_key`가 `insight_driver_scores`에 없으면:

- `404` 반환 + `detail: "Driver score not found. Try running impact analysis first."`
- 프론트(`useDriverDetail`)는 404 시 store의 그래프 노드 데이터로 fallback (현재 동작 유지)

#### 3.12 백엔드 구현

**파일**: `services/weaver/app/api/insight.py`

```python
@router.get("/drivers/detail")
async def get_driver_detail(
    driver_key: str = Query(..., description="column_key (예: customers.region)"),
    time_range: str = "30d",
    tenant_id: str = Depends(get_effective_tenant_id),
):
    try:
        days = parse_time_range_days(time_range)
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))

    pool = await insight_store.get_pool()
    async with rls_session(pool, tenant_id) as conn:
        driver = await fetch_driver_score(conn, tenant_id, driver_key)
        if not driver:
            raise HTTPException(
                404, detail="Driver score not found. Run impact analysis first."
            )
        evidence = await fetch_driver_evidence(conn, tenant_id, driver_key, days)

    return {"driver": driver, "evidence": evidence}
```

`fetch_driver_evidence`: 정규식 매칭 (E6 개선안 1):

```sql
SELECT query_id, normalized_sql, executed_at, COUNT(*) AS count
FROM weaver.insight_query_logs
WHERE tenant_id = $1
  AND executed_at >= NOW() - INTERVAL '{days} days'
  AND normalized_sql ~* $2   -- '\bcustomers\b.*\bregion\b'
GROUP BY query_id, normalized_sql, executed_at
ORDER BY count DESC
LIMIT 5
```

#### 3.13 프론트엔드 수정

**파일**: [features/insight/api/insightApi.ts](apps/canvas/src/features/insight/api/insightApi.ts)

```typescript
export async function fetchDriverDetail(
  driverKey: string,
  timeRange: TimeRange,
): Promise<DriverDetailResponse>
```

**파일**: [features/insight/hooks/useDriverDetail.ts](apps/canvas/src/features/insight/hooks/useDriverDetail.ts)

현재 스텁(21 LOC)을 교체:

```typescript
export function useDriverDetail({ nodeId }: UseDriverDetailOptions) {
  const { selectDriver, timeRange } = useInsightStore();
  const [detail, setDetail] = useState<DriverDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!nodeId) { setDetail(null); return; }
    setLoading(true);
    fetchDriverDetail(nodeId, timeRange)
      .then(setDetail)
      .catch(() => setDetail(null))   // 404 fallback: store 데이터 사용
      .finally(() => setLoading(false));
  }, [nodeId, timeRange]);

  return { detail, loading, close: () => selectDriver(null) };
}
```

---

### [P1-B] Oracle→Weaver 자동 인제스트

**목적**: NL2SQL 실행 후 Weaver에 쿼리 로그 자동 전송. 수동 인제스트 없이 데이터 자동 축적.

#### 3.14 인증 주체 확정 (E7 해결)

Oracle이 Weaver에 POST할 때 사용자 access_token을 재사용하는 방식은 issuer/audience 불일치 위험 + tenant 전파 계약이 불명확하다.

##### 결정: 서비스 토큰 방식 (권장)

Oracle config에 `WEAVER_INSIGHT_TOKEN` 추가. Weaver는 이 토큰을 내부 서비스 전용으로 검증.

```python
# services/oracle/app/core/config.py 추가
WEAVER_INSIGHT_URL: str = "http://weaver:8001/api/insight/logs"
WEAVER_INSIGHT_TOKEN: str = ""   # 내부 서비스 토큰 (docker-compose / k8s secret)
```

```python
headers={
    "Authorization": f"Bearer {settings.WEAVER_INSIGHT_TOKEN}",
    "X-Tenant-Id": tenant_id,   # Oracle이 알고 있는 tenant
    "X-Source": "oracle-nl2sql",
}
```

Weaver `/logs` 엔드포인트: `X-Tenant-Id` 헤더로 tenant 결정 (서비스 토큰 + tenant 헤더 조합). 기존 `get_effective_tenant_id`가 이 헤더를 이미 처리하는지 확인 필요.

> `WEAVER_INSIGHT_TOKEN`이 미설정이면 forwarding을 skip (로그만 기록). 실제 작동 여부를 config 수준에서 명시.

#### 3.15 동시성 제한 (E8 해결)

```python
import asyncio
_INSIGHT_SEMAPHORE = asyncio.Semaphore(10)  # 동시 전송 최대 10

async def _forward_to_insight(
    tenant_id: str,
    sql: str,
    datasource: str,
    duration_ms: int,
    row_count: int | None,
    nl_query: str | None,
    trace_id: str,
):
    if not settings.WEAVER_INSIGHT_TOKEN:
        return  # 미설정 시 skip

    entry = {
        "request_id":   str(uuid4()),
        "trace_id":     trace_id,
        "datasource":   datasource,
        "dialect":      "postgresql",
        "executed_at":  datetime.now(timezone.utc).isoformat(),
        "status":       "success",
        "duration_ms":  duration_ms,
        "row_count":    row_count,
        "nl_query":     nl_query,
        "sql":          sql,
        "tags":         ["nl2sql", "auto"],
    }

    async with _INSIGHT_SEMAPHORE:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(
                    settings.WEAVER_INSIGHT_URL,
                    json={"entries": [entry]},
                    headers={
                        "Authorization": f"Bearer {settings.WEAVER_INSIGHT_TOKEN}",
                        "X-Tenant-Id":   tenant_id,
                        "X-Source":      "oracle-nl2sql",
                    },
                )
        except Exception as exc:
            # 실패는 샘플링해서 로그 폭주 방지
            if random.random() < 0.1:  # 10% 샘플링
                logger.warning("insight_forward_failed: %s", exc)
```

**호출 위치**: `nl2sql.py`의 SQL 실행 완료 직후, 응답 반환 전:

```python
asyncio.create_task(
    _forward_to_insight(
        tenant_id=str(current_user.tenant_id),
        sql=final_sql,
        datasource=datasource_id,
        duration_ms=duration_ms,
        row_count=result.row_count,
        nl_query=nl_query,
        trace_id=request_id,
    )
)
```

#### 3.16 P0-A와의 연계 (옵션 A 선택 시)

P0-A를 "로그 스키마 확장" 방식으로 구현한다면, ingest entry에 `kpi_fingerprint`를 추가:

```python
entry["kpi_fingerprint"] = _detect_kpi_fingerprint(sql, datasource)
# 감지 불가 시 None
```

`_detect_kpi_fingerprint`: SQL에서 aggregate expression 추출 → fingerprint 생성. `query_log_analyzer.py`의 기존 로직 재사용.

---

### [P2-A] `useKpiTimeseries` + `KpiMiniChart`

#### 3.17 데이터 원천 확정 (E9 해결)

`insight_query_logs`에는 KPI "값"이 없다 (`row_count`만 있음). 따라서:

##### Phase 1 (지금 구현 가능) — 활동도(쿼리 횟수) 트렌드

백엔드: `insight_query_logs` 집계 → 날짜별 해당 KPI/driver 관련 쿼리 횟수 반환.

```json
{
  "kpi_name": "AR Balance",
  "series_type": "activity",
  "series": [
    { "date": "2026-02-20", "value": 12, "driver_value": "서울" },
    { "date": "2026-02-21", "value": 8, "driver_value": "서울" }
  ]
}
```

프론트 차트 제목: "쿼리 활동도" (값 트렌드가 아님을 명시).

##### Phase 2 (별도 PR) — 실제 KPI 값 시계열

원천: 실제 DB에 timeseries 쿼리를 다시 실행. 권한/비용/캐시 설계가 추가로 필요.

> **P2-A는 Phase 1 (활동도 트렌드)로 먼저 구현**. 설계서 §4.6의 KPI 값 시계열은 Phase 2에서.

#### 3.18 백엔드 구현

**파일**: `services/weaver/app/api/insight.py`

```python
@router.get("/kpi/activity")   # 활동도 트렌드 (Phase 1)
async def kpi_activity(
    kpi_fingerprint: str,
    driver_key: str | None = None,
    time_range: str = "30d",
    granularity: str = "day",   # "day" | "week"
    tenant_id: str = Depends(get_effective_tenant_id),
):
```

#### 3.19 프론트엔드 구현

**신규 파일**: [features/insight/hooks/useKpiTimeseries.ts](apps/canvas/src/features/insight/hooks/useKpiTimeseries.ts)

```typescript
export function useKpiTimeseries(params: {
  kpiFingerprint: string | null;
  driverKey?: string;
  timeRange: TimeRange;
}) {
  const [data, setData] = useState<ActivityPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!params.kpiFingerprint) return;
    setLoading(true);
    fetchKpiActivity(params)
      .then((r) => setData(r.series))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [params.kpiFingerprint, params.driverKey, params.timeRange]);

  return { data, loading };
}
```

**신규 파일**: [features/insight/components/KpiMiniChart.tsx](apps/canvas/src/features/insight/components/KpiMiniChart.tsx)

구현 방식: 외부 차트 라이브러리 없이 SVG 직접 구현 (번들 크기 최소화). Recharts가 이미 설치돼 있으면 재사용.

---

### [P2-B] `useNodeDataPreview` (Ontology)

#### 3.20 Synapse 의존성 완화 (E10 해결)

설계서 §4.10은 Synapse 서비스에서 `GET /api/ontology/preview/coverage`를 구현해야 하지만, Synapse 신규 개발은 일정 리스크가 크다.

##### Phase 1 (지금 구현 가능) — Weaver 기반 schema + querylog preview

Ontology 노드 클릭 시 Weaver에서 조회 가능한 정보만 표시:

- 해당 테이블/컬럼이 `insight_query_logs`에 등장한 횟수
- 마지막 등장 시각
- 관련 driver score 유무

```
GET /api/insight/schema-coverage?table=customers&column=region
```

구현: `insight_query_logs` + `insight_driver_scores` 조회만으로 가능.

##### Phase 2 — Synapse 실데이터 샘플/커버리지

Synapse 안정화 후 별도 PR.

**신규 파일**: [features/ontology/hooks/useNodeDataPreview.ts](apps/canvas/src/features/ontology/hooks/useNodeDataPreview.ts)

```typescript
export function useNodeDataPreview(nodeId: string | null) {
  const [preview, setPreview] = useState<NodePreview | null>(null);

  useEffect(() => {
    if (!nodeId) return;
    fetchSchemaCoverage(nodeId).then(setPreview).catch(() => setPreview(null));
  }, [nodeId]);

  return preview;
}
```

---

## 4. 구현 순서 및 의존성

```
┌──────────────────────────────────────────────────────┐
│  Sprint 1 (병렬 가능)                                  │
│                                                       │
│  P0-A: GET /kpis + KpiSelector 수정                  │
│    └─ 전제: 옵션 선택 (A=로그확장 or B=AST추출)         │
│                                                       │
│  P1-B: Oracle 자동 인제스트                            │
│    └─ 전제: 인증 토큰 발급 (WEAVER_INSIGHT_TOKEN)       │
└──────────────────────────────────────────────────────┘
         ↓                        ↓
┌──────────────────────────────────────────────────────┐
│  Sprint 2 (병렬 가능)                                  │
│                                                       │
│  P0-B: GET /drivers                                  │
│    └─ 전제: impact_task에 DB 쓰기 추가 (옵션 A)         │
│                                                       │
│  P1-A: GET /drivers/detail + useDriverDetail 수정     │
│    └─ 전제: insight_driver_scores에 데이터 존재 (P0-B) │
└──────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────┐
│  Sprint 3 (독립)                                       │
│                                                       │
│  P2-A: /kpi/activity + useKpiTimeseries + KpiMiniChart│
│  P2-B: /schema-coverage + useNodeDataPreview         │
└──────────────────────────────────────────────────────┘
```

---

## 5. 파일 목록

### P0-A 변경 파일

| 파일 | 변경 유형 | 주요 내용 |
| ------ | --------- | --------- |
| `services/weaver/app/api/insight.py` | 수정 | `GET /kpis` 엔드포인트 |
| `services/weaver/app/services/insight_query_store.py` | 수정 | `fetch_kpis()`, `parse_time_range_days()` |
| `services/weaver/app/services/insight_store.py` | 수정 (옵션 A) | `kpi_fingerprint`, `kpi_name` 컬럼 마이그레이션 추가 |
| `apps/canvas/src/features/insight/api/insightApi.ts` | 수정 | `fetchKpis()` 추가 |
| `apps/canvas/src/features/insight/types/insight.ts` | 수정 | `KpiListItem`, `KpiListResponse` 타입 |
| `apps/canvas/src/features/insight/components/KpiSelector.tsx` | 수정 | 하드코딩 제거, API 연동 |

### P0-B 변경 파일

| 파일 | 변경 유형 | 주요 내용 |
| ------ | --------- | --------- |
| `services/weaver/app/worker/impact_task.py` | 수정 | `_persist_driver_scores()` 추가 (DB 쓰기) |
| `services/weaver/app/api/insight.py` | 수정 | `GET /drivers` 엔드포인트 |
| `services/weaver/app/services/insight_query_store.py` | 수정 | `fetch_drivers()` 추가 |

### P1-A 변경 파일

| 파일 | 변경 유형 | 주요 내용 |
| ------ | --------- | --------- |
| `services/weaver/app/api/insight.py` | 수정 | `GET /drivers/detail` 엔드포인트 |
| `services/weaver/app/services/insight_query_store.py` | 수정 | `fetch_driver_score()`, `fetch_driver_evidence()` |
| `apps/canvas/src/features/insight/api/insightApi.ts` | 수정 | `fetchDriverDetail()` 추가 |
| `apps/canvas/src/features/insight/hooks/useDriverDetail.ts` | 수정 | 스텁 → 실제 API 호출 (21 LOC → ~40 LOC) |

### P1-B 변경 파일

| 파일 | 변경 유형 | 주요 내용 |
| ------ | --------- | --------- |
| `services/oracle/app/api/nl2sql.py` | 수정 | `asyncio.create_task(_forward_to_insight(...))` |
| `services/oracle/app/core/config.py` | 수정 | `WEAVER_INSIGHT_URL`, `WEAVER_INSIGHT_TOKEN` 추가 |

### P2-A 파일

| 파일 | 변경 유형 | 주요 내용 |
| ------ | --------- | --------- |
| `services/weaver/app/api/insight.py` | 수정 | `GET /kpi/activity` 추가 |
| `apps/canvas/src/features/insight/hooks/useKpiTimeseries.ts` | **신규** | 활동도 트렌드 훅 |
| `apps/canvas/src/features/insight/components/KpiMiniChart.tsx` | **신규** | SVG 미니 라인차트 |
| `apps/canvas/src/features/insight/api/insightApi.ts` | 수정 | `fetchKpiActivity()` 추가 |

### P2-B 파일

| 파일 | 변경 유형 | 주요 내용 |
| ------ | --------- | --------- |
| `services/weaver/app/api/insight.py` | 수정 | `GET /insight/schema-coverage` (Weaver 기반, Synapse 불필요) |
| `apps/canvas/src/features/ontology/hooks/useNodeDataPreview.ts` | **신규** | querylog 기반 schema coverage 훅 |

---

## 6. 검증 기준 (Gate) — 단위 테스트 포함

### P0 Gate

#### P0 기능 확인

- [ ] `GET /api/insight/kpis` → 200, `kpis` 배열 + `total` (전체 수) + `pagination.has_more`
- [ ] 빈 DB에서 `kpis: [], total: 0`
- [ ] `KpiSelector` 마운트 시 `/kpis` 호출 (Network 탭)
- [ ] 하드코딩 `SAMPLE_KPIS` 상수 삭제됨
- [ ] `GET /api/insight/drivers` → 200, `meta.source` 필드 포함

#### P0 단위 테스트 (Weaver)

- [ ] `time_range="30d"` → 정상, `time_range="invalid"` → 422
- [ ] `/kpis`: 빈 DB → `[]` + 200 (500 아님)
- [ ] `/drivers`: scores 없을 때 `meta.source: "empty"` + `[]` + 200
- [ ] RLS: tenant A 로그가 tenant B `/kpis` 응답에 미포함

### P1 Gate

#### P1 기능 확인

- [ ] `GET /api/insight/drivers/detail?driver_key=customers.region` → 200, `driver.score` + `evidence` 포함
- [ ] NL2SQL 실행 후 Weaver `/logs`에 자동 POST 확인 (Weaver 로그 또는 DB row)
- [ ] Oracle NL2SQL 응답 시간 변화 없음 (fire-and-forget 검증)
- [ ] `useDriverDetail` → `NodeDetailPanel`에 서버 데이터 표시

#### P1 단위 테스트

- [ ] `driver_key` 없는 레코드 → 404 + 명확한 메시지
- [ ] `fetch_driver_evidence`: 테이블+컬럼 동시 매칭, 컬럼명만 단독 LIKE 금지
- [ ] Oracle `WEAVER_INSIGHT_TOKEN` 미설정 시 → forwarding skip, NL2SQL 정상 반환
- [ ] 동시 10+개 요청 시 세마포어로 정확히 10개만 동시 전송

### P2 Gate

- [ ] `GET /kpi/activity` → 200, `series_type: "activity"` 확인
- [ ] `KpiMiniChart` → 데이터 포인트가 SVG 경로로 렌더링됨
- [ ] `useNodeDataPreview` → Ontology 노드 클릭 시 querylog count 표시
- [ ] `GET /schema-coverage` 빈 결과 → 200 + `count: 0` (404 아님)

---

## 7. 위험 요소 — 수정된 대응 포함

| 위험 | 발생 조건 | 대응 |
| ------ | --------- | ------ |
| KPI fingerprint 불일치 | P0-A와 P1-B가 다른 로직으로 fingerprint 생성 | `compute_kpi_fingerprint()` 함수를 `fingerprintUtils.ts` / `insight_query_store.py`에 각각 SSOT로 구현 |
| `insight_driver_scores` 빈 상태 | P0-B 이전에 P1-A를 호출 | P0-B Gate 통과 후 P1-A 개발 시작 (순서 의존성 명시) |
| Oracle WEAVER_INSIGHT_TOKEN 미발급 | 배포 환경 변수 누락 | `is_configured` 가드로 skip. docker-compose 예시에 주석 추가 |
| Weaver의 X-Tenant-Id 헤더 미지원 | Oracle에서 tenant를 헤더로 전달해도 Weaver가 무시 | `get_effective_tenant_id`에서 헤더 처리 여부 확인 후 필요 시 수정 |
| driver_id URL 인코딩 오염 | 프론트가 `encodeURIComponent` 미적용 | query parameter 방식으로 E5 해결 완료. path param 사용 금지 |
| timeseries 원천 부재 | `/kpi/timeseries` 구현 전 framing 오류 | P2-A를 "활동도 트렌드"로 먼저 구현. KPI 값 시계열은 별도 issue로 이관 |
