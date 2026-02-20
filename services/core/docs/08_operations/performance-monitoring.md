# 성능 최적화 및 모니터링 전략

<!-- affects: operations, backend, frontend, data -->
<!-- requires-update: 각 서비스 08_operations/deployment.md -->

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **범위**: Cross-service (Core, Oracle, Vision, Synapse, Weaver, Canvas)

---

## 이 문서가 답하는 질문

- Axiom 전체의 SLO/SLA 목표는 무엇인가?
- 각 서비스별 성능 최적화 전략은 무엇인가?
- Prometheus 메트릭 체계와 Grafana 대시보드 구성은?
- 알림(Alert) 규칙과 대응 절차는?
- 분산 추적(Tracing)과 로그 집중화 전략은?
- 성능 테스트와 용량 계획은 어떻게 수행하는가?

---

## 1. SLO/SLA 정의

### 1.1 서비스별 SLO 목표

| 서비스 | 엔드포인트 유형 | p50 | p95 | p99 | 가용성 | 에러율 |
|--------|---------------|-----|-----|-----|--------|--------|
| **Core** | API (CRUD) | < 100ms | < 500ms | < 1s | 99.9% | < 0.1% |
| **Core** | Worker (비동기) | < 5s | < 15s | < 30s | 99.5% | < 1% |
| **Oracle** | NL2SQL (LLM 포함) | < 3s | < 8s | < 15s | 99.5% | < 2% |
| **Oracle** | 캐시 히트 응답 | < 200ms | < 500ms | < 1s | 99.9% | < 0.1% |
| **Vision** | OLAP 피벗 쿼리 | < 500ms | < 2s | < 5s | 99.5% | < 0.5% |
| **Vision** | What-if 시뮬레이션 | < 10s | < 30s | < 60s | 99.0% | < 2% |
| **Synapse** | 문서 추출 (LLM) | < 30s | < 60s | < 120s | 99.0% | < 3% |
| **Synapse** | 온톨로지 검색 | < 200ms | < 500ms | < 1s | 99.5% | < 0.5% |
| **Weaver** | 메타데이터 조회 | < 300ms | < 1s | < 2s | 99.5% | < 0.5% |
| **Weaver** | 크로스 DB 쿼리 | < 5s | < 15s | < 30s | 99.0% | < 2% |
| **Canvas** | 초기 로드 (LCP) | < 1.5s | < 2.5s | < 4s | 99.9% | < 0.1% |
| **Canvas** | 인터랙션 (FID) | < 50ms | < 100ms | < 200ms | - | - |

### 1.2 SLI 측정 방법

```
SLI 공식:

가용성 = (성공 응답 수 / 전체 요청 수) × 100
지연 SLI = (SLO 이내 응답 수 / 전체 요청 수) × 100
에러율 = (5xx 응답 수 / 전체 요청 수) × 100

에러 버짓:
  99.9% 가용성 → 월 43분 다운타임 허용
  99.5% 가용성 → 월 3.6시간 다운타임 허용
  99.0% 가용성 → 월 7.3시간 다운타임 허용

에러 버짓 소진 시:
  1. 신규 기능 배포 중단
  2. 안정성 개선 작업 우선
  3. 포스트모템 작성
```

### 1.3 SLA 등급 (고객 약정)

| 등급 | 가용성 | 대상 | 위반 시 |
|------|--------|------|---------|
| **Tier 1** | 99.9% | Core API, Canvas | 에스컬레이션 + 즉시 대응 |
| **Tier 2** | 99.5% | Oracle, Vision, Weaver | 4시간 내 대응 |
| **Tier 3** | 99.0% | Synapse (배치), Worker | 다음 영업일 대응 |

---

## 2. 성능 최적화 전략

### 2.1 레이어별 최적화 맵

