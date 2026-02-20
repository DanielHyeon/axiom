# Axiom MSA — 복원력 설계 (Resilience Patterns)

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **범위**: Cross-service (Core, Oracle, Vision, Synapse, Weaver, Canvas)

<!-- affects: api, backend, operations, frontend -->
<!-- requires-update: 08_operations/deployment.md, 08_operations/performance-monitoring.md -->

---

## 이 문서가 답하는 질문

- 서비스 간 의존 관계는 어떤 형태이며, 각 의존의 중요도는?
- Circuit Breaker는 어떻게 동작하며, 서비스 쌍별 설정은?
- 특정 서비스 장애 시 Fallback 전략은 무엇인가?
- DLQ(Dead Letter Queue)는 어떻게 설계하는가?
- K8s Probe(liveness/readiness/startup)는 어떻게 분리하는가?
- Graceful Degradation 단계는 어떻게 정의되는가?
- 장애 대응 Runbook은 어떤 시나리오를 다루는가?

---

## 1. 서비스 의존성 맵

### 1.1 동기 호출 그래프

```
┌─ 동기 의존성 (HTTP/httpx) ──────────────────────────────────────────┐
│                                                                       │
│                      ┌──────────┐                                     │
│                      │  Canvas  │                                     │
│                      │ (React)  │                                     │
│                      └─────┬────┘                                     │
│                            │ HTTP/WebSocket/SSE                       │
│                            ▼                                          │
│                      ┌──────────┐                                     │
│              ┌───────│   Core   │───────┐                             │
│              │       │ (FastAPI)│       │                              │
│              │       └──┬───┬──┘       │                              │
│              │          │   │          │                               │
│         ┌────▼────┐ ┌──▼───▼──┐ ┌────▼────┐                         │
│         │ Oracle  │ │ Synapse │ │  Weaver │                          │
│         │ (NL2SQL)│ │(Ontology│ │ (Data   │                          │
│         │         │ │+Mining) │ │ Fabric) │                          │
│         └────┬────┘ └────┬────┘ └────┬────┘                         │
│              │           │           │                                │
│              │      ┌────▼────┐      │                               │
│              │      │ Vision  │      │                                │
│              │      │ (OLAP)  │      │                                │
│              │      └─────────┘      │                                │
│              │                       │                                │
│         ┌────▼────┐            ┌────▼────┐                           │
│         │  Neo4j  │            │ MindsDB │                           │
│         └─────────┘            └─────────┘                           │
│                                                                       │
│  [참고] Vision은 Core를 통하지 않고 직접 PostgreSQL에 접근한다.      │
│  [참고] Oracle/Synapse는 Neo4j에 직접 접근한다.                      │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

**호출 관계 상세:**

| Caller | Callee | Protocol | Timeout | Criticality | 비고 |
|--------|--------|----------|:-------:|:-----------:|------|
| Core | Oracle | HTTP (httpx) | 60s | High | NL2SQL 프록시 |
| Core | Vision | HTTP (httpx) | 180s | Medium | OLAP/What-if 프록시 |
| Core | Synapse | HTTP (httpx) | 60s/180s/300s | Medium | 온톨로지 60s, 마이닝 180s, 이벤트로그 300s |
| Core | Weaver | HTTP (httpx) | 60s | Low | 데이터 패브릭 프록시 |
| EventLog Worker | Synapse | HTTP (httpx) | 60s/chunk | Medium | 이벤트 로그 청크 스트리밍 |
| Oracle | Neo4j | Bolt | 30s | Critical | 스키마 그래프/벡터 검색 |
| Oracle | OpenAI | HTTPS | 30s | High | SQL 생성, HyDE, 시각화 |
| Vision | PostgreSQL | asyncpg | 30s | Critical | OLAP 쿼리, MV |
| Synapse | Neo4j | Bolt | 30s | Critical | 온톨로지 CRUD, 그래프 검색 |
| Weaver | MindsDB | HTTP | 120s | High | Cross-DB 쿼리 |

### 1.2 비동기 이벤트 흐름

```
┌─ 비동기 의존성 (Redis Streams) ─────────────────────────────────────┐
│                                                                       │
│  Core (sync_worker)                                                   │
│    │ Event Outbox → Redis Streams 발행                                │
│    │                                                                  │
│    ├── axiom:events ─────┬── vision_group (Vision)                   │
│    │                     └── synapse_group (Synapse)                  │
│    │                                                                  │
│    ├── axiom:watches ──── watch_cep_group (Watch CEP Worker)         │
│    │                                                                  │
│    ├── axiom:workers ──── worker_group (OCR/Extract/Generate/EventLog)│
│    │                                                                  │
│    └── axiom:process_mining ─┬── synapse_mining_group (Synapse)      │
│                              └── canvas_mining_group (Canvas SSE)     │
│                                                                       │
│  axiom:notifications:{tenant_id} → Canvas SSE/WebSocket (실시간 알림)│
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

> 상세: [event-driven.md](./event-driven.md) §5, [event-outbox.md](../06_data/event-outbox.md) §2

### 1.3 실시간 채널

