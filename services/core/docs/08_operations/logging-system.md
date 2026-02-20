# 로깅 체계 및 AI 기반 로그 분석

<!-- affects: operations, backend, frontend, security -->
<!-- requires-update: 08_operations/performance-monitoring.md, 각 서비스 deployment.md -->

> **최종 수정일**: 2026-02-20
> **상태**: Draft
> **범위**: Cross-service (Core, Oracle, Vision, Synapse, Weaver, Canvas)

---

## 이 문서가 답하는 질문

- Axiom의 로깅 표준과 수집 파이프라인은 어떻게 구성되는가?
- 로그 보관 정책은 어떻게 되며 7일 기준의 근거는 무엇인가?
- 시스템 관리자가 AI 챗봇을 통해 로그를 분석하는 방법은?
- 서비스별 로그 레벨 관리와 동적 변경은 어떻게 하는가?
- 로그에서 민감 정보는 어떻게 보호되는가?

---

## 1. 로깅 아키텍처 전체 개요

```
┌─ Axiom 로깅 아키텍처 ──────────────────────────────────────────────────┐
│                                                                          │
│  ┌─ 서비스 계층 ──────────────────────────────────────────────────┐    │
│  │                                                                  │    │
│  │  Core API    Oracle    Vision    Synapse    Weaver    Workers    │    │
│  │  (structlog JSON → stdout)                                       │    │
│  │                                                                  │    │
│  │  Canvas (Browser)                                                │    │
│  │  (Sentry SDK → Sentry, console.error → DevTools)                │    │
│  │                                                                  │    │
│  └────────────────────┬─────────────────────────────────────────────┘    │
│                       │ stdout (JSON lines)                              │
│                       ▼                                                  │
│  ┌─ 수집 계층 ────────────────────────────────────────────────────┐    │
│  │                                                                  │    │
│  │  Fluent Bit (DaemonSet)                                          │    │
│  │  ├── Parser: JSON 파싱 + 메타데이터 추가                        │    │
│  │  ├── Filter: PII 마스킹, 불필요 필드 제거                       │    │
│  │  ├── Buffer: 파일 기반 버퍼 (유실 방지)                         │    │
│  │  └── Output: 환경별 라우팅                                       │    │
│  │                                                                  │    │
│  └────────────────────┬─────────────────────────────────────────────┘    │
│                       │                                                  │
│           ┌───────────┼───────────┐                                      │
│           ▼           ▼           ▼                                      │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐                              │
│  │ Loki       │ │CloudWatch│ │ DataDog  │                              │
│  │ (개발)     │ │(스테이징)│ │ (프로덕션│                              │
│  │ 7일 보관   │ │ 7일 보관 │ │  APM 연동│                              │
│  └─────┬──────┘ └────┬─────┘ │ 7일 보관)│                              │
│        │             │       └────┬─────┘                              │
│        └──────┬──────┘            │                                      │
│               │                   │                                      │
│               ▼                   ▼                                      │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  Grafana (Explore / Dashboards)                               │      │
│  │  ├── 로그 탐색 (LogQL / CloudWatch Insights)                  │      │
│  │  ├── 로그 ↔ 메트릭 ↔ 트레이스 상관관계                       │      │
│  │  └── 알림 연동                                                │      │
│  └──────────────────────────────────────────────────────────────┘      │
│               │                                                          │
│               ▼                                                          │
│  ┌──────────────────────────────────────────────────────────────┐      │
│  │  AI 로그 분석 챗봇 (Admin 전용)                               │      │
│  │  ├── Grafana + LLM API 연동                                   │      │
│  │  ├── 자연어 로그 질의 → LogQL 변환                            │      │
│  │  └── 자동 근본 원인 분석 + 대응 제안                          │      │
│  └──────────────────────────────────────────────────────────────┘      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 구조화 로깅 표준

### 2.1 structlog 설정

모든 백엔드 서비스는 `structlog`를 사용하여 JSON 구조화 로그를 출력한다.

```python
# 각 서비스 공통: app/core/logging.py

import structlog
import logging
from app.core.config import settings

def setup_logging():
    """서비스 로깅 초기화"""

    # 기본 로그 레벨
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,   # ContextVar 자동 주입
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            _add_service_context,                      # 서비스 메타 주입
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _mask_sensitive_fields,                     # PII 마스킹
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def _add_service_context(logger, method_name, event_dict):
    """서비스명, 버전, 환경 자동 주입"""
    event_dict.setdefault("service", settings.SERVICE_NAME)
    event_dict.setdefault("version", settings.APP_VERSION)
    event_dict.setdefault("env", settings.APP_ENV)
    return event_dict


def _mask_sensitive_fields(logger, method_name, event_dict):
    """민감 정보 마스킹"""
    SENSITIVE_KEYS = {
        "password", "token", "secret", "api_key",
        "authorization", "cookie", "ssn", "credit_card",
    }
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict
```

### 2.2 필수 로그 필드

| 필드 | 필수 | 타입 | 설명 | 예시 |
|------|:----:|------|------|------|
| `timestamp` | Y | string | ISO 8601 UTC | `2026-02-20T10:30:00.000Z` |
| `level` | Y | string | 로그 레벨 | `info`, `error`, `warning` |
| `event` | Y | string | 이벤트명 (snake_case) | `api_request_completed` |
| `service` | Y | string | 서비스명 | `core`, `oracle`, `vision` |
| `env` | Y | string | 환경 | `dev`, `staging`, `production` |
| `tenant_id` | Y | UUID | 멀티테넌트 격리 | `550e8400-e29b...` |
| `request_id` | Y | UUID | 요청 추적 ID | `6ba7b810-9dad...` |
| `trace_id` | 조건 | string | OpenTelemetry trace ID | `abc123def456` |
| `user_id` | 조건 | UUID | 요청 사용자 | `7c9e6679-7425...` |
| `duration_ms` | 조건 | number | 처리 시간 (완료 시) | `350` |
| `error` | 조건 | string | 에러 메시지 | `Connection timeout` |
| `stack_trace` | 조건 | string | 스택 트레이스 | (에러 + DEBUG 시) |

### 2.3 로그 이벤트 명명 규칙

```
[대상]_[동작]_[상태]