```
┌─ 성능 최적화 레이어 ─────────────────────────────────────────────┐
│                                                                    │
│  Layer 1: 프론트엔드 (Canvas)                                     │
│  ├── 코드 스플리팅 (라우트별 청크, < 200KB gzip 초기 로드)        │
│  ├── TanStack Query 캐시 (staleTime/gcTime 데이터별 차등)         │
│  ├── WebSocket 기반 캐시 무효화 (폴링 제거)                       │
│  ├── 낙관적 업데이트 (승인/읽음 등 즉시 반영)                     │
│  └── 프리페칭 (hover 시 상세 데이터 선로드)                       │
│                                                                    │
│  Layer 2: API Gateway / 인증                                      │
│  ├── Redis Rate Limiting (슬라이딩 윈도우, 100 req/min)           │
│  ├── JWT 검증 (HS256, 15분 만료)                                  │
│  └── CORS 사전 검사 캐시 (Access-Control-Max-Age: 3600)           │
│                                                                    │
│  Layer 3: 애플리케이션 서비스                                     │
│  ├── Connection Pool (pool_size=20, max_overflow=80)              │
│  ├── LLM 응답 캐시 (Redis, 동일 입력 재활용)                     │
│  ├── asyncio 기반 비동기 I/O (블로킹 작업 제로)                   │
│  └── ContextVar 멀티테넌트 (요청 격리, RLS 이중 보호)             │
│                                                                    │
│  Layer 4: 데이터 계층                                             │
│  ├── PostgreSQL 인덱스 전략 (B-tree, GIN for JSONB)               │
│  ├── Neo4j HNSW 벡터 인덱스 (수십ms 검색)                        │
│  ├── Materialized View (Vision OLAP, 서브초 응답)                 │
│  ├── Redis Streams (밀리초 이벤트 전달)                            │
│  └── Event Outbox (DB 트랜잭션 + 이벤트 원자성)                   │
│                                                                    │
│  Layer 5: 인프라                                                  │
│  ├── EKS HPA (CPU 70% 오토스케일)                                 │
│  ├── Redis maxmemory-policy=allkeys-lru                           │
│  ├── Nginx gzip + immutable 캐시 (정적 파일 1년)                  │
│  └── Docker 멀티스테이지 빌드 (이미지 최소화)                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 2.2 서비스별 핵심 성능 설정

#### Core

| 설정 | 값 | 근거 |
|------|-----|------|
| `DB_POOL_SIZE` | 20 | 기본 커넥션 수 |
| `DB_MAX_OVERFLOW` | 80 | 피크 시 최대 100 커넥션 |
| `pool_recycle` | 3600 | PostgreSQL idle timeout 대응 |
| `pool_pre_ping` | True | 끊어진 커넥션 자동 감지 |
| `WORKER_POLL_INTERVAL` | 5초 | Event Outbox 폴링 간격 |
| `RATE_LIMIT_DEFAULT` | 100 req/min | 테넌트별 기본 속도 제한 |
| Redis maxmemory | 256MB (dev) | allkeys-lru 정책 |

#### Oracle

| 설정 | 값 | 근거 |
|------|-----|------|
| `ORACLE_SQL_TIMEOUT` | 30초 | SQL 실행 최대 대기 |
| `ORACLE_MAX_ROWS` | 10,000 | 메모리 보호 |
| `ORACLE_ROW_LIMIT` | 1,000 | API 응답 크기 제한 |
| `ORACLE_MAX_JOIN_DEPTH` | 5 | SQL 복잡도 제한 |
| `ORACLE_MAX_SUBQUERY_DEPTH` | 3 | 서브쿼리 깊이 제한 |
| `ORACLE_VECTOR_TOP_K` | 10 | 벡터 검색 후보 수 |
| `ORACLE_CONF_THRESHOLD` | 0.90 | 캐시 승인 임계값 |

#### Vision

| 설정 | 값 | 근거 |
|------|-----|------|
| `QUERY_TIMEOUT` | 30초 | OLAP 쿼리 타임아웃 |
| `SCENARIO_SOLVER_TIMEOUT` | 60초 | What-if 솔버 타임아웃 |
| `REDIS_CACHE_TTL` | 3600초 | 피벗 결과 1시간 캐시 |
| `MAX_ROWS` | 1,000 | 단일 쿼리 행 제한 |
| `ETL_SYNC_INTERVAL` | 3600초 | MV 자동 새로고침 주기 |
| MV CONCURRENT REFRESH | 활성화 | 읽기 중단 없는 갱신 |

#### Synapse

| 설정 | 값 | 근거 |
|------|-----|------|
| `MAX_CONCURRENT_EXTRACTIONS` | 5 | LLM 동시 호출 제한 |
| `HITL_CONFIDENCE_THRESHOLD` | 0.75 | HITL 분기 임계값 |
| Neo4j `heap.max_size` | 4GB (prod) | 그래프 탐색 메모리 |
| Neo4j `pagecache.size` | 4GB (prod) | 인덱스 캐시 |
| 벡터 검색 지연 목표 | < 200ms | HNSW 인덱스 최적화 |

#### Weaver

| 설정 | 값 | 근거 |
|------|-----|------|
| `MINDSDB_TIMEOUT` | 120초 | 크로스 DB 조인 타임아웃 |
| Uvicorn 워커 수 | CPU × 2 | 동시 요청 처리 |
| HTTP keepalive | 활성화 | 커넥션 재사용 |
| MindsDB 메모리 | 8GB (prod) | 크로스 DB 조인 메모리 |

### 2.3 캐시 전략 통합 뷰

```
┌─ 멀티 레이어 캐시 아키텍처 ──────────────────────────────────────┐
│                                                                    │
│  L1: 브라우저 캐시 (Canvas)                                       │
│  ├── TanStack Query (인메모리, 페이지 내)                         │
│  │   ├── 케이스 목록: staleTime 1분, gcTime 10분                  │
│  │   ├── OLAP 결과: staleTime 10분, gcTime 1시간                  │
│  │   └── 온톨로지: staleTime 30분, gcTime 2시간                   │
│  ├── Nginx immutable 캐시 (정적 자산, 1년)                        │
│  └── Service Worker (오프라인 대비, 향후)                          │
│                                                                    │
│  L2: Redis 캐시 (서버사이드)                                      │
│  ├── API 응답 캐시 (GET 요청, TTL 5분)                            │
│  ├── LLM 응답 캐시 (동일 프롬프트, TTL 1시간)                     │
│  ├── 세션/토큰 (Refresh Token 블랙리스트, TTL 7일)                │
│  ├── Rate Limiting 카운터 (INCR + EXPIRE, 1분)                    │
│  └── 멱등성 키 (이벤트 중복 방지, TTL 24시간~7일)                 │
│                                                                    │
│  L3: 애플리케이션 캐시                                            │
│  ├── Oracle Query 노드 (Neo4j, 유사 질문 벡터 캐시)               │
│  ├── Oracle ValueMapping (Neo4j, 고유명사→DB값)                    │
│  ├── Oracle Enum 캐시 (부트스트랩, 카테고리 값 사전 로드)          │
│  └── Vision MV (PostgreSQL Materialized View)                      │
│                                                                    │
│  L4: DB 레벨 캐시                                                 │
│  ├── PostgreSQL shared_buffers (25% RAM)                           │
│  ├── Neo4j page cache (pagecache.size, 4GB prod)                   │
│  └── PostgreSQL query plan cache                                   │
│                                                                    │
│  캐시 무효화 전략:                                                │
│  ├── L1: WebSocket 이벤트 → invalidateQueries()                   │
│  ├── L2: TTL 만료 + Mutation 후 삭제                              │
│  ├── L3: 수동 갱신 API + 데이터 변경 이벤트                       │
│  └── L4: REFRESH MATERIALIZED VIEW CONCURRENTLY                    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Prometheus 메트릭 체계

### 3.1 메트릭 네이밍 규약