| 채널 | 프로토콜 | 용도 | 연결 범위 |
|------|---------|------|----------|
| `/agents/ws` | WebSocket | AI 에이전트 스트리밍 | 에이전트 채팅 페이지 |
| `/api/v1/watches/stream` | SSE | Watch 대시보드 전용 알림 | Watch 페이지 |
| `/api/v1/events/stream` | SSE | 범용 이벤트 스트림 | DashboardLayout |
| `/api/v1/workers/progress` | SSE | Worker 진행 상황 | 문서 처리 페이지 |
| Redis `axiom:notifications:{tenant_id}` | WebSocket relay | 전역 실시간 알림 | 전체 앱 |

### 1.4 인프라 의존성

| 인프라 | 의존 서비스 | 장애 시 영향 |
|--------|-----------|------------|
| **PostgreSQL** (Primary) | Core, Vision | 전체 쓰기 불가 (최대 위험) |
| **PostgreSQL** (Read Replica) | Core, Vision | 읽기 전용 Fallback |
| **Redis** | Core, Oracle, Synapse, Weaver | 이벤트 지연, 캐시 미스, Rate Limit 불가 |
| **Neo4j** | Oracle, Synapse | NL2SQL + 온톨로지 불가 |
| **MinIO/S3** | Core (Workers) | 문서 업로드/다운로드 불가 |
| **OpenAI API** | Oracle, Vision, Synapse | LLM 기능 불가 |

---

## 2. Circuit Breaker 설계

### 2.1 상태 전이

```
         failure_count >= threshold
CLOSED ──────────────────────────────> OPEN
  ▲                                     │
  │ probe 성공                          │ open_duration 경과
  │                                     ▼
  └─────────── HALF_OPEN <─────────────┘
                │
                │ probe 실패
                └──────────────> OPEN
```

| 상태 | 설명 | 동작 |
|------|------|------|
| **CLOSED** | 정상 | 모든 요청을 통과시키고, 실패를 카운트한다 |
| **OPEN** | 차단 | 즉시 CircuitOpenError를 반환한다 (Fallback 실행) |
| **HALF_OPEN** | 탐침 | 1개 요청만 허용. 성공 → CLOSED, 실패 → OPEN |

### 2.2 서비스 쌍별 설정

| Caller → Callee | Failure Threshold | Window | Open Duration | Half-Open Probes | Fallback |
|-----------------|:-:|:-:|:-:|:-:|----------|
| Core → Oracle | 5회 / 60s | 60s | 30s | 1 | `ORACLE_UNAVAILABLE` + 캐시된 NL2SQL 결과 |
| Core → Vision | 5회 / 60s | 60s | 30s | 1 | `VISION_UNAVAILABLE`, Core CRUD 정상 |
| Core → Synapse | 5회 / 60s | 60s | 30s | 1 | `SYNAPSE_UNAVAILABLE`, Core CRUD 정상 |
| Core → Weaver | 3회 / 60s | 60s | 60s | 1 | `WEAVER_UNAVAILABLE` |
| Oracle → OpenAI | 5회 / 60s | 60s | 30s | 1 | Query Node 캐시 → error |
| Oracle → Neo4j | 3회 / 30s | 30s | 15s | 1 | 503 (서비스 불가, readiness fail) |
| EventLog Worker → Synapse | 3회 / 60s | 60s | 60s | 1 | Retry later → DLQ |
| Vision → OpenAI | 5회 / 60s | 60s | 30s | 1 | NL-to-Pivot 불가, 수동 피벗은 정상 |

```
[결정] Core → 외부 모듈 호출의 Circuit Breaker는 Core 측에서 관리한다.
[결정] 모듈 내부 의존성(Oracle→Neo4j 등)은 해당 모듈에서 관리한다.
[결정] Circuit Breaker 상태 변경 시 구조화 로그를 기록한다 (circuit_breaker_opened 등).
```

### 2.3 구현 패턴

```python
# app/core/circuit_breaker.py
# 전 서비스 공통 모듈

from enum import Enum
from dataclasses import dataclass, field
import time
import asyncio

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5       # window 내 허용 실패 수
    window_seconds: int = 60         # 실패 카운트 윈도우
    open_duration_seconds: int = 30  # OPEN 유지 시간
    half_open_max_probes: int = 1    # HALF_OPEN 시 허용 요청 수

class CircuitBreaker:
    """서비스 간 호출에 적용하는 Circuit Breaker"""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failures: list[float] = []
        self.last_opened_at: float = 0

    async def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_opened_at > self.config.open_duration_seconds:
                self.state = CircuitState.HALF_OPEN
                logger.info("circuit_breaker_half_open", target=self.name)
            else:
                CIRCUIT_BREAKER_STATE.labels(target_service=self.name).set(1)
                raise CircuitOpenError(self.name)

        try:
            result = await func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failures.clear()
                logger.info("circuit_breaker_closed", target=self.name)
                CIRCUIT_BREAKER_STATE.labels(target_service=self.name).set(0)
            return result
        except Exception as e:
            self._record_failure()
            raise

    def _record_failure(self):
        now = time.time()
        self.failures = [
            t for t in self.failures
            if now - t < self.config.window_seconds
        ]
        self.failures.append(now)
        if len(self.failures) >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            self.last_opened_at = now
            logger.warning("circuit_breaker_opened", target=self.name)
            CIRCUIT_BREAKER_STATE.labels(target_service=self.name).set(1)
            CIRCUIT_BREAKER_TRIPS.labels(target_service=self.name).inc()

class CircuitOpenError(Exception):
    """Circuit Breaker가 OPEN 상태일 때 발생"""
    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(f"Circuit breaker is OPEN for {service_name}")
```