예시:
  api_request_started          # API 요청 시작
  api_request_completed        # API 요청 완료
  api_request_failed           # API 요청 실패
  db_query_slow                # 슬로우 쿼리 감지
  llm_call_completed           # LLM 호출 완료
  llm_call_fallback            # LLM Fallback 발생
  worker_task_started          # Worker 작업 시작
  worker_task_completed        # Worker 작업 완료
  cache_hit                    # 캐시 히트
  cache_miss                   # 캐시 미스
  auth_login_success           # 로그인 성공
  auth_login_failed            # 로그인 실패
  event_published              # 이벤트 발행
  event_consumed               # 이벤트 소비
  event_consume_failed         # 이벤트 소비 실패
```

### 2.4 복원력 로그 이벤트

| 이벤트명 | 레벨 | 설명 |
|---------|------|------|
| `circuit_breaker_opened` | warning | Circuit Breaker가 OPEN 상태로 전환 |
| `circuit_breaker_closed` | info | Circuit Breaker가 CLOSED 상태로 복구 |
| `circuit_breaker_half_open` | info | Circuit Breaker가 HALF_OPEN 상태로 전환 |
| `fallback_activated` | warning | Fallback 전략 활성화 (target_service, fallback_type) |
| `dlq_message_added` | warning | 메시지가 DLQ로 이동 (stream, message_id, error) |
| `dlq_message_reprocessed` | info | DLQ 메시지 재처리 (stream, message_id) |
| `probe_readiness_failed` | warning | Readiness probe 실패 (failed_checks) |

> 상세 설계: [resilience-patterns.md](../01_architecture/resilience-patterns.md)

### 2.5 로그 레벨 가이드라인

| 레벨 | 용도 | 예시 | 보관 |
|------|------|------|------|
| `CRITICAL` | 서비스 중단 수준 장애 | DB 연결 불가, 메모리 고갈 | 전체 보관 |
| `ERROR` | 요청 실패, 예외 발생 | 500 응답, LLM API 에러 | 전체 보관 |
| `WARNING` | 잠재적 문제 감지 | 슬로우 쿼리, Rate Limit 근접, Fallback | 전체 보관 |
| `INFO` | 정상 비즈니스 이벤트 | 요청 완료, Worker 작업 완료 | 전체 보관 |
| `DEBUG` | 개발/디버깅 상세 | SQL 쿼리 텍스트, 요청/응답 body | 개발만 |

### 2.6 요청 컨텍스트 자동 주입

```python
# app/middleware/request_context.py

import uuid
import structlog
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 요청 ID (클라이언트 전달 또는 생성)
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        tenant_id = request.headers.get("X-Tenant-Id", "")
        user_id = getattr(request.state, "user_id", "")

        # ContextVar 설정 → structlog에 자동 주입
        _request_id.set(request_id)
        _tenant_id.set(tenant_id)
        _user_id.set(user_id)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

        logger = structlog.get_logger()
        logger.info("api_request_started",
                     method=request.method,
                     path=str(request.url.path))

        response = await call_next(request)

        logger.info("api_request_completed",
                     method=request.method,
                     path=str(request.url.path),
                     status=response.status_code)

        response.headers["X-Request-ID"] = request_id
        return response
```

---

## 3. 서비스별 로그 설정

### 3.1 서비스별 기본 로그 레벨

| 서비스 | 환경변수 | 개발 | 스테이징 | 프로덕션 |
|--------|---------|:----:|:-------:|:-------:|
| Core API | `LOG_LEVEL` | DEBUG | INFO | INFO |
| Core Workers | `LOG_LEVEL` | DEBUG | INFO | WARNING |
| Oracle | `LOG_LEVEL` | DEBUG | INFO | INFO |
| Vision | `LOG_LEVEL` | DEBUG | INFO | INFO |
| Synapse | `LOG_LEVEL` | DEBUG | INFO | INFO |
| Weaver | `LOG_LEVEL` | DEBUG | INFO | INFO |

### 3.2 서비스별 특화 로그 이벤트

#### Core API

```json
{"event": "api_request_completed", "method": "POST", "path": "/api/v1/cases", "status": 201, "duration_ms": 120}
{"event": "auth_login_success", "user_id": "uuid", "ip": "10.0.1.5"}
{"event": "auth_login_failed", "email": "user@example.com", "reason": "invalid_password", "ip": "10.0.1.5"}
{"event": "event_published", "event_type": "case.created", "aggregate_id": "uuid", "outbox_id": "uuid"}
```

#### Core Workers

```json
{"event": "worker_task_started", "worker": "sync_worker", "event_type": "case.created", "stream_id": "msg-123"}
{"event": "worker_task_completed", "worker": "sync_worker", "duration_ms": 2500, "stream_id": "msg-123"}
{"event": "worker_task_failed", "worker": "sync_worker", "error": "Redis connection timeout", "retry_count": 2}
```

#### Oracle

```json
{"event": "llm_call_completed", "model": "gpt-4o", "tokens": 1200, "duration_ms": 3500, "cache_hit": false}
{"event": "llm_call_fallback", "from_model": "gpt-4o", "to_model": "gpt-4o-mini", "reason": "rate_limit"}
{"event": "sql_guard_rejected", "reason": "mutation_detected", "query_preview": "UPDATE ..."}
{"event": "cache_hit", "cache_type": "nl2sql", "confidence": 0.95, "original_question": "..."}
```

#### Vision

```json
{"event": "olap_query_completed", "datasource_id": "uuid", "duration_ms": 800, "rows_returned": 1500}
{"event": "mv_refresh_completed", "view": "sales_summary", "duration_ms": 45000}
{"event": "mv_refresh_failed", "view": "sales_summary", "error": "lock timeout"}
```

#### Synapse

```json
{"event": "document_extraction_started", "doc_id": "uuid", "doc_type": "pdf", "page_count": 45}
{"event": "document_extraction_completed", "doc_id": "uuid", "entities": 120, "duration_ms": 55000}
{"event": "hitl_review_required", "doc_id": "uuid", "confidence": 0.68, "entity": "금액"}
{"event": "neo4j_query_completed", "query_type": "vector_search", "duration_ms": 150, "results": 10}
```

#### Weaver

```json
{"event": "datasource_sync_started", "datasource_id": "uuid", "type": "postgresql", "tables": 45}
{"event": "datasource_sync_completed", "datasource_id": "uuid", "tables_synced": 45, "duration_ms": 120000}
{"event": "mindsdb_prediction_completed", "model": "sales_forecast", "duration_ms": 5000}
```

### 3.3 동적 로그 레벨 변경

운영 중 재배포 없이 로그 레벨을 변경할 수 있는 관리자 API를 제공한다.

```python
# app/api/admin/log_admin.py

