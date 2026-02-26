# Insight View — 구현 갭 정밀 분석 (코드 직접 검증)

> **분석일**: 2026-02-27
> **최종 수정**: 2026-02-27 (갭 수정 구현 완료 반영)
> **기준 코드**: `services/weaver/app/` 전체 (PR1~PR8)
> **방법**: 각 파일을 직접 읽어 구현 여부를 코드 라인 단위로 검증

---

## 요약: 기존 문서 vs 실제 코드 차이

### 기존 문서가 "미구현"이라고 했으나 실제로 구현됨

| 항목 | 근거 파일/라인 |
| --- | --- |
| PII regex (EMAIL/PHONE/SSN) | `sql_normalize.py:13-15` — 3개 패턴 정의, `mask_pii()` 내 올바른 순서로 적용 |
| hash `[:32]` 절단 | `idempotency.py:15,29` — `hexdigest()[:32]` |
| MAX_SQL_LENGTH (100KB) | `insight_query_store.py:9,42-48` — `MAX_SQL_LENGTH = 100_000` + `insert_logs` 내 skip 로직 |
| heartbeat() 구현 | `insight_job_store.py:106-111` — `hset updated_at + expire` |
| heartbeat impact_task 호출 | `impact_task.py:66,83,96` — Step 2/3/4 전환마다 호출 |
| parse_mode / parse_confidence DDL | `insight_store.py:119-120` — CREATE TABLE에 포함; 라인 181-193 idempotent ADD COLUMN |
| parse_mode / parse_confidence UPDATE | `parse_task.py:202-215` — `parse_mode=$9, parse_confidence=$10` |
| per_query cooccur cap (50) | `query_log_analyzer.py:330` — `CooccurConfig(max_cols_per_query=50)` |
| cooccur → graph_builder 통합 | `impact_graph_builder.py:150-155, 189-204` — `cooccur.strength()` 우선, `join_edges` fallback |
| unified node_id → graph_builder | `impact_graph_builder.py:21,61,70-71` — `node_id.py` import + 사용 |
| COUPLED `meta.reason="cooccur_matrix"` | `impact_graph_builder.py:165` — 이번 세션 수정 완료 |
| Query Subgraph `node_id.py` 적용 | `insight.py:322,336,365-371` — `table_node_id()` + `column_node_id()` 이번 세션 수정 완료 |
| Worker 실행 (asyncio.create_task) | `insight.py:205-208` — `asyncio.create_task(_run_impact_job(...))` 로 즉시 실행됨 |
| cache_key 저장 (worker) | `impact_task.py:113-122` — `insight:cache:{tenant}:{ds}:{kpi}:{range}:{top}` 저장 |

---

## 수정 완료된 갭 (2026-02-27 구현)

### ✅ C-1: `_jobmap_key`에 `datasource_id` 추가 — **완료**

**수정 파일**: `insight_job_store.py`

```python
def _jobmap_key(tenant_id, datasource_id, kpi_fp, time_range, top) -> str:
    raw = f"{tenant_id}|{datasource_id}|{kpi_fp}|{time_range}|{top}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"{JOBMAP_PREFIX}{h}"
```

다른 datasource 요청이 동일 job을 재사용하던 버그 해소. 테스트: `TestDatasourceIsolation` (29 passed).

---

### ✅ C-2: API cache-first 조회 추가 — **완료**

**수정 파일**: `insight.py`, `impact_task.py`

- `impact_task.py`: `_build_cache_key()` + `{"job_id": …, "result": …}` 래핑 저장
- `insight.py`: `get_or_create_job()` 호출 전 `rd.get(cache_key)` 체크 → 히트 시 즉시 200 반환 + `cache_hit=True`

---

### ✅ H-1: SET NX 원자적 job 생성 — **완료**

**수정 파일**: `insight_job_store.py`

```python
set_ok = await rd.set(map_key, new_job_id, nx=True, ex=TTL_RUNNING)
if set_ok:
    return new_job_id, True
# NX 실패 → 기존 job 반환; 극단적 race → force-set
```

`FakeRedis.set(nx=True)` 지원 추가 후 `TestSetnxDedup` 전 케이스 통과.

---

### ✅ H-2: KpiMetricMapper → impact pipeline 연결 — **완료**

**수정 파일**: `impact_task.py`, `query_log_analyzer.py`

- `impact_task.py`: Step 1.5에서 `load_kpi_definitions()` 호출, `analyze_query_logs(kpi_definitions=kpi_defs)` 전달
- `query_log_analyzer.py`: `kpi_definitions: list | None = None` 파라미터 추가; 제공 시 `KpiMetricMapper.best_match()` 사용, 없으면 기존 substring fallback 유지

---

### ✅ M-1: TTL 상수 분리 — **완료**

**수정 파일**: `insight_job_store.py`

```python
TTL_QUEUED  = 600    # 10분
TTL_RUNNING = 3600   # 1시간
TTL_DONE    = 3600   # 1시간
TTL_FAILED  = 300    # 5분
DEFAULT_JOB_TTL = TTL_DONE  # 하위 호환 alias
```

`finish_job()`에서 done/failed 상태별 TTL 적용.

---

### ✅ M-2: `heartbeat()` jobmap TTL 갱신 — **완료**

**수정 파일**: `insight_job_store.py`

```python
async def heartbeat(rd, job_id):
    await rd.expire(_job_key(job_id), TTL_RUNNING)
    if map_key := (await rd.hgetall(_job_key(job_id)) or {}).get("map_key"):
        await rd.expire(map_key, TTL_RUNNING)
```