**Core의 프록시 라우터 적용 예:**

```python
# app/api/proxy.py (개념)

oracle_cb = CircuitBreaker("oracle", CircuitBreakerConfig(
    failure_threshold=5, window_seconds=60, open_duration_seconds=30
))

async def proxy_to_oracle(path: str, **kwargs):
    try:
        return await oracle_cb.call(httpx_client.get, f"{ORACLE_URL}{path}", **kwargs)
    except CircuitOpenError:
        raise HTTPException(
            status_code=503,
            detail={"code": "SERVICE_CIRCUIT_OPEN", "message": "Oracle 서비스가 일시적으로 사용 불가능합니다"}
        )
```

### 2.4 Prometheus 메트릭

| 메트릭 | 유형 | 라벨 | 설명 |
|--------|------|------|------|
| `core_circuit_breaker_state` | Gauge | target_service | 0=closed, 1=open, 2=half_open |
| `core_circuit_breaker_trips_total` | Counter | target_service | CB가 OPEN으로 전환된 횟수 |
| `core_circuit_breaker_fallback_total` | Counter | target_service | Fallback 실행 횟수 |

> 알림 규칙은 [performance-monitoring.md](../08_operations/performance-monitoring.md) §4.1을 참조한다.

---

## 3. Fallback Matrix

### 3.1 동기 호출 Fallback

| Caller | Callee | Failure Mode | Fallback 동작 | 사용자 영향 |
|--------|--------|-------------|--------------|------------|
| Core | Oracle | Timeout / 5xx / CB Open | error `ORACLE_UNAVAILABLE`, message "자연어 쿼리를 일시적으로 사용할 수 없습니다" | NL2SQL 불가, Cases/Docs/Watch 정상 |
| Core | Vision | Timeout / 5xx / CB Open | error `VISION_UNAVAILABLE`, message "분석 기능을 일시적으로 사용할 수 없습니다" | What-if/OLAP 불가, Cases/Docs 정상 |
| Core | Synapse | Timeout / 5xx / CB Open | error `SYNAPSE_UNAVAILABLE`, message "온톨로지 기능을 일시적으로 사용할 수 없습니다" | 온톨로지/마이닝 불가, CRUD 정상 |
| Core | Weaver | Timeout / 5xx / CB Open | error `WEAVER_UNAVAILABLE`, message "데이터 패브릭을 일시적으로 사용할 수 없습니다" | 데이터 패브릭 불가 |
| Oracle | OpenAI | RateLimit / Timeout | (1) gpt-4o-mini 전환 → (2) Query Node 캐시 → (3) error | 점진적 품질 저하 |
| Oracle | Neo4j | ConnectionError | 503, readiness probe 실패 → Pod 제거 | Oracle 전체 불가 |
| Vision | PostgreSQL | ConnectionError | readiness probe 실패 → Pod 제거 | Vision 전체 불가 |
| Synapse | Neo4j | ConnectionError | readiness probe 실패 → Pod 제거 | Synapse 전체 불가 |
| Weaver | MindsDB | Timeout / ConnectionError | error, schema introspection은 어댑터 직접 접근으로 정상 | Cross-DB 쿼리 불가 |
| EventLog Worker | Synapse | 5xx | 3회 재시도 → DLQ | 이벤트 로그 수집 지연 |

### 3.2 비동기 이벤트 처리 Fallback

| 이벤트 흐름 | Failure Mode | Fallback | 영향 |
|------------|-------------|----------|------|
| Event Outbox → Redis | Redis 연결 실패 | Outbox 테이블에 계속 축적 (status=PENDING), Redis 복구 후 재발행 | 이벤트 전달 지연, 유실 없음 |
| Redis → Consumer | Consumer 장애 | Pending 메시지 5분 후 XCLAIM으로 다른 Consumer에 재할당 | 처리 지연 (최대 5분) |
| Consumer 처리 실패 | 3회 재시도 실패 | DLQ로 이동 (§5 참조) | 영구 실패 메시지 격리 |

### 3.3 인프라 Fallback

| 인프라 | Failure Mode | Fallback | 영향 |
|--------|-------------|----------|------|
| PostgreSQL (Primary) | Connection 실패 | Connection Pool pool_pre_ping + 자동 재연결. 지속 실패 시 Read Replica Fallback (읽기만) | 쓰기 불가 = §7 Level 3 Emergency |
| Redis | Connection 실패 | Rate Limiting → 인메모리 카운터 (정밀도 저하). Event Outbox → DB에 계속 축적. 캐시 → DB 직접 조회 | 성능 저하, 이벤트 지연 |
| Neo4j | Connection 실패 | Oracle/Synapse 503, readiness fail | NL2SQL + 온톨로지 불가 |
| MinIO/S3 | Connection 실패 | OCR/Generate Workers pause, 문서 업로드/다운로드 실패 | 문서 관리 불가 |

### 3.4 LLM Provider Fallback Chain