from fastapi import APIRouter, Depends
from app.core.auth import require_role

router = APIRouter(prefix="/admin/log", tags=["admin"])

@router.put("/level")
async def change_log_level(
    level: str,        # "DEBUG" | "INFO" | "WARNING" | "ERROR"
    service: str = "", # 특정 로거 지정 (빈 값이면 루트)
    _=Depends(require_role("admin"))
):
    """
    운영 중 로그 레벨 동적 변경 (Admin 전용)
    - 변경은 해당 Pod에만 적용 (재시작 시 환경변수 기준 복원)
    - 변경 이력은 audit log로 기록
    """
    import logging
    target_logger = logging.getLogger(service) if service else logging.getLogger()
    target_logger.setLevel(getattr(logging, level.upper()))

    structlog.get_logger().warning(
        "log_level_changed",
        new_level=level,
        target_logger=service or "root",
    )
    return {"status": "ok", "level": level, "logger": service or "root"}


@router.get("/level")
async def get_log_level(
    _=Depends(require_role("admin"))
):
    """현재 로그 레벨 조회"""
    import logging
    root_level = logging.getLogger().getEffectiveLevel()
    return {"level": logging.getLevelName(root_level)}
```

---

## 4. 로그 수집 파이프라인 (Fluent Bit)

### 4.1 Fluent Bit 설정

```ini
# infra/fluent-bit/fluent-bit.conf

[SERVICE]
    Flush         5
    Log_Level     info
    Daemon        off
    Parsers_File  parsers.conf
    HTTP_Server   On
    HTTP_Listen   0.0.0.0
    HTTP_Port     2020
    storage.path  /var/log/flb-storage/    # 파일 기반 버퍼 (유실 방지)

# ─── 입력: Kubernetes Pod 로그 ───
[INPUT]
    Name              tail
    Tag               kube.*
    Path              /var/log/containers/axiom-*.log
    Parser            docker
    DB                /var/log/flb_kube.db
    Mem_Buf_Limit     10MB
    Refresh_Interval  5

# ─── 필터: Kubernetes 메타데이터 추가 ───
[FILTER]
    Name                kubernetes
    Match               kube.*
    Kube_URL            https://kubernetes.default.svc:443
    Kube_Tag_Prefix     kube.var.log.containers.
    Merge_Log           On
    Keep_Log            Off

# ─── 필터: PII 마스킹 (2차 방어) ───
[FILTER]
    Name    lua
    Match   kube.*
    script  /fluent-bit/scripts/mask_pii.lua
    call    mask_sensitive_data

# ─── 출력: Loki (개발 환경) ───
[OUTPUT]
    Name        loki
    Match       kube.*
    Host        loki
    Port        3100
    Labels      job=axiom, service=$service, env=$env
    Line_Format json

# ─── 출력: CloudWatch (스테이징/프로덕션) ───
[OUTPUT]
    Name              cloudwatch_logs
    Match             kube.*
    region            ap-northeast-2
    log_group_name    /axiom/${ENV}
    log_stream_prefix ${SERVICE_NAME}-
    auto_create_group On
```

### 4.2 PII 마스킹 (Lua 스크립트)

```lua
-- infra/fluent-bit/scripts/mask_pii.lua

function mask_sensitive_data(tag, timestamp, record)
    local sensitive_patterns = {
        -- 주민등록번호 (한국)
        {pattern = "%d%d%d%d%d%d%-%d%d%d%d%d%d%d", mask = "******-*******"},
        -- 이메일 (로그 메시지 내)
        {pattern = "[%w%.%-]+@[%w%.%-]+%.%w+", mask = "[EMAIL]"},
        -- 신용카드번호
        {pattern = "%d%d%d%d%-%d%d%d%d%-%d%d%d%d%-%d%d%d%d", mask = "****-****-****-****"},
        -- 전화번호 (한국)
        {pattern = "01[016789]%-%d%d%d%d%-%d%d%d%d", mask = "***-****-****"},
    }

    -- 로그 메시지 내 PII 패턴 마스킹
    if record["message"] then
        for _, p in ipairs(sensitive_patterns) do
            record["message"] = string.gsub(record["message"], p.pattern, p.mask)
        end
    end

    return 1, timestamp, record