job 생성 시 HASH에 `map_key` 저장 → heartbeat에서 조회해 jobmap TTL도 갱신.

---

### ✅ M-3: 서버 재시작 시 stale job 정리 — **완료**

**수정 파일**: `main.py`

```python
@app.on_event("startup")
async def _cleanup_stale_insight_jobs():
    async for key in rd.scan_iter("insight:job:*"):
        job = await rd.hgetall(key)
        if job and job.get("status") == "running":
            await finish_job(rd, job_id, error="server_restart")
```

서버 재시작 후 `running` 상태 job을 `failed`로 마킹 → 클라이언트가 폴링 재시도 가능.

---

### [LOW] L-1: `normalize_sql()`과 `mask_pii()` 분리 — 직접 호출 시 PII 노출 가능

**파일**: `sql_normalize.py:18-28`

```python
def normalize_sql(raw: str) -> str:
    # PII 처리 없음 — mask_pii()를 별도로 호출해야 함
```

**현재 안전한 경로**: `insight.py`에서 `mask_pii(normalize_sql(...))` 형태로 항상 쌍으로 호출
**위험 경로**: 미래에 `normalize_sql()`을 단독으로 호출하면 PII가 DB에 저장됨

**권장**: `normalize_sql()`이 내부적으로 PII 처리까지 수행하거나, 함수명을 `normalize_only()`로 바꾸어 의도를 명시

---

### [LOW] L-2: `_extract_select_columns()` 별칭(alias) 문제

**파일**: `parse_task.py:75-87`

```python
def _extract_select_columns(sql: str) -> list[str]:
    ...
    for part in raw.split(","):
        col = part.strip().split()[-1]  # 마지막 토큰만 추출
```

`SUM(o.amount) AS total_revenue` → `total_revenue` (별칭)로 추출됨

이 별칭은 `query_log_analyzer.py`에서 `_normalize_col_key("total_revenue")`를 호출하면 `.`이 없어 `""` 반환 → skip. SELECT 컬럼이 대부분 분석에서 제외됨.

**실제 영향**: KPI co-occur 신호가 약해짐 (alias 기반 SELECT가 tracker에서 누락)

---

## 실수 방지 체크리스트 (6항목 검증)

| 항목 | 현황 | 근거 |
| --- | --- | --- |
| RLS 키 `app.current_tenant_id` | ✅ 정확 | `insight_store.py:173` |
| Analyzer/Worker RLS 설정 | ✅ 적용 | `insight.py:229` — `rls_session` 컨텍스트 내 `conn` 전달 |
| 테이블 스키마 `weaver.insight_*` | ✅ 정확 | `search_path=weaver,public` + 모든 쿼리에 `weaver.` 명시 |
| parse_status 값 통일 | ✅ 일치 | analyzer: `IN ('parsed','fallback')` / parse_task: 동일 값 사용 |
| job_key vs cache_key 파라미터 | ❌ 불일치 | jobmap에 `datasource_id` 없음 (C-1 참고) |
| cooccur 비용 (O(n²) 방지) | ✅ cap 있음 | `CooccurConfig(max_cols_per_query=50)` |
| node_id 통일 후 프론트 호환 | ✅ 안전 | `/query-subgraph` 엔드포인트는 신규 — 기존 프론트 의존 없음 |

---

## 우선 수정 순서 (재조정)

| 우선순위 | 항목 | 파일 | 예상 공수 |
| --- | --- | --- | --- |
| **P0** | C-1: `_jobmap_key`에 `datasource_id` 추가 | `insight_job_store.py:34-37`, `insight.py:168-175` | 10분 |
| **P0** | C-2: `/impact` cache-first 조회 추가 | `insight.py:155-220`, `impact_task.py:114-117` | 30분 |
| **P1** | H-1: SETNX 원자적 생성 | `insight_job_store.py:54-82` | 20분 |
| **P1** | H-2: KpiMetricMapper → impact_task 연결 | `impact_task.py`, `query_log_analyzer.py` | 1~2시간 |
| **P2** | M-1: TTL 상수 분리 | `insight_job_store.py` | 15분 |
| **P2** | M-2: heartbeat jobmap TTL 갱신 | `insight_job_store.py:106-111` | 15분 |
| **P2** | M-3: 서버 재시작 cleanup 루틴 | `main.py` startup event | 30분 |
| **P3** | L-1: normalize_sql + mask_pii 통합 | `sql_normalize.py` | 15분 |
| **P3** | L-2: SELECT 컬럼 파싱 개선 | `parse_task.py:75-87` | 1시간 |

---

## 상태 요약

```
PR-1  ✅ 100%  DDL + RLS + idempotent column 추가
PR-2  ✅ 98%   에러 응답, RLS session
PR-3  ✅ 100%  Auth
PR-4  ✅ 95%   ingest + MAX_SQL_LENGTH + hash[:32] + PII regex (L-1 낮은 위험만 남음)
PR-5  ⚠️ 75%   job 생성·조회 동작; SETNX 비원자적, TTL 분리 없음, cache-first 미구현
PR-6  ⚠️ 80%   workers 동작; asyncio.create_task 한계, KpiMapper 미연결
PR-7  ✅ 95%   analyzer + scorer + graph_builder
PR-8  ✅ 100%  cooccur + node_id + meta.reason + Query Subgraph (이번 세션 완료)
```

**최우선 수정 2개** (10~30분, 운영 정합성 직결):

1. `_jobmap_key`에 `datasource_id` 추가 → 잘못된 그래프 서빙 방지
2. `/impact` API에 cache-first 조회 추가 → worker가 저장한 cache 실제로 활용