```
┌─ LLM Fallback Chain ────────────────────────────────────────────────┐
│                                                                       │
│  Primary:    OpenAI gpt-4o                                           │
│     │ (타임아웃 30s, rate limit, 5xx)                                │
│     ▼                                                                 │
│  Fallback 1: OpenAI gpt-4o-mini       (cheaper, faster, lower quality)│
│     │ (동일 조건)                                                     │
│     ▼                                                                 │
│  Fallback 2: Anthropic Claude          (ANTHROPIC_API_KEY 설정 시)   │
│     │ (동일 조건)                                                     │
│     ▼                                                                 │
│  Fallback 3: Ollama local              (개발 환경 전용)              │
│     │ (동일 조건)                                                     │
│     ▼                                                                 │
│  Final:      HTTP 502 EXTERNAL_SERVICE_ERROR                         │
│              "AI 서비스가 일시적으로 사용 불가능합니다"               │
│                                                                       │
│  로그: llm_call_fallback (provider, from_model, to_model, reason)    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

> LLM 모델 포트폴리오 및 비용 상세는 [llmops-model-portfolio.md](../05_llm/llmops-model-portfolio.md)를 참조한다.

---

## 4. Retry & Timeout 통합 정리

### 4.1 동기 호출 타임아웃

> 원천: [gateway-api.md](../02_api/gateway-api.md) §2.1

| 엔드포인트 패턴 | Timeout | 근거 |
|----------------|:-------:|------|
| `/api/v1/cases/**` | 30s | Simple CRUD |
| `/api/v1/process/**` | 60s | BPM 실행 |
| `/api/v1/agents/**` | 120s | LLM 에이전트 |
| `/api/v1/documents/**` | 60s | 문서 CRUD |
| `/api/v1/watches/**` | 30s | 알림 관리 |
| `/api/v1/completion/**` | 120s | LLM Completion |
| `/api/v1/vision/**` | 180s | What-if 솔버 등 |
| `/api/v1/oracle/**` | 60s | NL2SQL |
| `/api/v1/synapse/**` | 60s | 온톨로지 |
| `/api/v1/event-logs/**` | 300s | 대용량 업로드 |
| `/api/v1/process-mining/**` | 180s | 마이닝 알고리즘 |
| `/api/v1/weaver/**` | 60s | 데이터 패브릭 |

### 4.2 Worker 재시도 정책

> 원천: [worker-system.md](../03_backend/worker-system.md) §2

| Worker | Max Retries | Backoff | 재시도 조건 | 비재시도 (→ DLQ) |
|--------|:-:|---------|-----------|----------------|
| sync_worker | 3 | Linear (retry_count in outbox) | Redis 연결, 타임아웃 | N/A (outbox status=FAILED) |
| watch_cep | 3 | Exponential 2s/4s/8s | Redis 에러, 알림 발송 실패 | CEP 룰 평가 에러 |
| ocr | 3 | Exponential 2s/4s/8s | 외부 서비스 타임아웃 | 잘못된 파일 형식 |
| extract | 3 | Exponential 2s/4s/8s | LLM 타임아웃/rate limit | 잘못된 문서 |
| generate | 3 | Exponential 2s/4s/8s | LLM 타임아웃, MinIO 에러 | 템플릿 에러 |
| event_log | 3 | Exponential 2s/4s/8s | 네트워크 에러, Synapse 503 | 포맷 에러, 컬럼 누락 |

### 4.3 Exponential Backoff with Jitter

```python
import random

def compute_backoff(attempt: int, base: float = 2.0, max_wait: float = 60.0) -> float:
    """Exponential Backoff + Full Jitter"""
    exponential = base * (2 ** attempt)
    jitter = random.uniform(0, base)
    return min(exponential + jitter, max_wait)

# 예: attempt 0 → ~2-4s, attempt 1 → ~4-6s, attempt 2 → ~8-10s
```

```
[결정] 모든 재시도에 Full Jitter를 적용한다.
[근거] Thundering herd 방지. 동시 재시도 시 부하 분산.
```

---

## 5. Dead Letter Queue (DLQ) 설계

### 5.1 DLQ 아키텍처

```
Normal Flow:
  event_outbox (PENDING)
    → sync_worker → Redis Streams → Consumer Workers
    → 처리 성공 → XACK

DLQ Flow (Worker 재시도 실패):
  Consumer Worker: 3회 재시도 실패
    → XACK (원본 메시지 확인 처리)
    → XADD axiom:dlq:{stream_name} (실패 메시지 복사)
    → 로그: dlq_message_added

DLQ Flow (Event Outbox 실패):
  event_outbox: retry_count >= max_retries
    → status = FAILED (기존 로직 유지)
    → Admin API로 조회/재처리

재처리 Flow:
  Admin: POST /admin/dlq/streams/{stream}/{id}/retry
    → DLQ에서 메시지 읽기
    → 원본 Stream에 XADD (재발행)
    → DLQ에서 XDEL
    → 로그: dlq_message_reprocessed
```

### 5.2 DLQ Redis Streams

```python
# DLQ 스트림 설정 (event-outbox.md의 STREAMS와 1:1 매핑)

DLQ_STREAMS = {
    "axiom:dlq:events":         "axiom:events 실패 이벤트",
    "axiom:dlq:watches":        "axiom:watches 실패 Watch 이벤트",
    "axiom:dlq:workers":        "axiom:workers 실패 Worker 태스크",
    "axiom:dlq:process_mining": "axiom:process_mining 실패 마이닝 이벤트",
}

DLQ_CONFIG = {
    "maxlen": 5000,            # DLQ 스트림 최대 길이
    "retention_days": 30,       # 30일 후 자동 정리 (pg_cron)
}
```

### 5.3 DLQ 관리 API

| Method | Path | 설명 | 권한 |
|--------|------|------|------|
| GET | `/admin/dlq/outbox` | Event Outbox 실패 목록 (status=FAILED) | admin |
| POST | `/admin/dlq/outbox/{id}/retry` | Outbox 메시지 재처리 (status=PENDING으로 복원) | admin |
| GET | `/admin/dlq/streams` | 모든 DLQ 스트림의 메시지 수 + 최근 메시지 | admin |
| GET | `/admin/dlq/streams/{stream}` | 특정 DLQ 스트림 메시지 목록 | admin |
| POST | `/admin/dlq/streams/{stream}/{id}/retry` | DLQ 메시지를 원본 스트림으로 재발행 | admin |

### 5.4 DLQ Prometheus 메트릭 및 알림

| 메트릭 | 유형 | 라벨 | 설명 |
|--------|------|------|------|
| `core_dlq_depth` | Gauge | stream | 현재 DLQ 대기 메시지 수 |
| `core_dlq_messages_total` | Counter | stream | DLQ로 이동한 총 메시지 수 |
| `core_dlq_reprocessed_total` | Counter | stream | DLQ에서 재처리된 총 메시지 수 |

```yaml
# 알림 규칙 (performance-monitoring.md §4.1에 추가)
- alert: DLQBacklog
  expr: core_dlq_depth > 100
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "DLQ {{ $labels.stream }}에 {{ $value }}건 적체"
    runbook: "§8.8 DLQ 메시지 누적 Runbook 참조"
```

---

## 6. Kubernetes Probe 설계

### 6.1 Probe 유형 구분

| Probe | 목적 | 실패 시 동작 | 검사 범위 |
|-------|------|------------|----------|
| **Startup** | 서비스 초기화 (DB 마이그레이션, 부트스트랩) | 대기, 초과 시 컨테이너 재시작 | 프로세스 기동, import 완료 |
| **Liveness** | 프로세스 교착 감지 | 컨테이너 재시작 | 이벤트 루프 응답 가능 |
| **Readiness** | 트래픽 수신 가능 여부 | Service 엔드포인트에서 제거 | DB, Redis, 의존 서비스 연결 |

```
[결정] 기존 단일 /health 엔드포인트를 3개로 분리한다.
[결정] Readiness에만 외부 의존성을 검사한다 (Liveness에 DB 체크 금지).
[근거] Liveness에 DB 체크를 넣으면 DB 일시 장애 시 모든 Pod가 재시작되어 cascade failure 발생.
[금지] Liveness probe에서 외부 시스템(DB, Redis, 외부 API)을 검사하지 않는다.
```

### 6.2 서비스별 Probe 설정

| 서비스 | Startup Probe | Liveness Probe | Readiness Probe |
|--------|--------------|----------------|-----------------|
| **Core API** | `GET /health/startup` initialDelay=10s, period=5s, failureThreshold=12 (max 60s) | `GET /health/live` period=10s, failureThreshold=3 | `GET /health/ready` (DB+Redis) period=10s, failureThreshold=3 |
| **Core Workers** | 동일 | `GET /health/live` period=15s, failureThreshold=3 | `GET /health/ready` (Redis) period=15s, failureThreshold=3 |
| **Oracle** | `GET /health/startup` initialDelay=15s, period=5s, failureThreshold=12 | `GET /health/live` period=10s, failureThreshold=3 | `GET /health/ready` (Neo4j+TargetDB) period=10s, failureThreshold=3 |
| **Vision** | `GET /health/startup` initialDelay=10s, period=5s, failureThreshold=12 | `GET /health/live` period=10s, failureThreshold=3 | `GET /health/ready` (PostgreSQL) period=10s, failureThreshold=3 |
| **Synapse** | `GET /health/startup` initialDelay=15s, period=5s, failureThreshold=18 (max 90s, Neo4j bootstrap) | `GET /health/live` period=10s, failureThreshold=3 | `GET /health/ready` (Neo4j+Redis) period=10s, failureThreshold=3 |
| **Weaver** | `GET /health/startup` initialDelay=10s, period=5s, failureThreshold=12 | `GET /health/live` period=10s, failureThreshold=3 | `GET /health/ready` (MindsDB) period=10s, failureThreshold=3 |

### 6.3 Probe 엔드포인트 구현

```python
# app/api/health.py (전 서비스 공통 패턴)

from fastapi import APIRouter
from starlette.responses import JSONResponse

router = APIRouter(tags=["health"])

@router.get("/health/startup")
async def startup():
    """Startup probe — 앱이 기동되었는지 확인"""
    return {"status": "started"}

@router.get("/health/live")
async def liveness():
    """Liveness probe — 이벤트 루프가 응답 가능한지 확인
    [금지] 여기서 DB, Redis 등 외부 시스템을 검사하지 않는다.
    """
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness():
    """Readiness probe — 트래픽을 받을 수 있는지 확인"""
    checks = {}

    # DB 연결 (Core, Vision)
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"

    # Redis 연결 (Core, Synapse)
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"

    # [서비스별 추가]
    # Oracle: Neo4j 연결, Target DB 연결
    # Synapse: Neo4j 연결
    # Weaver: MindsDB 연결

    all_healthy = all(v == "healthy" for v in checks.values())
    status_code = 200 if all_healthy else 503

    if not all_healthy:
        logger.warning("probe_readiness_failed", checks=checks)

    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if all_healthy else "not_ready", "checks": checks}
    )
```

### 6.4 PodDisruptionBudget (PDB)

| 서비스 | minAvailable | 근거 |
|--------|:------------:|------|
| Core API | 1 | API 가용성 필수 |
| Core sync_worker | 1 | Outbox 폴링 지속 필요 |
| Oracle | 1 | NL2SQL 가용성 |
| Vision | 1 | OLAP 가용성 |
| Synapse | 1 | 온톨로지 가용성 |
| Weaver | 0 | 낮은 우선순위, 일시 중단 허용 |

```yaml
# infra/k8s/core/pdb.yaml (예시)
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: core-api-pdb
  namespace: axiom
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: core-api
```

### 6.5 HPA (Horizontal Pod Autoscaler) 설정

| 서비스 | Min Replicas | Max Replicas | Scale Metric | Target | Scale-Down 지연 |
|--------|:--:|:--:|-------------|:------:|:--:|
| Core API | 2 | 8 | CPU | 70% | 300s |
| Core Workers (각) | 1 | 4 | `core_worker_queue_depth` | 500 pending msgs | 300s |
| Oracle | 2 | 6 | CPU | 70% | 300s |
| Vision | 2 | 6 | CPU | 70% | 300s |
| Synapse | 2 | 6 | CPU | 70% | 300s |
| Weaver | 1 | 3 | CPU | 70% | 300s |

> 리소스 사양(CPU, 메모리)은 [performance-monitoring.md](../08_operations/performance-monitoring.md) §10.1을 참조한다.

### 6.6 Resource Limits

| 서비스 | CPU Request | CPU Limit | Memory Request | Memory Limit |
|--------|:--:|:--:|:--:|:--:|
| Core API | 500m | 2000m | 1Gi | 4Gi |
| Core Workers | 250m | 1000m | 512Mi | 2Gi |
| Oracle | 500m | 2000m | 512Mi | 2Gi |
| Vision | 500m | 2000m | 1Gi | 4Gi |
| Synapse | 500m | 2000m | 1Gi | 4Gi |
| Weaver | 250m | 1000m | 512Mi | 2Gi |

---

## 7. Graceful Degradation 전략

### 7.1 열화 수준 정의

| Level | 이름 | 조건 | 동작 |
|:-----:|------|------|------|
| **0** | Normal | 모든 서비스 정상 | 전체 기능 사용 가능 |
| **1** | Degraded | 모듈 서비스(Oracle/Vision/Synapse/Weaver) 1개 이상 장애 | Core CRUD 정상. 장애 모듈 기능은 "일시적으로 사용 불가능합니다" 배너 표시. Canvas에서 서비스 상태 인디케이터 표시 |
| **2** | Critical | Redis 장애 | 이벤트 → DB Outbox에 축적 (Redis 복구 후 재발행). Rate Limiting → 인메모리 카운터 (정밀도 저하). 캐시 미스 → DB 직접 조회. 알림 지연 |
| **3** | Emergency | PostgreSQL Primary 장애 | Read Replica 사용 가능 시 읽기 전용 모드. 쓰기 → 503. Canvas에 유지보수 배너 표시 |

### 7.2 서비스별 열화 동작

| 장애 서비스 | 영향받는 기능 | 정상 유지 기능 |
|-----------|------------|-------------|
| Oracle 장애 | NL2SQL, ReAct Agent | Cases, Docs, OLAP, Watch, Process |
| Vision 장애 | What-if, OLAP, Root Cause, NL-Pivot | Cases, Docs, NL2SQL, Watch, Process |
| Synapse 장애 | 온톨로지, 프로세스 마이닝, NER 추출 | Cases, Docs, NL2SQL, OLAP, Watch |
| Weaver 장애 | 데이터소스 관리, Cross-DB 쿼리 | 전체 (데이터 패브릭 외) |
| Redis 장애 | 이벤트 실시간 전달, 캐시, Rate Limit 정밀도 | CRUD (DB 직접), 인메모리 Rate Limit |
| Neo4j 장애 | NL2SQL (Oracle), 온톨로지 (Synapse) | Cases, Docs, OLAP (Vision), Watch |

---

## 8. Incident Management Runbooks

### 8.1 장애 대응 프로세스

```
감지 (Detection)
  │ Prometheus 알림 / Sentry 에러 / 사용자 보고
  ▼
분류 (Classification)
  │ 심각도 결정: Critical / Warning / Info
  │ 영향 범위 확인: 전체 / 특정 테넌트 / 특정 기능
  ▼
대응 (Response)
  │ Runbook 실행
  │ 에스컬레이션 (필요 시)
  ▼
복구 (Recovery)
  │ 서비스 정상화 확인
  │ 모니터링 대시보드 확인
  ▼
포스트모템 (Post-mortem)
  │ 근본 원인 분석
  │ 재발 방지 대책
  └── 문서화
```

### 8.2 시나리오별 Runbook

#### Runbook 1: Core API 무응답

```
증상: ServiceDown 알림 (core), 502 에러 급증
즉시 조치 (< 5분):
  1. kubectl get pods -n axiom -l app=core-api
  2. OOMKilled 확인: kubectl describe pod <pod-name>
  3. Pod 재시작: kubectl rollout restart deployment/core-api -n axiom
진단:
  - 로그 확인: kubectl logs -f deployment/core-api -n axiom --tail=100
  - 메모리 사용 확인: Grafana → Data Infrastructure → PostgreSQL 커넥션 풀
  - 최근 배포 확인: kubectl rollout history deployment/core-api -n axiom
복구:
  - OOM → Resource Limit 증가
  - DB Pool 고갈 → DB_POOL_SIZE 증가 또는 누수 쿼리 식별
  - 배포 문제 → kubectl rollout undo deployment/core-api -n axiom
에스컬레이션: 5분 내 복구 불가 시 → 팀 리드
```

#### Runbook 2: Oracle NL2SQL 실패 (LLM Rate Limit)

```
증상: LLMErrorRate 알림 (oracle), CircuitBreakerOpen 알림 (oracle → openai)
즉시 조치:
  1. OpenAI 상태 페이지 확인: status.openai.com
  2. LLM Fallback 확인: Grafana → LLM Operations → Fallback 횟수
  3. Fallback 체인 작동 여부: gpt-4o → gpt-4o-mini → (Claude)
진단:
  - Rate Limit 여부: 429 응답 로그 확인
  - API 키 유효성: OpenAI 대시보드에서 확인
  - 토큰 예산: Grafana → LLM Operations → 토큰 사용량
복구:
  - Rate Limit → 요청 간격 조절 또는 API 키 추가
  - 프로바이더 장애 → ANTHROPIC_API_KEY 설정하여 Claude로 전환
에스컬레이션: Fallback 체인 전체 실패 시 → 팀 리드
```

#### Runbook 3: Vision 컴퓨트 타임아웃

```
증상: HighLatency 알림 (vision), 시나리오 솔버 타임아웃
즉시 조치:
  1. Vision Pod 상태 확인: kubectl get pods -l app=vision
  2. 활성 컴퓨팅 수 확인: Grafana → vision_active_computations
진단:
  - 솔버 파라미터 확인: 과도한 변수/제약 조건
  - MV 갱신 상태: vision_mv_refresh_duration_seconds
  - PostgreSQL 슬로우 쿼리: pg_stat_statements
복구:
  - 과부하 → HPA 스케일 업 확인, 수동 스케일: kubectl scale deployment/vision --replicas=4
  - 슬로우 쿼리 → EXPLAIN ANALYZE 후 인덱스 추가
```

#### Runbook 4: Synapse Neo4j 연결 실패

```
증상: Synapse readiness 실패, synapse_neo4j_pool_usage = 0
즉시 조치:
  1. Neo4j 상태 확인: kubectl get pods -l app=neo4j
  2. Neo4j 로그: kubectl logs deployment/neo4j -n axiom --tail=50
진단:
  - 디스크 풀: Neo4j 데이터 볼륨 사용률
  - 커넥션 풀 누수: Bolt 커넥션 수 확인
  - 메모리 부족: Neo4j heap 사용률
복구:
  - Pod 재시작: kubectl rollout restart deployment/neo4j
  - 디스크 풀 → PVC 확장
  - 메모리 → Neo4j heap 설정 증가 (dbms.memory.heap.max_size)
에스컬레이션: Neo4j 재시작 후에도 연결 불가 → 인프라 팀
```

#### Runbook 5: Redis 클러스터 장애

```
증상: RedisHighMemory 알림, 전 서비스 Redis 연결 에러
즉시 조치:
  1. Redis 상태: redis-cli -h <host> ping
  2. ElastiCache 콘솔 확인
  3. §7 Level 2 (Critical) 열화 모드 진입 확인
진단:
  - 메모리 사용: redis-cli info memory
  - 큰 키 확인: redis-cli --bigkeys
  - Stream 길이: XLEN axiom:events, axiom:workers
복구:
  - 메모리 부족 → MAXLEN 축소, 캐시 TTL 감소
  - 클러스터 장애 → ElastiCache failover 트리거
  - 지속 → ElastiCache 인스턴스 업그레이드
에스컬레이션: 10분 내 복구 불가 시 → 인프라 팀 + 팀 리드
```

#### Runbook 6: PostgreSQL Primary 장애

```
증상: ServiceDown (전 서비스), DB 연결 에러 급증
즉시 조치:
  1. §7 Level 3 (Emergency) 열화 모드 진입
  2. RDS 콘솔 상태 확인
  3. Read Replica 가용 시 읽기 전용 모드 전환
진단:
  - RDS 이벤트 로그
  - 커넥션 수: SELECT count(*) FROM pg_stat_activity
  - 디스크 사용: CloudWatch RDS 메트릭
복구:
  - RDS Multi-AZ → 자동 Failover 대기 (보통 1-2분)
  - 수동 Failover: RDS 콘솔 → Actions → Failover
  - 장기 → 백업에서 복구
에스컬레이션: 즉시 인프라 팀 + 팀 리드 + CTO
```

#### Runbook 7: Event Outbox 적체 증가

```
증상: OutboxBacklog 알림 (core_event_outbox_pending > 1000)
즉시 조치:
  1. sync_worker 상태: kubectl get pods -l app=sync-worker
  2. Redis 연결 확인: sync_worker 로그에서 Redis 에러 검색
진단:
  - sync_worker 에러 로그
  - Redis Streams 상태: XINFO STREAM axiom:events
  - Outbox 테이블 상태: SELECT status, count(*) FROM event_outbox GROUP BY status
복구:
  - Worker 재시작: kubectl rollout restart deployment/sync-worker
  - Worker 인스턴스 추가: kubectl scale deployment/sync-worker --replicas=3
  - Redis 장애 → Runbook 5 참조
```

#### Runbook 8: DLQ 메시지 누적

```
증상: DLQBacklog 알림 (core_dlq_depth > 100)
즉시 조치:
  1. DLQ 메시지 확인: GET /admin/dlq/streams
  2. 실패 패턴 분석: 동일 에러? 특정 스트림 집중?
진단:
  - 실패 메시지의 공통 에러 확인
  - 다운스트림 서비스 상태 확인 (Synapse, Vision 등)
  - 메시지 내용 검토: GET /admin/dlq/streams/{stream}
복구:
  - 일시적 장애 해소 후: POST /admin/dlq/streams/{stream}/{id}/retry (일괄 재처리)
  - 영구 실패 (포맷 에러 등): 수동 확인 후 삭제
  - 구조적 문제: 코드 수정 후 배포 → 재처리
```

#### Runbook 9: Worker 프로세스 크래시 루프

```
증상: Worker Pod CrashLoopBackOff, Worker 관련 알림
즉시 조치:
  1. kubectl describe pod <worker-pod> -n axiom (종료 코드 확인)
  2. kubectl logs <worker-pod> -n axiom --previous (이전 로그)
진단:
  - 종료 코드 137: OOMKilled → 메모리 증가
  - 종료 코드 1: 코드 에러 → 스택 트레이스 확인
  - Import 에러: 패키지 의존성 확인
복구:
  - OOM → Resource Limit 증가
  - 코드 에러 → 이전 버전 롤백
  - 의존성 → Docker 이미지 재빌드
```

#### Runbook 10: LLM 프로바이더 전체 장애

```
증상: LLMErrorRate 알림 (전 프로바이더), CircuitBreakerOpen (전 LLM 호출)
즉시 조치:
  1. OpenAI status page 확인
  2. Anthropic status page 확인
  3. Fallback Chain 전체 실패 확인
진단:
  - 네트워크 문제 (egress 차단 등)
  - API 키 만료/제한
  - DNS 해석 실패
복구:
  - 네트워크 → 보안 그룹/방화벽 확인
  - Ollama 로컬 모드 (개발 환경만): OLLAMA_BASE_URL 설정
  - LLM 기능 일시 비활성화: BPM 수동 모드로 전환 (기존 결정 사항)
에스컬레이션: 즉시 팀 리드 (LLM 의존 기능 전체 영향)
```

### 8.3 에스컬레이션 매트릭스

| 심각도 | 응답 시간 | 1차 대응 | 에스컬레이션 (미해결 시) |
|:------:|:--------:|---------|----------------------|
| Critical | 5분 | 당직 엔지니어 | 15분 → 팀 리드, 30분 → CTO |
| Warning | 30분 | 담당 팀 | 2시간 → 팀 리드 |
| Info | 다음 근무일 | 담당 엔지니어 | 필요 시 |

### 8.4 포스트모템 템플릿

```markdown
# 포스트모템: [제목]

## 요약
- 발생 시각:
- 복구 시각:
- 영향 범위:
- 심각도:

## 타임라인
| 시각 | 이벤트 |
|------|--------|
| HH:MM | 알림 수신 |
| HH:MM | 대응 시작 |
| HH:MM | 복구 완료 |

## 근본 원인

## 영향 분석
- 영향받은 사용자 수:
- 영향받은 기능:
- 에러 버짓 소모:

## 대응 결과
- 잘 된 점:
- 개선할 점:

## 재발 방지 대책
| 항목 | 담당자 | 기한 | 상태 |
|------|--------|------|------|
```

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| [architecture-overview.md](./architecture-overview.md) | §5 장애 격리 — 이 문서의 SSOT를 참조 |
| [event-driven.md](./event-driven.md) | §5 Consumer Group, at-least-once 보장 |
| [event-outbox.md](../06_data/event-outbox.md) | Event Outbox 패턴, Redis Streams 설정, 멱등성 |
| [gateway-api.md](../02_api/gateway-api.md) | 타임아웃 정책, Rate Limiting, 에러 코드 (SERVICE_CIRCUIT_OPEN) |
| [worker-system.md](../03_backend/worker-system.md) | BaseWorker 재시도, DLQ 라우팅 |
| [transaction-boundaries.md](../03_backend/transaction-boundaries.md) | Saga 패턴, 보상 실패 시 DLQ |
| [performance-monitoring.md](../08_operations/performance-monitoring.md) | Prometheus 메트릭 (§3), 알림 규칙 (§4), Grafana 대시보드 (§5), OpenTelemetry (§6), 용량 계획 (§10) |
| [logging-system.md](../08_operations/logging-system.md) | 구조화 로깅, 복원력 로그 이벤트 |
| [deployment.md](../08_operations/deployment.md) | K8s Probe 설정, PDB, 롤백 절차 |
| [configuration.md](../08_operations/configuration.md) | Circuit Breaker/DLQ 환경 변수 |
| [ADR-005-saga-compensation.md](../99_decisions/ADR-005-saga-compensation.md) | Saga 보상 패턴 결정 |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 (서비스 의존성, Circuit Breaker, Fallback, DLQ, K8s Probe, Degradation, Runbooks) |