end
```

---

## 5. 로그 보관 정책

### 5.1 보관 기간: 7일

| 환경 | 저장소 | 보관 기간 | 근거 |
|------|--------|:---------:|------|
| **개발** | Loki (로컬 스토리지) | 7일 | 디버깅 주기 충분 |
| **스테이징** | CloudWatch Logs | 7일 | 스테이징 테스트 사이클 |
| **프로덕션** | CloudWatch Logs + DataDog | 7일 | 아래 근거 참조 |

#### 7일 보관 근거

```
[결정] 모든 환경에서 로그를 7일간 보관한다.
[근거]
  1. 인시던트 대응 주기: 대부분의 문제는 발생 후 48시간 내 감지되며,
     근본 원인 분석(RCA)에 최대 5일 소요 → 7일이면 충분
  2. 비용 효율성: CloudWatch Logs 비용은 보관량에 비례
     - 7일: ~$50/월 (5개 서비스 기준)
     - 30일: ~$200/월
     - 90일: ~$600/월
  3. 규정 준수: 감사 로그(audit log)는 별도 보관 (하단 참조)
  4. 메트릭/알림 보완: 7일 이전 데이터는 Prometheus 메트릭 +
     Sentry 이슈 이력으로 대체 가능
```

### 5.2 보관 계층 구조

```
┌─ 로그 보관 계층 ────────────────────────────────────────────┐
│                                                               │
│  Layer 1: Hot (실시간 ~ 7일)                                 │
│  ├── Loki / CloudWatch Logs                                  │
│  ├── 전체 로그 (모든 레벨)                                   │
│  ├── 자유 검색 가능 (LogQL / CloudWatch Insights)            │
│  └── AI 챗봇 분석 대상                                       │
│                                                               │
│  Layer 2: Warm (7일 ~ 90일) - 선택적 보관                    │
│  ├── S3 Glacier Instant Retrieval (ERROR/CRITICAL만)         │
│  ├── Fluent Bit → S3 Output 플러그인                         │
│  └── 필요 시 S3 Select로 조회                                │
│                                                               │
│  Layer 3: Cold (감사 로그 전용, 1년+)                        │
│  ├── S3 Glacier Deep Archive                                  │
│  ├── 대상: auth_login_*, permission_*, data_export_*         │
│  └── 규정 준수 목적 (접근 빈도 극히 낮음)                    │
│                                                               │
│  Layer 4: 영구 (메트릭/대시보드)                             │
│  ├── Prometheus → Thanos (장기 메트릭)                       │
│  ├── Sentry 이슈 이력 (영구)                                 │
│  └── Grafana 스냅샷 (수동 보존)                              │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 5.3 자동 삭제 설정

```yaml
# Loki (개발 환경)
# infra/loki/loki-config.yaml
limits_config:
  retention_period: 168h  # 7일 = 168시간

# CloudWatch (스테이징/프로덕션)
# infra/terraform/cloudwatch.tf
resource "aws_cloudwatch_log_group" "axiom_logs" {
  name              = "/axiom/${var.env}"
  retention_in_days = 7
}

# S3 Lifecycle (Layer 2: Warm)
resource "aws_s3_bucket_lifecycle_configuration" "log_archive" {
  bucket = aws_s3_bucket.log_archive.id

  rule {
    id     = "error-logs-to-glacier"
    status = "Enabled"

    filter {
      prefix = "logs/error/"
    }

    transition {
      days          = 7
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 90
    }
  }
}
```

### 5.4 감사 로그 (Audit Log) 별도 보관

보안 및 규정 준수를 위해 다음 이벤트는 7일 제한과 별도로 1년 이상 보관한다.

| 감사 대상 | 이벤트 패턴 | 보관 기간 |
|----------|-----------|:---------:|
| 로그인/로그아웃 | `auth_login_*`, `auth_logout` | 1년 |
| 권한 변경 | `permission_changed`, `role_assigned` | 1년 |
| 데이터 내보내기 | `data_export_*` | 1년 |
| 관리자 작업 | `admin_*` | 1년 |
| 설정 변경 | `config_changed`, `log_level_changed` | 1년 |

```python
# app/core/audit_logger.py

import structlog

audit_logger = structlog.get_logger("audit")

async def log_audit(event: str, actor_id: str, details: dict):
    """감사 로그 기록 (별도 스트림으로 S3 직접 전송)"""
    audit_logger.info(
        event,
        actor_id=actor_id,
        audit=True,  # Fluent Bit에서 이 플래그로 S3 라우팅
        **details,
    )
```

---

## 6. AI 챗봇 기반 로그 분석

### 6.1 개요

시스템 관리자가 자연어로 로그를 조회하고 문제를 분석할 수 있도록 AI 챗봇 인터페이스를 제공한다. Grafana의 로그 데이터를 LLM이 분석하여 근본 원인과 대응 방안을 제시한다.

```
┌─ AI 로그 분석 흐름 ──────────────────────────────────────────┐
│                                                                │
│  관리자                    AI 분석 API                         │
│    │                         │                                 │
│    │ "지난 1시간 Oracle      │                                 │
│    │  에러 원인 분석해줘"    │                                 │
│    │ ─────────────────────▶ │                                 │
│    │                         │  1. 의도 파악 (LLM)             │
│    │                         │  ├── 대상: Oracle 서비스         │
│    │                         │  ├── 기간: 1시간                │
│    │                         │  └── 작업: 에러 분석             │
│    │                         │                                 │
│    │                         │  2. LogQL/Insights 생성          │
│    │                         │  └── {service="oracle"}          │
│    │                         │      |= "error" | json          │
│    │                         │      | line_format "{{.event}}"  │
│    │                         │                                 │
│    │                         │  3. Loki/CloudWatch 조회         │
│    │                         │  └── 에러 로그 128건 수집        │
│    │                         │                                 │
│    │                         │  4. LLM 분석                    │
│    │                         │  ├── 에러 패턴 클러스터링        │
│    │                         │  ├── 시간대별 발생 분포          │
│    │                         │  └── 근본 원인 + 대응 제안       │
│    │                         │                                 │
│    │  분석 결과              │                                 │
│    │ ◀───────────────────── │                                 │
│    │                         │                                 │
│    │  "Oracle Rate Limit     │                                 │
│    │   에러가 80% 차지.      │                                 │
│    │   OpenAI API 한도 초과  │                                 │
│    │   → Fallback 모델       │                                 │
│    │     전환 권장"          │                                 │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 6.2 AI 로그 분석 API

```python
# app/api/admin/log_analysis.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import require_role
from app.services.log_analyzer import LogAnalyzer