```
{service}_{subsystem}_{metric_name}_{unit}

예시:
  core_api_request_duration_seconds        (Histogram)
  oracle_llm_tokens_total                  (Counter)
  synapse_neo4j_connection_pool_usage      (Gauge)
  vision_pivot_query_duration_seconds      (Histogram)
  canvas_web_vitals_lcp_seconds            (Histogram)
```

### 3.2 서비스별 Prometheus 메트릭

#### Core 메트릭

| 메트릭 | 유형 | 라벨 | 설명 |
|--------|------|------|------|
| `core_api_request_duration_seconds` | Histogram | method, path, status | API 요청 처리 시간 |
| `core_api_requests_total` | Counter | method, path, status | 총 API 요청 수 |
| `core_db_pool_active_connections` | Gauge | - | 활성 DB 커넥션 수 |
| `core_db_pool_overflow` | Gauge | - | 오버플로우 커넥션 수 |
| `core_redis_operations_total` | Counter | operation, status | Redis 명령 수 |
| `core_redis_latency_seconds` | Histogram | operation | Redis 지연 |
| `core_event_outbox_pending` | Gauge | - | 미발행 이벤트 수 |
| `core_event_outbox_published_total` | Counter | event_type | 발행 완료 이벤트 수 |
| `core_event_outbox_failed_total` | Counter | event_type | 발행 실패 이벤트 수 |
| `core_worker_processing_duration_seconds` | Histogram | worker_type | Worker 처리 시간 |
| `core_worker_queue_depth` | Gauge | stream, group | Consumer Group 대기 메시지 |
| `core_llm_request_duration_seconds` | Histogram | provider, model | LLM 호출 지연 |
| `core_llm_tokens_total` | Counter | provider, model, direction | 토큰 사용량 (input/output) |
| `core_llm_errors_total` | Counter | provider, error_type | LLM 에러 수 |
| `core_rate_limit_exceeded_total` | Counter | tenant_id | 속도 제한 초과 횟수 |
| `core_circuit_breaker_state` | Gauge | target_service | Circuit Breaker 상태 (0=closed, 1=open, 2=half_open) |
| `core_circuit_breaker_trips_total` | Counter | target_service | Circuit Breaker OPEN 전환 횟수 |
| `core_dlq_depth` | Gauge | stream | DLQ 대기 메시지 수 |
| `core_dlq_messages_total` | Counter | stream | DLQ 이동 총 메시지 수 |

#### Oracle 메트릭

| 메트릭 | 유형 | 라벨 | 설명 |
|--------|------|------|------|
| `oracle_requests_total` | Counter | endpoint, status | 총 요청 수 |
| `oracle_request_duration_seconds` | Histogram | endpoint | 요청 처리 시간 |
| `oracle_sql_execution_duration_seconds` | Histogram | - | SQL 실행 시간 |
| `oracle_llm_calls_total` | Counter | purpose | LLM 호출 수 (sql_gen, hyde, judge 등) |
| `oracle_llm_tokens_total` | Counter | model, purpose | 토큰 사용량 |
| `oracle_cache_hits_total` | Counter | cache_type | 캐시 히트 (query, enum, value_mapping) |
| `oracle_cache_misses_total` | Counter | cache_type | 캐시 미스 |
| `oracle_guard_rejects_total` | Counter | reason | SQL Guard 거부 |
| `oracle_neo4j_query_duration_seconds` | Histogram | query_type | Neo4j 쿼리 시간 |
| `oracle_active_connections` | Gauge | db_type | 활성 커넥션 (target_db, neo4j) |
| `oracle_quality_gate_results_total` | Counter | decision | 품질 게이트 결과 (approve, pending, reject) |

#### Vision 메트릭

| 메트릭 | 유형 | 라벨 | 설명 |
|--------|------|------|------|
| `vision_pivot_query_duration_seconds` | Histogram | cube_name | 피벗 쿼리 시간 |
| `vision_scenario_compute_duration_seconds` | Histogram | solver_method | 시나리오 솔버 시간 |
| `vision_etl_sync_duration_seconds` | Histogram | sync_type | ETL 동기화 시간 |
| `vision_llm_call_duration_seconds` | Histogram | node | NL→피벗 LLM 호출 시간 |
| `vision_active_computations` | Gauge | - | 진행 중 계산 수 |
| `vision_cache_hit_ratio` | Gauge | - | Redis 캐시 히트율 |
| `vision_mv_refresh_duration_seconds` | Histogram | mv_name | MV 갱신 시간 |
| `vision_mv_row_count` | Gauge | mv_name | MV 행 수 |

#### Synapse 메트릭

| 메트릭 | 유형 | 라벨 | 설명 |
|--------|------|------|------|
| `synapse_extraction_duration_seconds` | Histogram | extraction_type | 추출 소요 시간 |
| `synapse_extraction_queue_length` | Gauge | - | 추출 대기열 길이 |
| `synapse_hitl_pending_count` | Gauge | - | HITL 대기 항목 |
| `synapse_neo4j_pool_usage` | Gauge | - | Neo4j 커넥션 풀 사용률 |
| `synapse_neo4j_query_duration_seconds` | Histogram | query_type | Neo4j 쿼리 시간 |
| `synapse_llm_error_rate` | Gauge | - | LLM 에러율 (5분 윈도우) |
| `synapse_vector_search_duration_seconds` | Histogram | - | 벡터 검색 시간 |
| `synapse_ontology_node_count` | Gauge | node_type | 온톨로지 노드 수 |

#### Weaver 메트릭

| 메트릭 | 유형 | 라벨 | 설명 |
|--------|------|------|------|
| `weaver_metadata_sync_duration_seconds` | Histogram | datasource | 메타데이터 동기화 시간 |
| `weaver_mindsdb_query_duration_seconds` | Histogram | - | MindsDB 쿼리 시간 |
| `weaver_mindsdb_health` | Gauge | - | MindsDB 상태 (1=healthy, 0=unhealthy) |
| `weaver_neo4j_health` | Gauge | - | Neo4j 상태 |
| `weaver_active_datasources` | Gauge | - | 활성 데이터소스 수 |
| `weaver_schema_introspection_duration_seconds` | Histogram | db_type | 스키마 추출 시간 |