router = APIRouter(prefix="/admin/log-analysis", tags=["admin"])

class LogAnalysisRequest(BaseModel):
    question: str               # 자연어 질문
    time_range: str = "1h"      # 분석 대상 기간 (1h, 6h, 24h, 7d)
    service: str | None = None  # 특정 서비스 필터 (없으면 전체)
    level: str | None = None    # 특정 레벨 필터

class LogAnalysisResponse(BaseModel):
    summary: str                # 분석 요약
    root_cause: str             # 추정 근본 원인
    recommendation: str         # 권장 대응
    log_query: str              # 실행된 로그 쿼리 (투명성)
    log_count: int              # 분석된 로그 수
    error_patterns: list[dict]  # 에러 패턴 분류
    related_alerts: list[str]   # 관련 활성 알림

@router.post("", response_model=LogAnalysisResponse)
async def analyze_logs(
    request: LogAnalysisRequest,
    _=Depends(require_role("admin"))
):
    """
    AI 기반 로그 분석 (Admin 전용)
    1. 자연어 → 로그 쿼리 변환
    2. Loki/CloudWatch에서 로그 조회
    3. LLM으로 패턴 분석 + 원인 추정
    """
    analyzer = LogAnalyzer()
    return await analyzer.analyze(
        question=request.question,
        time_range=request.time_range,
        service=request.service,
        level=request.level,
    )
```

### 6.3 LogAnalyzer 서비스

```python
# app/services/log_analyzer.py

import structlog
from app.core.llm import get_llm_client
from app.services.log_query_builder import LogQueryBuilder
from app.services.log_store import LogStore

logger = structlog.get_logger()

class LogAnalyzer:
    def __init__(self):
        self.llm = get_llm_client()
        self.query_builder = LogQueryBuilder()
        self.log_store = LogStore()

    async def analyze(
        self,
        question: str,
        time_range: str,
        service: str | None,
        level: str | None,
    ) -> dict:
        # Step 1: 자연어 → LogQL 변환
        log_query = await self._build_query(question, time_range, service, level)
        logger.info("log_analysis_query_built", query=log_query)

        # Step 2: 로그 조회 (최대 500건 샘플링)
        logs = await self.log_store.query(log_query, limit=500)
        logger.info("log_analysis_logs_fetched", count=len(logs))

        if not logs:
            return {
                "summary": "해당 기간에 일치하는 로그가 없습니다.",
                "root_cause": "N/A",
                "recommendation": "시간 범위를 확장하거나 필터 조건을 변경해보세요.",
                "log_query": log_query,
                "log_count": 0,
                "error_patterns": [],
                "related_alerts": [],
            }

        # Step 3: LLM 분석
        analysis = await self._analyze_with_llm(question, logs)

        # Step 4: 관련 알림 조회
        related_alerts = await self._get_related_alerts(service)

        return {
            **analysis,
            "log_query": log_query,
            "log_count": len(logs),
            "related_alerts": related_alerts,
        }

    async def _build_query(self, question, time_range, service, level):
        """자연어에서 LogQL 생성"""
        system_prompt = """당신은 Axiom 시스템의 로그 분석 전문가입니다.
사용자의 자연어 질문을 Loki LogQL 쿼리로 변환하세요.

서비스 목록: core, oracle, vision, synapse, weaver
로그 형식: JSON (structlog)
필수 필드: timestamp, level, event, service, tenant_id, request_id

LogQL 문법:
- 서비스 필터: {service="oracle"}
- 레벨 필터: | level="error"
- 텍스트 검색: |= "keyword"
- JSON 파싱: | json
- 시간은 API에서 처리하므로 쿼리에 포함하지 마세요."""

        response = await self.llm.generate(
            system=system_prompt,
            prompt=f"질문: {question}\n서비스: {service or '전체'}\n레벨: {level or '전체'}",
            model="gpt-4o-mini",  # 쿼리 생성은 가벼운 모델
            temperature=0,
        )
        return response.content.strip()

    async def _analyze_with_llm(self, question, logs):
        """로그 데이터를 LLM으로 분석"""
        # 로그를 요약 가능한 형태로 전처리
        log_summary = self._preprocess_logs(logs)

        system_prompt = """당신은 Axiom 시스템의 SRE(Site Reliability Engineer)입니다.
수집된 로그를 분석하여 다음을 제공하세요:

1. summary: 상황 요약 (2-3문장)
2. root_cause: 추정 근본 원인
3. recommendation: 구체적 대응 방안 (명령어 포함)
4. error_patterns: 에러 패턴 분류 [{pattern, count, first_seen, last_seen}]

응답은 JSON 형식으로 반환하세요.
한국어로 작성하되, 명령어/코드는 영문 그대로 유지하세요."""

        response = await self.llm.generate(
            system=system_prompt,
            prompt=f"질문: {question}\n\n수집된 로그 ({len(logs)}건):\n{log_summary}",
            model="gpt-4o",
            temperature=0,
            response_format={"type": "json_object"},
        )

        import json
        return json.loads(response.content)

    def _preprocess_logs(self, logs: list[dict]) -> str:
        """로그를 LLM 분석용으로 전처리 (토큰 절약)"""
        # 에러/경고 우선, 중복 제거, 시간 순 정렬
        from collections import Counter
        event_counts = Counter(log.get("event", "unknown") for log in logs)

        summary_lines = []
        summary_lines.append(f"=== 이벤트별 발생 횟수 ===")
        for event, count in event_counts.most_common(20):
            summary_lines.append(f"  {event}: {count}건")

        summary_lines.append(f"\n=== 대표 로그 샘플 (최근 50건) ===")
        for log in logs[-50:]:
            line = (
                f"[{log.get('timestamp', '')}] "
                f"{log.get('level', '').upper()} "
                f"{log.get('service', '')} "
                f"{log.get('event', '')} "
            )
            if log.get("error"):
                line += f"error={log['error']} "
            if log.get("duration_ms"):
                line += f"duration={log['duration_ms']}ms "
            summary_lines.append(line)

        return "\n".join(summary_lines)

    async def _get_related_alerts(self, service: str | None) -> list[str]:
        """Prometheus AlertManager에서 관련 활성 알림 조회"""
        # AlertManager API 조회
        # GET http://alertmanager:9093/api/v2/alerts?filter=job="axiom-{service}"
        return []  # 실제 구현에서 AlertManager API 연동
```

### 6.4 AI 챗봇 프리셋 질문

관리자가 자주 사용하는 분석 패턴을 프리셋으로 제공한다.

| 카테고리 | 프리셋 질문 | 설명 |
|---------|-----------|------|
| **에러 분석** | "지난 1시간 에러 요약" | 전체 서비스 에러 패턴 분석 |
| **에러 분석** | "{service} 에러 원인 분석" | 특정 서비스 에러 근본 원인 |
| **성능** | "현재 가장 느린 API 엔드포인트" | 지연 상위 API 식별 |
| **성능** | "DB 슬로우 쿼리 분석" | 1초 이상 쿼리 패턴 분석 |
| **LLM** | "LLM 호출 실패율과 원인" | LLM API 에러/Rate Limit 분석 |
| **LLM** | "토큰 사용량 이상 패턴" | 비정상 토큰 소비 감지 |
| **인프라** | "Redis 메모리 사용 추이" | Redis 메모리 이상 패턴 |
| **인프라** | "DB 커넥션 풀 상태" | 커넥션 풀 포화 여부 |
| **보안** | "로그인 실패 패턴 분석" | 브루트포스 공격 감지 |
| **비즈니스** | "HITL 대기 건수와 병목" | 리뷰 대기 적체 분석 |

### 6.5 AI 분석 응답 예시

```
┌─ AI 로그 분석 결과 ──────────────────────────────────────────┐
│                                                                │
│  🔍 질문: "지난 1시간 Oracle 에러 원인 분석해줘"              │
│                                                                │
│  📊 분석 요약                                                 │
│  지난 1시간 동안 Oracle 서비스에서 128건의 에러가 발생했습니다.│
│  주요 원인은 OpenAI API Rate Limit 초과(80%)와               │
│  DB 커넥션 타임아웃(15%)입니다.                               │
│                                                                │
│  🎯 에러 패턴                                                 │
│  ┌──────────────────────────────────────────┐                 │
│  │ 패턴                  │ 건수 │ 비율    │                 │
│  ├──────────────────────────────────────────┤                 │
│  │ llm_call_failed       │  102 │  79.7%  │                 │
│  │ (RateLimitError)      │      │         │                 │
│  ├──────────────────────────────────────────┤                 │
│  │ db_query_timeout      │   19 │  14.8%  │                 │
│  ├──────────────────────────────────────────┤                 │
│  │ cache_write_failed    │    7 │   5.5%  │                 │
│  └──────────────────────────────────────────┘                 │
│                                                                │
│  🔎 추정 근본 원인                                            │
│  14:00~14:30 사이 NL2SQL 동시 요청이 급증 (평소 3배)하면서   │
│  OpenAI API Tier 2 Rate Limit (500 RPM)을 초과.              │
│  Fallback 모델(gpt-4o-mini) 전환이 지연되어 연쇄 에러 발생.  │
│                                                                │
│  💡 권장 대응                                                  │
│  1. Fallback 임계값 조정:                                      │
│     ORACLE_LLM_FALLBACK_THRESHOLD=3 → 2                       │
│  2. Rate Limiter 강화:                                         │
│     ORACLE_MAX_LLM_CONCURRENT=10 → 5                          │
│  3. 캐시 히트율 확인:                                          │
│     현재 32% → Enum 부트스트랩 재실행 권장                    │
│                                                                │
│  🔗 실행된 쿼리                                               │
│  {service="oracle"} |= "error" | json                         │
│                                                                │
│  ⚠️ 관련 활성 알림                                             │
│  - LLMErrorRate: Oracle 에러율 12.5%                          │
│  - LowCacheHitRate: Oracle 캐시 히트율 32%                    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 6.6 AI 분석 제약사항 및 보안

| 항목 | 정책 |
|------|------|
| **접근 권한** | `admin` 역할만 사용 가능 |
| **로그 전송 범위** | LLM에 전송 시 PII 제거된 로그만 전달 |
| **토큰 제한** | 분석 1회당 최대 8,000 input tokens (로그 샘플링) |
| **Rate Limit** | 관리자당 분당 5회 분석 요청 제한 |
| **모델 선택** | 쿼리 생성: gpt-4o-mini, 분석: gpt-4o |
| **응답 캐시** | 동일 쿼리+시간범위 → 5분간 캐시 |
| **감사 로그** | 모든 분석 요청/응답은 audit log에 기록 |

---

## 7. 로그 검색 및 쿼리

### 7.1 Loki LogQL 예시 (개발 환경)

```logql
# 특정 서비스의 에러 로그
{service="oracle"} |= "error" | json | level="error"

# 특정 tenant의 모든 로그
{service=~"core|oracle|vision"} | json | tenant_id="550e8400-..."

# 슬로우 쿼리 (1초 이상)
{service=~"core|oracle|vision"} | json | duration_ms > 1000

# 특정 요청 추적 (request_id)
{service=~".+"} | json | request_id="6ba7b810-..."

# LLM Fallback 발생
{service=~"core|oracle|synapse"} |= "llm_call_fallback" | json

# 로그인 실패 (보안 모니터링)
{service="core"} |= "auth_login_failed" | json
  | count_over_time({service="core"} |= "auth_login_failed" [5m]) > 10
```