### 3.3 Prometheus 스크래핑 설정

```yaml
# prometheus/prometheus.yml

global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'axiom-core'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: core-api
        action: keep
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: 'axiom-oracle'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: oracle
        action: keep
    metrics_path: /metrics

  - job_name: 'axiom-vision'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: vision
        action: keep
    metrics_path: /metrics

  - job_name: 'axiom-synapse'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: synapse
        action: keep
    metrics_path: /metrics

  - job_name: 'axiom-weaver'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_label_app]
        regex: weaver
        action: keep
    metrics_path: /metrics

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'postgresql'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'neo4j'
    static_configs:
      - targets: ['neo4j:2004']
    metrics_path: /metrics
```

### 3.4 FastAPI Prometheus 미들웨어 구현

```python
# 각 서비스 공통 패턴: app/core/metrics.py

from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

# 공통 메트릭
REQUEST_COUNT = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds",
    "API request latency",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
)
ACTIVE_REQUESTS = Gauge(
    "api_active_requests",
    "Currently processing requests"
)

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path in ("/metrics", "/health", "/health/ready"):
            return await call_next(request)

        method = request.method
        path = self._normalize_path(request.url.path)

        ACTIVE_REQUESTS.inc()
        start = time.perf_counter()

        try:
            response = await call_next(request)
            status = str(response.status_code)
        except Exception:
            status = "500"
            raise
        finally:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(duration)
            ACTIVE_REQUESTS.dec()

        return response

    def _normalize_path(self, path: str) -> str:
        """UUID 등을 마스킹하여 카디널리티 제한"""
        import re
        return re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}", path
        )

# /metrics 엔드포인트
async def metrics_endpoint(request):
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

---

## 4. 알림 규칙 및 대응 절차

### 4.1 통합 알림 규칙

```yaml
# alertmanager/rules/axiom-alerts.yml

groups:
  - name: axiom-availability
    rules:
      # 서비스 다운
      - alert: ServiceDown
        expr: up{job=~"axiom-.*"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} 서비스 다운"
          runbook: "서비스 Pod 상태 확인 → kubectl get pods"

      # 높은 에러율
      - alert: HighErrorRate
        expr: |
          sum(rate(api_requests_total{status=~"5.."}[5m])) by (job)
          / sum(rate(api_requests_total[5m])) by (job) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.job }} 에러율 {{ $value | humanizePercentage }}"

      - alert: CriticalErrorRate
        expr: |
          sum(rate(api_requests_total{status=~"5.."}[5m])) by (job)
          / sum(rate(api_requests_total[5m])) by (job) > 0.20
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "{{ $labels.job }} 에러율 {{ $value | humanizePercentage }} - 즉시 대응"

  - name: axiom-latency
    rules:
      # API 지연
      - alert: HighLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(api_request_duration_seconds_bucket[5m])) by (job, le)
          ) > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.job }} p95 지연 {{ $value }}s"

      # LLM 지연
      - alert: LLMHighLatency
        expr: |
          histogram_quantile(0.95,
            sum(rate(core_llm_request_duration_seconds_bucket[5m])) by (provider, le)
          ) > 15
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "LLM {{ $labels.provider }} p95 지연 {{ $value }}s"

  - name: axiom-resources
    rules:
      # DB 커넥션 풀 고갈
      - alert: DBPoolExhaustion
        expr: core_db_pool_active_connections > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DB 커넥션 풀 {{ $value }}/100 사용 중"

      # Redis 메모리
      - alert: RedisHighMemory
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Redis 메모리 {{ $value | humanizePercentage }} 사용"

      # Event Outbox 적체
      - alert: OutboxBacklog
        expr: core_event_outbox_pending > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Event Outbox {{ $value }}건 적체"

      # Neo4j 커넥션 풀
      - alert: Neo4jPoolHigh
        expr: synapse_neo4j_pool_usage > 0.80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Neo4j 커넥션 풀 {{ $value | humanizePercentage }} 사용"

      # Circuit Breaker 오픈
      - alert: CircuitBreakerOpen
        expr: core_circuit_breaker_state > 0
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Circuit Breaker OPEN: {{ $labels.target_service }}"
          runbook: "resilience-patterns.md §8.2 참조"

      # DLQ 적체
      - alert: DLQBacklog
        expr: core_dlq_depth > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "DLQ {{ $labels.stream }}에 {{ $value }}건 적체"
          runbook: "resilience-patterns.md §8.8 참조"

  - name: axiom-llm
    rules:
      # LLM 에러율
      - alert: LLMErrorRate
        expr: |
          sum(rate(core_llm_errors_total[5m])) by (provider)
          / sum(rate(core_llm_request_duration_seconds_count[5m])) by (provider) > 0.10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "LLM {{ $labels.provider }} 에러율 {{ $value | humanizePercentage }}"

      # 토큰 예산 소진
      - alert: TokenBudgetHigh
        expr: core_llm_tokens_total > 800000  # 일일 1M 중 80%
        labels:
          severity: warning
        annotations:
          summary: "일일 토큰 예산 80% 소진"

  - name: axiom-business
    rules:
      # Oracle 캐시 히트율 저조
      - alert: LowCacheHitRate
        expr: |
          sum(rate(oracle_cache_hits_total[1h]))
          / (sum(rate(oracle_cache_hits_total[1h])) + sum(rate(oracle_cache_misses_total[1h])))
          < 0.30
        for: 30m
        labels:
          severity: info
        annotations:
          summary: "Oracle 캐시 히트율 {{ $value | humanizePercentage }} - Enum 부트스트랩 확인"

      # Synapse HITL 대기 과다
      - alert: HITLBacklog
        expr: synapse_hitl_pending_count > 100
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "HITL 대기 {{ $value }}건 - 검토자 배정 필요"

      # Vision MV 갱신 실패
      - alert: MVRefreshSlow
        expr: vision_mv_refresh_duration_seconds > 300
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "MV 갱신 {{ $value }}초 소요 - 쿼리 최적화 필요"
```

### 4.2 알림 대응 플레이북

| 알림 | 심각도 | 즉시 조치 | 근본 원인 조사 |
|------|--------|----------|---------------|
| **ServiceDown** | Critical | Pod 재시작 (`kubectl rollout restart`) | 로그 확인, OOM 여부, 디스크 풀 |
| **CriticalErrorRate** | Critical | 이전 버전 롤백 (`kubectl rollout undo`) | 최근 배포 diff, DB 마이그레이션 오류 |
| **HighLatency** | Warning | 동시 요청 수 확인, HPA 스케일 트리거 | 느린 쿼리 EXPLAIN, 커넥션 풀 포화 |
| **LLMHighLatency** | Warning | Fallback 모델 전환 | OpenAI 상태 페이지 확인, Rate Limit |
| **DBPoolExhaustion** | Warning | `DB_MAX_OVERFLOW` 임시 증가 | 느린 트랜잭션 식별, 누수 커넥션 |
| **RedisHighMemory** | Warning | MAXLEN 축소, 캐시 TTL 감소 | 메모리 프로파일링 (`redis-cli memory doctor`) |
| **OutboxBacklog** | Warning | Sync Worker 인스턴스 추가 | Worker 에러 로그, Redis 연결 확인 |
| **LLMErrorRate** | Warning | Fallback 모델 자동 전환 | API 키 유효성, Rate Limit 상태 |
| **TokenBudgetHigh** | Warning | 비필수 LLM 호출 일시 중단 | 토큰 소비 분석 (모델/목적별) |
| **CircuitBreakerOpen** | Warning | 타겟 서비스 상태 확인, 최근 배포 리뷰 | 타겟 서비스 과부하 또는 다운 |
| **DLQBacklog** | Warning | Admin API로 DLQ 메시지 확인, 실패 패턴 분석 | 지속적 다운스트림 장애 |

### 4.3 알림 라우팅

```yaml
# alertmanager/alertmanager.yml