### 7.2 CloudWatch Insights 예시 (프로덕션)

```sql
-- 에러 패턴 TOP 10
fields @timestamp, service, event, error
| filter level = "error"
| stats count(*) as error_count by event, service
| sort error_count desc
| limit 10

-- 특정 tenant 요청 추적
fields @timestamp, service, event, duration_ms, status
| filter tenant_id = "550e8400-..."
| sort @timestamp asc

-- 슬로우 API 엔드포인트
fields @timestamp, service, path, duration_ms
| filter event = "api_request_completed" and duration_ms > 1000
| stats avg(duration_ms) as avg_ms, max(duration_ms) as max_ms, count(*) by path
| sort avg_ms desc
| limit 20

-- LLM 비용 분석
fields @timestamp, service, llm_model, llm_tokens
| filter event = "llm_call_completed"
| stats sum(llm_tokens) as total_tokens by llm_model, service
| sort total_tokens desc
```

---

## 8. Canvas 프론트엔드 로깅

### 8.1 프론트엔드 에러 수집 (Sentry)

Canvas 프론트엔드의 에러는 Sentry를 통해 수집한다. (`performance-monitoring.md` 8절 참조)

```typescript
// src/lib/error-logging.ts

import * as Sentry from '@sentry/react';

/**
 * 구조화된 에러 로깅 (Sentry에 컨텍스트 추가)
 */
export function logError(error: Error, context?: Record<string, unknown>) {
  Sentry.withScope((scope) => {
    if (context) {
      scope.setContext('axiom', context);
    }

    // tenant_id, user_id 자동 포함
    const authStore = useAuthStore.getState();
    if (authStore.user) {
      scope.setUser({
        id: authStore.user.id,
        email: authStore.user.email,
      });
      scope.setTag('tenant_id', authStore.user.tenant_id);
    }

    Sentry.captureException(error);
  });
}

/**
 * API 에러 전용 로깅
 */
export function logApiError(
  error: AxiosError,
  endpoint: string,
  method: string,
) {
  logError(error as Error, {
    endpoint,
    method,
    status: error.response?.status,
    request_id: error.response?.headers?.['x-request-id'],
    duration_ms: error.config?.metadata?.duration,
  });
}
```

### 8.2 프론트엔드 성능 로깅

```typescript
// src/lib/performance-logging.ts

/**
 * API 호출 시간 자동 측정 (Axios 인터셉터)
 */
instance.interceptors.request.use((config) => {
  config.metadata = { startTime: performance.now() };
  return config;
});

instance.interceptors.response.use(
  (response) => {
    const duration = performance.now() - response.config.metadata.startTime;
    if (duration > 3000) {
      // 3초 이상 → Sentry breadcrumb 기록
      Sentry.addBreadcrumb({
        category: 'api.slow',
        message: `Slow API: ${response.config.url} (${Math.round(duration)}ms)`,
        level: 'warning',
        data: {
          url: response.config.url,
          method: response.config.method,
          duration_ms: Math.round(duration),
          status: response.status,
        },
      });
    }
    return response;
  },
);
```

---

## 9. Grafana 로그 대시보드

### 9.1 로그 전용 대시보드 구성

```
┌─ Grafana: Axiom Log Explorer ──────────────────────────────────────┐
│                                                                      │
│  ┌─ 필터 바 ──────────────────────────────────────────────────┐    │
│  │ 서비스: [전체 ▼]  레벨: [전체 ▼]  기간: [1시간 ▼]  🔍    │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ 로그 볼륨 히트맵 (시간 × 서비스 × 레벨) ──────────────────┐  │
│  │                                                                │  │
│  │  14:00 ░░░░░░░░░░░░░█████░░░░░░  Core                        │  │
│  │  14:00 ░░░░░░████████████████░░░  Oracle (에러 급증)          │  │
│  │  14:00 ░░░░░░░░░░░░░░░░░░░░░░░░  Vision                     │  │
│  │  14:00 ░░░░░░░░░░░█░░░░░░░░░░░░  Synapse                    │  │
│  │  14:00 ░░░░░░░░░░░░░░░░░░░░░░░░  Weaver                     │  │
│  │                                                                │  │
│  │  색상: ░ info  ▒ warning  █ error  ██ critical                │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ 에러 패턴 TOP 10 ────────────┐  ┌─ 레벨별 비율 ──────────┐  │
│  │                                │  │                         │  │
│  │  llm_call_failed     ███ 102  │  │  INFO     ████████ 85% │  │
│  │  db_query_timeout    █    19  │  │  WARNING  ██       8%  │  │
│  │  cache_write_failed  ░     7  │  │  ERROR    █        6%  │  │
│  │  event_consume_fail  ░     3  │  │  CRITICAL ░        1%  │  │
│  │                                │  │                         │  │
│  └────────────────────────────────┘  └─────────────────────────┘  │
│                                                                      │
│  ┌─ 로그 스트림 (실시간) ──────────────────────────────────────┐  │
│  │                                                                │  │
│  │  14:32:15 ERR oracle llm_call_failed error="RateLimitError"  │  │
│  │  14:32:14 INF core   api_request_completed status=200 45ms   │  │
│  │  14:32:13 WRN oracle db_query_timeout duration=5200ms        │  │
│  │  14:32:12 INF core   event_published type=case.updated       │  │
│  │  14:32:11 INF vision olap_query_completed rows=500 800ms     │  │
│  │  ...                                                           │  │
│  │                                    [이전] [다음] [실시간 ▶]   │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─ AI 분석 패널 ─────────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  💬 AI에게 질문하기                                          │    │
│  │  ┌──────────────────────────────────────────────────────┐   │    │
│  │  │ "지난 1시간 Oracle 에러 원인 분석해줘"              │   │    │
│  │  └──────────────────────────────────────────────────────┘   │    │
│  │  [분석 시작]                                                │    │
│  │                                                              │    │
│  │  프리셋: [에러 요약] [슬로우 쿼리] [LLM 분석] [보안 점검]  │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 10. 알림 연동

로그 기반 알림은 `performance-monitoring.md` 4절의 AlertManager 규칙과 연동된다. 추가로 로그 패턴 기반 알림을 설정한다.

### 10.1 로그 기반 알림 규칙

```yaml
# Loki Recording Rules (개발 환경)
# infra/loki/rules.yaml

groups:
  - name: axiom-log-alerts
    rules:
      # 5분간 에러 로그 50건 이상
      - alert: HighErrorLogRate
        expr: |
          sum(count_over_time({service=~"core|oracle|vision|synapse|weaver"}
            | json | level="error" [5m])) > 50
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "5분간 에러 로그 {{ $value }}건"

      # 로그인 실패 10회 이상 (5분)
      - alert: BruteForceAttempt
        expr: |
          sum(count_over_time({service="core"}
            |= "auth_login_failed" [5m])) > 10
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "로그인 실패 {{ $value }}회 - 브루트포스 의심"

      # Worker 에러 연속 발생
      - alert: WorkerErrorSpike
        expr: |
          sum(count_over_time({service="core"}
            |= "worker_task_failed" [10m])) > 20
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Worker 에러 {{ $value }}건 (10분)"
```

---

## 11. 트러블슈팅 가이드

### 11.1 로그로 문제 추적하는 일반 절차

```
1. 문제 인지 (알림 또는 사용자 신고)
   │
2. Grafana Log Explorer에서 해당 시간대 로그 확인
   │  또는 AI 챗봇에 자연어 질의
   │
3. 에러 로그에서 request_id 확인
   │
4. request_id로 전체 서비스 로그 추적
   │  LogQL: {service=~".+"} | json | request_id="xxx"
   │
5. trace_id가 있으면 Jaeger/Tempo에서 분산 추적 확인
   │
6. 근본 원인 파악 → 대응 조치
   │
7. 대응 결과 확인 (로그 패턴 변화 모니터링)
```

### 11.2 자주 발생하는 문제 패턴

| 증상 | 로그 이벤트 | 원인 | 대응 |
|------|-----------|------|------|
| API 5xx 급증 | `api_request_failed` | DB/Redis 연결 문제 | 커넥션 풀 확인, Pod 재시작 |
| LLM 응답 지연 | `llm_call_completed` (duration > 15s) | API Rate Limit, 모델 과부하 | Fallback 전환, 요청 큐잉 |
| Worker 적체 | `worker_task_failed` (반복) | Redis Streams 연결 끊김 | Redis 상태 확인, Worker 재시작 |
| 캐시 미스 급증 | `cache_miss` (연속) | Redis 메모리 풀, TTL 만료 | Redis MAXLEN 확인, 캐시 워밍 |
| 로그인 실패 폭증 | `auth_login_failed` (> 10/5min) | 브루트포스 공격 | IP 차단, Rate Limit 강화 |

---

## 결정 사항 (Decisions)

- 로그 보관 기간 7일 (전 환경 통일)
  - 근거: 인시던트 RCA 주기(5일) + 여유, 비용 효율성
  - 재평가: 규정 요구사항 변경 시

- 감사 로그는 1년 이상 별도 보관
  - 근거: 보안 컴플라이언스, 접근 이력 추적 필요

- AI 로그 분석에 gpt-4o 사용 (쿼리 빌더는 gpt-4o-mini)
  - 근거: 분석 정확도 > 비용, 관리자 전용이므로 호출 빈도 낮음

- Fluent Bit를 로그 수집기로 사용 (Fluentd 아님)
  - 근거: 경량, 낮은 메모리 사용, DaemonSet 적합

- 구조화 로깅(structlog JSON) 필수
  - 근거: 파싱 자동화, 검색/필터링 용이, AI 분석 호환

## 금지됨 (Forbidden)

- 로그에 비밀번호, API 키, 토큰 원문 포함
- DEBUG 레벨을 프로덕션에서 상시 활성화 (임시 변경 후 반드시 복원)
- 로그 메시지에 사용자 개인정보(주민번호, 전화번호) 포함
- AI 분석 결과를 자동화된 조치에 바로 연결 (반드시 관리자 확인 후 실행)

## 필수 (Required)

- 모든 API 요청에 `request_id` 포함 (RequestContextMiddleware)
- 에러 발생 시 `error` + `stack_trace` 필드 필수
- LLM 호출 시 `llm_model`, `llm_tokens` 필드 필수
- 로그 레벨 변경 시 audit log 기록

---

## 관련 문서

| 문서 | 관계 |
|------|------|
| `08_operations/performance-monitoring.md` | SLO/SLA, Prometheus 메트릭, Grafana 대시보드, 알림 규칙 |
| `08_operations/deployment.md` | 환경별 로그 설정 (stdout/CloudWatch/DataDog) |
| `08_operations/configuration.md` | LOG_LEVEL, LANGCHAIN_TRACING_V2 등 환경변수 |
| `01_architecture/event-driven.md` | Redis Streams 이벤트 로그, Worker 로그 |
| `03_backend/worker-system.md` | Worker 작업 로그 패턴 |
| `05_llm/llmops-model-portfolio.md` | LLM 호출 로그, LangSmith 추적 |
| `06_data/database-operations.md` | DB 로그 이벤트 (db_query_slow, neo4j_query_slow), 슬로우 쿼리 관리 |

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-20 | 1.0 | Axiom Team | 초기 작성 (로깅 체계, 7일 보관, AI 분석 챗봇) |