route:
  receiver: 'default'
  group_by: ['alertname', 'job']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'critical-channel'
      repeat_interval: 30m
    - match:
        severity: warning
      receiver: 'warning-channel'
      repeat_interval: 4h

receivers:
  - name: 'critical-channel'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_CRITICAL}'
        channel: '#axiom-critical'
        title: '🚨 {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    # + PagerDuty 또는 전화 호출

  - name: 'warning-channel'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_WARNING}'
        channel: '#axiom-alerts'
        title: '⚠️ {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

  - name: 'default'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_DEFAULT}'
        channel: '#axiom-monitoring'
```

---

## 5. Grafana 대시보드 설계

### 5.1 대시보드 구성

```
┌─ Axiom Grafana Dashboards ───────────────────────────────────────┐
│                                                                    │
│  Dashboard 1: Overview (전체 현황)                                │
│  ├── 5개 서비스 가용성 게이지 (초록/노랑/빨강)                    │
│  ├── 전체 요청량 그래프 (req/s)                                   │
│  ├── 전체 에러율 그래프 (%)                                       │
│  ├── Redis/PostgreSQL/Neo4j 상태                                  │
│  └── 활성 알림 목록                                               │
│                                                                    │
│  Dashboard 2: API Performance (서비스별)                          │
│  ├── p50/p95/p99 지연 히트맵 (서비스 × 시간)                      │
│  ├── 엔드포인트별 요청 분포                                       │
│  ├── HTTP 상태 코드 분포                                          │
│  └── 슬로우 쿼리 TOP 10                                          │
│                                                                    │
│  Dashboard 3: LLM Operations                                     │
│  ├── 모델별 호출 수/지연/에러율                                   │
│  ├── 토큰 사용량 (일별, 서비스별)                                 │
│  ├── LLM 비용 추이 (일별)                                        │
│  ├── Fallback 발생 횟수                                           │
│  └── 토큰 예산 소진율                                             │
│                                                                    │
│  Dashboard 4: Data Infrastructure                                 │
│  ├── PostgreSQL: 커넥션 풀, 쿼리 시간, 디스크 사용량              │
│  ├── Redis: 메모리 사용, 명령 수, Stream 길이                     │
│  ├── Neo4j: 쿼리 시간, 커넥션 풀, 인덱스 히트율                  │
│  └── Event Outbox: 적체량, 발행 속도, 실패율                     │
│                                                                    │
│  Dashboard 5: Workers & Events                                    │
│  ├── Worker별 처리량/지연/에러율                                  │
│  ├── Consumer Group 상태 (pending, lag)                            │
│  ├── Watch CEP 알림 발생/발송 현황                                │
│  └── Synapse 추출 파이프라인 현황                                 │
│                                                                    │
│  Dashboard 6: Canvas Frontend                                     │
│  ├── Web Vitals (LCP, FID, CLS) 추이                              │
│  ├── JS 에러율 (Sentry)                                           │
│  ├── API 호출 실패율 (프론트엔드 관점)                             │
│  └── 번들 크기 추이 (CI 빌드별)                                   │
│                                                                    │
│  Dashboard 7: Resilience (복원력)                                  │
│  ├── Circuit Breaker 상태 (서비스별 게이지)                       │
│  ├── Circuit Breaker Trip 이력 (시계열)                           │
│  ├── DLQ Depth (스트림별)                                        │
│  ├── Fallback 발생 횟수 (서비스별)                               │
│  └── Retry 성공/실패율                                           │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 5.2 핵심 대시보드 패널 상세

#### Overview 대시보드 핵심 패널

```
┌──────────────────────────────────────────────────────────────────┐
│ SERVICE HEALTH          │ ERROR BUDGET REMAINING (월간)           │
│                         │                                        │
│ Core    [████████] 99.98%  │ Core    [██████████████░] 92%         │
│ Oracle  [████████] 99.72%  │ Oracle  [████████████░░░] 81%         │
│ Vision  [████████] 99.91%  │ Vision  [█████████████░░] 89%         │
│ Synapse [███████░] 99.41%  │ Synapse [███████████░░░░] 73%         │
│ Weaver  [████████] 99.85%  │ Weaver  [██████████████░] 95%         │
│                         │                                        │
├─────────────────────────┼────────────────────────────────────────┤
│ REQUESTS/SEC (5분)      │ P95 LATENCY (5분)                      │
│                         │                                        │
│ Core    ████ 45 req/s   │ Core    ██░ 320ms                      │
│ Oracle  ██░ 12 req/s    │ Oracle  ████████░ 4.2s  (LLM 포함)    │
│ Vision  █░ 8 req/s      │ Vision  ███░ 1.1s                      │
│ Synapse ░ 2 req/s       │ Synapse ████████████░ 45s  (추출)      │
│ Weaver  ░ 3 req/s       │ Weaver  █████░ 2.8s                    │
│                         │                                        │
├─────────────────────────┴────────────────────────────────────────┤
│ ACTIVE ALERTS                                                     │
│                                                                   │
│ 🔴 [Critical] ServiceDown: synapse-worker-2       10분 전        │
│ 🟡 [Warning]  HighLatency: oracle p95=12s         25분 전        │
│ 🔵 [Info]     LowCacheHitRate: oracle 28%         1시간 전       │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## 6. 분산 추적 (Distributed Tracing)

### 6.1 OpenTelemetry 통합 전략

```
┌─ 추적 흐름 ──────────────────────────────────────────────────────┐
│                                                                    │
│  Canvas (Browser)                                                  │
│    │ trace_id: abc123                                              │
│    │ X-Request-ID: abc123                                          │
│    ▼                                                               │
│  Core API                                                          │
│    │ span: core.api.create_document                                │
│    ├── span: core.db.insert                                        │
│    ├── span: core.event_outbox.publish                             │
│    │   └── [async] sync_worker → Redis Streams                     │
│    └── span: core.llm.generate (문서 AI 생성)                     │
│         │ attributes: {model: gpt-4o, tokens: 1200}               │
│         ▼                                                          │
│       OpenAI API                                                   │
│         span: openai.chat.completions                              │
│                                                                    │
│  Oracle API (별도 요청)                                           │
│    │ span: oracle.api.text2sql                                     │
│    ├── span: oracle.neo4j.schema_search (벡터 검색)               │
│    ├── span: oracle.llm.sql_generation                             │
│    ├── span: oracle.sql_guard.validate                             │
│    ├── span: oracle.db.execute_sql                                 │
│    └── span: oracle.cache.postprocess [async]                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 6.2 OpenTelemetry 구현

```python
# 각 서비스: app/core/tracing.py

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

def setup_tracing(app, service_name: str):
    """OpenTelemetry 추적 초기화"""
    provider = TracerProvider(
        resource=Resource.create({
            "service.name": service_name,
            "service.version": settings.APP_VERSION,
            "deployment.environment": settings.APP_ENV,
        })
    )

    # OTLP → Jaeger/Tempo로 전송
    exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_ENDPOINT or "http://tempo:4317"
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # 자동 계측
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
    RedisInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()  # LLM API 호출 추적
```

### 6.3 LLM 호출 커스텀 Span

```python
# LLM 호출 시 추가 속성 기록

tracer = trace.get_tracer("axiom.llm")

async def call_llm_with_tracing(prompt: str, model: str, **kwargs):
    with tracer.start_as_current_span("llm.generate") as span:
        span.set_attribute("llm.model", model)
        span.set_attribute("llm.provider", provider)
        span.set_attribute("llm.prompt_tokens", count_tokens(prompt))
        span.set_attribute("llm.temperature", kwargs.get("temperature", 0))

        try:
            response = await llm_client.generate(prompt, **kwargs)
            span.set_attribute("llm.completion_tokens", response.usage.completion_tokens)
            span.set_attribute("llm.total_tokens", response.usage.total_tokens)
            span.set_status(StatusCode.OK)
            return response
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise
```

### 6.4 LangSmith + OpenTelemetry 공존

```
[결정] LangSmith과 OpenTelemetry를 병행 사용한다.
[근거]
  - LangSmith: LLM 프롬프트/응답 상세 추적 (프롬프트 디버깅, 품질 평가)
  - OpenTelemetry: 전체 요청 흐름 추적 (서비스 간 호출, DB, Redis)
  - 두 시스템은 역할이 다르므로 상호 보완적

프로젝트 매핑:
  LangSmith          OpenTelemetry
  axiom-core    →    service.name=axiom-core
  axiom-oracle  →    service.name=axiom-oracle
  axiom-vision  →    service.name=axiom-vision
  axiom-synapse →    service.name=axiom-synapse
```

---

## 7. 로그 집중화

### 7.1 구조화 로깅 표준

```python
# 모든 서비스 공통: structlog 설정

import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,  # ContextVar 자동 포함
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
)

# 로그 출력 예시
{
    "timestamp": "2026-02-20T10:30:00.000Z",
    "level": "info",
    "event": "api_request_completed",
    "service": "oracle",
    "tenant_id": "uuid",
    "request_id": "uuid",
    "method": "POST",
    "path": "/api/v1/text2sql",
    "status": 200,
    "duration_ms": 3500,
    "llm_model": "gpt-4o",
    "llm_tokens": 1200,
    "cache_hit": false
}
```

### 7.2 로그 수집 파이프라인

```
┌─ 로그 수집 아키텍처 ─────────────────────────────────────────────┐
│                                                                    │
│  서비스 Pod (stdout JSON)                                         │
│       │                                                            │
│       ▼                                                            │
│  ┌─────────────────┐                                              │
│  │ Fluent Bit       │  (DaemonSet, 각 노드에서 수집)              │
│  │ (로그 수집기)    │                                              │
│  └────────┬────────┘                                              │
│           │                                                        │
│     ┌─────┴─────┐                                                  │
│     ▼           ▼                                                  │
│  ┌──────┐  ┌──────────┐                                           │
│  │ Loki  │  │ CloudWatch│  (환경별 선택)                           │
│  │(개발) │  │ (프로덕션)│                                          │
│  └──┬───┘  └────┬─────┘                                           │
│     │           │                                                  │
│     └─────┬─────┘                                                  │
│           ▼                                                        │
│     ┌──────────┐                                                   │
│     │ Grafana   │  (로그 탐색, 대시보드)                           │
│     │ (Explore) │                                                  │
│     └──────────┘                                                   │
│                                                                    │
│  환경별:                                                          │
│    개발   → stdout + Loki                                         │
│    스테이징 → CloudWatch Logs                                      │
│    프로덕션 → CloudWatch Logs + DataDog (APM 통합)                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 7.3 필수 로그 필드

| 필드 | 필수 | 설명 |
|------|:----:|------|
| `timestamp` | Y | ISO 8601 형식 |
| `level` | Y | debug, info, warning, error, critical |
| `event` | Y | 이벤트명 (snake_case) |
| `service` | Y | 서비스명 (core, oracle, vision, synapse, weaver) |
| `tenant_id` | Y | 테넌트 ID (멀티테넌트 격리 추적) |
| `request_id` | Y | 요청 ID (분산 추적 연결) |
| `trace_id` | 조건 | OpenTelemetry trace ID (추적 활성 시) |
| `duration_ms` | 조건 | 처리 시간 (요청/작업 완료 시) |
| `error` | 조건 | 에러 메시지 (에러 발생 시) |
| `stack_trace` | 조건 | 스택 트레이스 (에러 + DEBUG 레벨) |

---

## 8. 에러 추적 (Sentry)

### 8.1 Sentry 프로젝트 구성

| Sentry 프로젝트 | 서비스 | 환경 |
|----------------|--------|------|
| `axiom-core` | Core API + Workers | staging, production |
| `axiom-oracle` | Oracle API | staging, production |
| `axiom-vision` | Vision API | staging, production |
| `axiom-synapse` | Synapse API | staging, production |
| `axiom-weaver` | Weaver API | staging, production |
| `axiom-canvas` | Canvas (Browser) | staging, production |

### 8.2 Sentry 초기화 (백엔드)

```python
# 각 서비스: app/core/sentry.py

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

def setup_sentry(service_name: str):
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.APP_ENV,
        release=f"{service_name}@{settings.APP_VERSION}",
        traces_sample_rate=0.1,  # 10% 트랜잭션 샘플링
        profiles_sample_rate=0.1,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        before_send=_filter_sensitive_data,
    )

def _filter_sensitive_data(event, hint):
    """민감 정보 필터링"""
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        for sensitive in ["Authorization", "Cookie", "X-API-Key"]:
            if sensitive in headers:
                headers[sensitive] = "[REDACTED]"
    return event
```

### 8.3 Sentry 초기화 (Canvas 프론트엔드)

```typescript
// src/lib/sentry.ts

import * as Sentry from '@sentry/react';

Sentry.init({
  dsn: import.meta.env.VITE_SENTRY_DSN,
  environment: import.meta.env.MODE,
  release: `axiom-canvas@${__APP_VERSION__}`,
  integrations: [
    Sentry.browserTracingIntegration(),
    Sentry.replayIntegration({ maskAllText: true }),
  ],
  tracesSampleRate: 0.1,
  replaysSessionSampleRate: 0.01,  // 1% 세션 녹화
  replaysOnErrorSampleRate: 0.1,   // 에러 시 10% 녹화
});
```

---

## 9. 성능 테스트

### 9.1 부하 테스트 도구 및 시나리오

```python
# tests/load/locustfile.py (Locust 부하 테스트)

from locust import HttpUser, task, between

class AxiomCoreUser(HttpUser):
    """Core API 부하 테스트"""
    wait_time = between(1, 3)
    host = "http://localhost:8000"

    def on_start(self):
        """인증 토큰 획득"""
        resp = self.client.post("/api/v1/auth/login", json={
            "email": "loadtest@axiom.kr",
            "password": "loadtest_password"
        })
        self.token = resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def list_cases(self):
        self.client.get("/api/v1/cases", headers=self.headers)

    @task(3)
    def get_case_detail(self):
        self.client.get("/api/v1/cases/sample-uuid", headers=self.headers)

    @task(1)
    def create_document(self):
        self.client.post("/api/v1/documents", headers=self.headers, json={
            "case_id": "sample-uuid",
            "title": "Load Test Document",
            "content": "..."
        })


class OracleUser(HttpUser):
    """Oracle NL2SQL 부하 테스트"""
    wait_time = between(5, 15)  # LLM 호출이므로 긴 간격
    host = "http://localhost:8002"

    @task
    def nl2sql_query(self):
        self.client.post("/api/v1/text2sql", json={
            "question": "지난 분기 매출 상위 5개 조직",
            "datasource_id": "sample-ds"
        })
```

### 9.2 부하 테스트 기준

| 시나리오 | 동시 사용자 | 목표 RPS | p95 지연 | 에러율 |
|---------|:----------:|:-------:|:-------:|:-----:|
| **일상** | 50 | 30 | < 1s (Core) | < 0.1% |
| **피크** | 200 | 100 | < 2s (Core) | < 0.5% |
| **스트레스** | 500 | 200 | < 5s (Core) | < 2% |
| **NL2SQL 집중** | 20 | 5 | < 10s (Oracle) | < 3% |
| **문서 추출** | 10 | 1 | < 60s (Synapse) | < 5% |

### 9.3 성능 회귀 테스트 (CI/CD)

```yaml
# .github/workflows/perf-test.yml (성능 회귀 검출)

name: Performance Regression Test
on:
  pull_request:
    branches: [main]

jobs:
  perf-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start services
        run: docker compose -f infra/docker/docker-compose.yml up -d

      - name: Run K6 baseline test
        run: |
          k6 run --out json=results.json tests/load/k6-baseline.js

      - name: Check regression
        run: |
          python tests/load/check_regression.py \
            --results results.json \
            --baseline tests/load/baseline.json \
            --threshold 20  # 20% 이상 악화 시 실패
```

---

## 10. 용량 계획

### 10.1 현재 리소스 사양

| 서비스 | 인스턴스 | CPU | 메모리 | 디스크 |
|--------|:-------:|:---:|:-----:|:-----:|
| Core API | 2 | 2 vCPU | 4GB | - |
| Core Workers (×4) | 4 | 1 vCPU | 2GB | - |
| Oracle | 2 | 2 vCPU | 2GB | - |
| Vision | 2 | 2 vCPU | 4GB | - |
| Synapse | 2 | 2 vCPU | 4GB | - |
| Weaver | 1 | 1 vCPU | 2GB | - |
| PostgreSQL (RDS) | 1 | 4 vCPU | 16GB | 100GB |
| Neo4j | 1 | 4 vCPU | 10GB | 50GB |
| Redis (ElastiCache) | 1 | 2 vCPU | 4GB | - |
| Canvas (Nginx) | 2 | 0.5 vCPU | 512MB | - |

### 10.2 스케일링 트리거

| 메트릭 | 임계값 | 스케일링 액션 |
|--------|--------|-------------|
| CPU 사용률 | > 70% (5분) | HPA: Pod 수 +1 (최대 8) |
| 메모리 사용률 | > 80% | HPA: Pod 수 +1 |
| DB 커넥션 풀 | > 80% | `DB_POOL_SIZE` 증가 또는 읽기 레플리카 |
| Redis 메모리 | > 80% | ElastiCache 노드 업그레이드 |
| Neo4j 쿼리 지연 | p95 > 500ms | Neo4j 메모리 증설 또는 읽기 레플리카 |
| Event Outbox 적체 | > 1,000건 | Sync Worker 인스턴스 추가 |
| NL2SQL 지연 | p95 > 15s | Oracle 인스턴스 추가 + LLM 캐시 확인 |

### 10.3 성장 시나리오별 용량 계획

| 규모 | 사용자 수 | 일일 요청 | 인프라 변경 |
|------|:--------:|:--------:|-----------|
| **현재** | ~50 | ~10K | 위 사양 그대로 |
| **6개월 후** | ~200 | ~50K | Core/Oracle 3 Pod, RDS r6g.xlarge |
| **1년 후** | ~500 | ~150K | Redis 클러스터, Neo4j 읽기 레플리카, RDS Multi-AZ |
| **2년 후** | ~2,000 | ~500K | Kafka 도입 검토 (Redis Streams 대체), Neo4j Enterprise |

---

## 11. 기존 문서 연결 맵

이 문서와 기존 서비스별 문서의 관계:

| 서비스 | 기존 문서 | 이 문서에서 통합하는 내용 |
|--------|----------|------------------------|
| Core | `08_operations/deployment.md` | 헬스체크 → SLO 연결 |
| Core | `08_operations/configuration.md` | 환경변수 → 성능 튜닝 근거 |
| Core | `01_architecture/event-driven.md` | Redis Streams → 이벤트 메트릭 |
| Core | `03_backend/concurrency-policy.md` | 커넥션 풀 → 리소스 모니터링 |
| Core | `03_backend/worker-system.md` | Worker → Worker 메트릭 |
| Core | `05_llm/llmops-model-portfolio.md` | LLM 모니터링 → LLM 대시보드 |
| Oracle | `08_operations/deployment.md` (6절) | 메트릭/알림 → 통합 알림 규칙 |
| Oracle | `03_backend/cache-system.md` | 캐시 히트율 → 비즈니스 메트릭 |
| Vision | `08_operations/deployment.md` (5절) | 메트릭 → 통합 Prometheus |
| Synapse | `08_operations/deployment.md` (7절) | 메트릭/로깅 → 통합 |
| Weaver | `08_operations/deployment.md` (5절) | 체크리스트 → 통합 모니터링 |
| Canvas | `08_operations/build-deploy.md` (5절) | Web Vitals → 프론트엔드 대시보드 |
| Canvas | `06_data/cache-strategy.md` | TanStack Query → 캐시 레이어 맵 |
| Core | `01_architecture/resilience-patterns.md` | Circuit Breaker, Fallback, DLQ, K8s Probe, Runbooks |

---

## 결정 사항 (Decisions)

- Prometheus + Grafana를 메트릭/대시보드 표준으로 사용
  - 근거: 오픈소스, EKS 통합 용이, 커뮤니티 지원

- OpenTelemetry를 분산 추적 표준으로 채택
  - 근거: 벤더 중립, LangSmith과 보완적 관계

- Sentry를 에러 추적 도구로 사용
  - 근거: 프론트엔드/백엔드 통합, Session Replay 기능

- LangSmith + OpenTelemetry 병행
  - 근거: LLM 전용 추적(프롬프트 디버깅) + 범용 분산 추적은 역할이 다름

- 로그는 JSON 구조화 로깅 (structlog) 필수
  - 근거: 검색/필터링 용이, Loki/CloudWatch 파싱 자동화

- 성능 테스트는 Locust(Python) + K6(CI 회귀) 병행
  - 근거: Locust는 시나리오 작성 용이, K6는 CI 통합 용이

---

## 관련 문서

- [08_operations/logging-system.md](./logging-system.md) (로깅 체계, 구조화 로깅 표준, 7일 보관 정책, AI 로그 분석 챗봇)
- [06_data/database-operations.md](../06_data/database-operations.md) (DB 백업/복구, 유지보수, 슬로우 쿼리, DR 전략, 관리자 대시보드 DB 모니터링)

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 (Cross-service 성능/모니터링 통합) |
