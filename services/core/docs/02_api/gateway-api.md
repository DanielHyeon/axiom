# Axiom Core - API Gateway

> 구현 상태 태그: `Implemented` (Core↔Synapse Gateway 범위)
> 기준일: 2026-02-22

## 이 문서가 답하는 질문

- API Gateway는 어떤 엔드포인트를 라우팅하는가?
- 인증이 필요한 경로와 공개 경로는 어떻게 구분되는가?
- 타임아웃과 속도 제한 정책은 어떻게 적용되는가?
- 멀티테넌트 라우팅은 어떻게 동작하는가?
- K-AIR의 Spring Boot Gateway에서 무엇을 이식하는가?

<!-- affects: frontend, security -->
<!-- requires-update: 07_security/auth-model.md -->

---

## 1. Gateway 개요

### 1.1 K-AIR -> Axiom 전환

```
[사실] K-AIR는 Spring Cloud Gateway (Java)로 API Gateway를 운영한다.
[결정] Axiom은 FastAPI 미들웨어로 Gateway 기능을 구현한다.
[근거] 전체 기술 스택을 Python으로 통일하고, 별도 Gateway 서비스를 두지 않는다.
       FastAPI의 미들웨어 + Depends() 패턴으로 동일한 기능을 구현할 수 있다.
```

### 1.2 이식 대상

```
process-gpt-gs-main/gateway/
  ├── ForwardHostHeaderFilter.java   --> app/core/middleware.py
  ├── JwtAuthFilter.java             --> app/core/security.py
  ├── WebSecurityConfig.java         --> FastAPI middleware chain
  └── application.yml (60+ routes)   --> app/core/routes.py
```

---

## 2. 라우팅 규칙

### 2.1 보호 경로 (인증 필수)

| 경로 패턴 | 대상 서비스 | 설명 | 타임아웃 |
|----------|-----------|------|---------|
| `/api/v1/cases/**` | Core | 케이스 CRUD | 30s |
| `/api/v1/process/**` | Core BPM | 프로세스 실행 | 60s |
| `/api/v1/agents/**` | Core Agent | 에이전트 관리 | 120s |
| `/api/v1/documents/**` | Core Worker | 문서 관리 | 60s |
| `/api/v1/watches/**` | Core Watch | 알림 구독/관리 | 30s |
| `/api/v1/completion/**` | Core LLM | LLM 완성 | 120s |
| `/api/v1/mcp/**` | Core MCP | MCP 도구 관리/실행 | 60s |
| `/api/v1/vision/**` | Vision (프록시) | 분석 API | 180s |
| `/api/v1/oracle/**` | Oracle (프록시) | NL2SQL API | 60s |
| `/api/v1/synapse/**` | Synapse (프록시) | 온톨로지 API | 60s |
| `/api/v1/extraction/**` | Synapse (프록시) | 문서 온톨로지 추출 API | 180s |
| `/api/v1/event-logs/**` | Core -> Synapse | 이벤트 로그 수집 (업로드/DB연결) | 300s |
| `/api/v1/process-mining/**` | Synapse (프록시) | 프로세스 마이닝 API | 180s |
| `/api/v1/schema-edit/**` | Synapse (프록시) | 스키마 편집 API | 180s |
| `/api/v1/graph/**` | Core -> Synapse | 그래프 검색/경로 탐색 프록시 | 180s |
| `/api/v1/ontology/**` | Core -> Synapse | 온톨로지 CRUD/조회 프록시 | 180s |
| `/api/v1/weaver/**` | Weaver (프록시) | 데이터 패브릭 API | 60s |

> **복원력 참조**: 각 프록시 경로의 Circuit Breaker 설정, Fallback 전략, Retry 정책은 [resilience-patterns.md](../01_architecture/resilience-patterns.md) §2~4를 참조한다.

### 2.2 공개 경로 (인증 불필요)

| 경로 | 설명 | 구현 |
|------|------|------|
| `/api/v1/auth/login` | 로그인 (JWT 발급) | Implemented — `app/api/auth/routes.py` |
| `/api/v1/auth/refresh` | 토큰 갱신 | Implemented — `app/api/auth/routes.py` |
| `/api/v1/health/*` | 헬스체크 (startup, live, ready, metrics) | Implemented — `app/api/health.py` |
| `/api/v1/docs` | OpenAPI 문서 (개발 환경만) | FastAPI 기본 |
| `/api/v1/redoc` | ReDoc 문서 (개발 환경만) | FastAPI 기본 |

보호 경로(process, watch, agent, gateway, events, users)는 `Depends(get_current_user)` 적용. 속도 제한 미들웨어는 미구현(선택).

### 2.3 SSE/WebSocket 경로

| 경로 | 프로토콜 | 설명 | 인증 |
|------|---------|------|------|
| `/api/v1/events/stream` | SSE | 범용 이벤트 스트림 | JWT (쿼리 파라미터) |
| `/api/v1/watches/stream` | SSE | 알림 스트림 | JWT (쿼리 파라미터) |
| `/api/v1/agents/ws` | WebSocket | 에이전트 실시간 통신 | JWT (초기 핸드셰이크) |
| `/api/v1/workers/progress` | SSE | 워커 진행률 | JWT (쿼리 파라미터) |
| `/api/v1/process-mining/stream` | SSE | 프로세스 마이닝 결과 실시간 스트림 | JWT (쿼리 파라미터) |

---

## 3. 미들웨어 체인

### 3.1 요청 처리 순서

```
들어오는 요청 (HTTP)
     |
     v
[1. CORS 미들웨어]
     | - Origin 검증
     | - Preflight(OPTIONS) 자동 응답
     v
[2. 요청 로깅 미들웨어]
     | - Request ID 생성 (X-Request-Id)
     | - 시작 시간 기록
     v
[3. 속도 제한 미들웨어]
     | - IP + User 기반 Rate Limiting
     | - 429 Too Many Requests 반환
     v
[4. JWT 인증 미들웨어]
     | - Authorization: Bearer <token> 추출
     | - 공개 경로는 건너뜀
     | - 토큰 검증 실패 시 401 반환
     v
[5. 멀티테넌트 미들웨어]
     | - X-Forwarded-Host 또는 X-Tenant-Id 헤더에서 테넌트 식별
     | - ContextVar에 tenant_id 설정
     v
[6. RBAC 미들웨어]
     | - 경로별 필요 권한 확인
     | - 권한 부족 시 403 반환
     v
[Router Handler]
     |
     v
[7. 응답 로깅 미들웨어]
     | - 응답 시간 기록
     | - 응답 상태 코드 로깅
     v
클라이언트로 응답 반환
```

### 3.2 구현 코드

```python
# app/core/middleware.py

from contextvars import ContextVar
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import time

# ContextVar: 요청 스코프 테넌트 ID
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")

def get_current_tenant_id() -> str:
    return _tenant_id.get()

def get_current_request_id() -> str:
    return _request_id.get()

class TenantMiddleware(BaseHTTPMiddleware):
    """멀티테넌트 식별 미들웨어
    K-AIR의 DBConfigMiddleware에서 이식.
    X-Forwarded-Host 헤더로 테넌트를 결정한다.
    """
    async def dispatch(self, request: Request, call_next):
        # 1. 테넌트 식별
        tenant_id = (
            request.headers.get("X-Tenant-Id") or
            request.headers.get("X-Forwarded-Host", "").split(".")[0] or
            "default"
        )

        # 2. ContextVar에 설정
        token = _tenant_id.set(tenant_id)

        try:
            response = await call_next(request)
            return response
        finally:
            _tenant_id.reset(token)

class RequestIdMiddleware(BaseHTTPMiddleware):
    """요청 ID 및 로깅 미들웨어"""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(
            "X-Request-Id", str(uuid.uuid4())
        )
        token = _request_id.set(request_id)
        start = time.time()

        try:
            response = await call_next(request)
            duration = time.time() - start
            response.headers["X-Request-Id"] = request_id
            response.headers["X-Response-Time"] = f"{duration:.3f}s"

            logger.info(
                f"{request.method} {request.url.path} "
                f"status={response.status_code} "
                f"duration={duration:.3f}s "
                f"tenant={get_current_tenant_id()}"
            )
            return response
        finally:
            _request_id.reset(token)
```

---

## 4. 속도 제한 정책

### 4.1 기본 정책

| 경로 패턴 | 제한 | 단위 | 근거 |
|----------|------|------|------|
| `/api/v1/auth/login` | 10 | 분당/IP | 브루트포스 방지 |
| `/api/v1/completion/**` | 30 | 분당/사용자 | LLM API 비용 제어 |
| `/api/v1/agents/**` | 20 | 분당/사용자 | 에이전트 남용 방지 |
| `/api/v1/**` (기본) | 100 | 분당/사용자 | 일반 API 보호 |

### 4.2 구현

```python
# app/core/rate_limiter.py

from fastapi import Request, HTTPException
from app.core.redis_client import get_redis

class RateLimiter:
    """Redis 기반 슬라이딩 윈도우 속도 제한"""

    RULES = {
        "/api/v1/auth/login": (10, 60),       # 10 req/min
        "/api/v1/completion/": (30, 60),       # 30 req/min
        "/api/v1/agents/": (20, 60),           # 20 req/min
        "default": (100, 60),                  # 100 req/min
    }

    @staticmethod
    async def check(request: Request):
        """속도 제한 확인 - 초과 시 429 반환"""
        path = request.url.path
        key_suffix = request.state.user_id if hasattr(request.state, "user_id") else request.client.host

        limit, window = RateLimiter._get_rule(path)
        redis_key = f"ratelimit:{path}:{key_suffix}"

        redis = await get_redis()
        current = await redis.incr(redis_key)
        if current == 1:
            await redis.expire(redis_key, window)

        if current > limit:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {limit} requests per {window}s.",
                headers={"Retry-After": str(window)}
            )
```

---

## 5. 에러 코드 체계

### 5.1 에러 응답 형식

```json
{
  "error": {
    "code": "CASE_NOT_FOUND",
    "message": "사건을 찾을 수 없습니다.",
    "details": {
      "case_id": "uuid"
    },
    "request_id": "uuid"
  }
}
```

### 5.2 에러 코드 카탈로그

| HTTP | 코드 | 설명 | 사용자 표시 |
|------|------|------|-----------|
| 400 | VALIDATION_ERROR | 요청 데이터 유효성 실패 | "입력 데이터를 확인해주세요" |
| 401 | AUTH_TOKEN_EXPIRED | JWT 토큰 만료 | "로그인이 만료되었습니다" |
| 401 | AUTH_TOKEN_INVALID | JWT 토큰 무효 | "인증에 실패했습니다" |
| 403 | PERMISSION_DENIED | 권한 부족 | "접근 권한이 없습니다" |
| 403 | TENANT_MISMATCH | 다른 테넌트 데이터 접근 시도 | "접근 권한이 없습니다" |
| 404 | CASE_NOT_FOUND | 사건 미발견 | "사건을 찾을 수 없습니다" |
| 404 | WORKITEM_NOT_FOUND | 워크아이템 미발견 | "작업을 찾을 수 없습니다" |
| 409 | WORKITEM_ALREADY_DONE | 이미 완료된 워크아이템 | "이미 완료된 작업입니다" |
| 422 | PROCESS_INVALID_STATE | 잘못된 프로세스 상태 전이 | "현재 상태에서 수행할 수 없습니다" |
| 429 | RATE_LIMIT_EXCEEDED | 속도 제한 초과 | "요청이 너무 많습니다" |
| 500 | INTERNAL_ERROR | 내부 오류 | "시스템 오류가 발생했습니다" |
| 502 | EXTERNAL_SERVICE_ERROR | 외부 서비스 오류 (LLM 등) | "외부 서비스에 문제가 있습니다" |
| 504 | GATEWAY_TIMEOUT | 프록시 타임아웃 | "응답 시간이 초과되었습니다" |
| 503 | `SERVICE_CIRCUIT_OPEN` | 대상 서비스의 Circuit Breaker가 OPEN 상태 | "서비스가 일시적으로 사용 불가능합니다. 잠시 후 다시 시도해 주세요." |
| 503 | `SERVICE_DEGRADED` | 서비스 열화 모드 | "일부 기능을 사용할 수 없습니다." |

---

## 6. CORS 정책

```python
# app/main.py

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.axiom.ai",             # 프로덕션
        "https://*.axiom.ai",               # 서브도메인 (테넌트별)
        "http://localhost:3000",             # 개발 환경
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id", "X-Request-Id"],
    expose_headers=["X-Request-Id", "X-Response-Time"],
)
```

```
[금지] allow_origins=["*"] 사용 금지 (K-AIR의 기술 부채)
[필수] 프로덕션에서는 도메인을 명시적으로 지정한다.
```

---

## 7. 이벤트 로그 수집 및 프로세스 마이닝 라우팅

### 7.1 이 섹션이 답하는 질문

- 이벤트 로그를 어떻게 업로드하는가?
- 프로세스 마이닝 API는 어떤 경로로 라우팅되는가?
- 파일 업로드 크기 제한과 지원 형식은 무엇인가?

### 7.2 이벤트 로그 수집 API (`/api/v1/event-logs/*`)

이벤트 로그 수집 요청은 Core에서 검증/파싱 후 Synapse로 라우팅한다.

| 메서드 | 경로 | 설명 | Content-Type | 상태 | 근거(구현/티켓) |
|--------|------|------|-------------|------|------------------|
| POST | `/api/v1/event-logs/upload` | XES/CSV 파일 업로드 | `multipart/form-data` | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/event-logs/db-connect` | DB 연결로 이벤트 로그 수집 | `application/json` | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/event-logs` | 수집된 이벤트 로그 목록 조회 | - | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/event-logs/{log_id}` | 이벤트 로그 상세 조회 | - | Implemented | `services/core/app/api/gateway/routes.py` |
| DELETE | `/api/v1/event-logs/{log_id}` | 이벤트 로그 삭제 | - | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/event-logs/{log_id}/preview` | 이벤트 로그 미리보기 (상위 100건) | - | Implemented | `services/core/app/api/gateway/routes.py` |
| PUT | `/api/v1/event-logs/{log_id}/column-mapping` | CSV 컬럼 매핑 설정/수정 | `application/json` | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/event-logs/{log_id}/refresh` | 이벤트 로그 재수집/갱신 트리거 | `application/json` | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/event-logs/export-bpm` | BPM 실행 이력을 이벤트 로그로 내보내기 | `application/json` | Implemented | `services/core/app/api/gateway/routes.py` |

#### 파일 업로드 요청/응답 예시

```
POST /api/v1/event-logs/upload
Content-Type: multipart/form-data
Authorization: Bearer <jwt-token>

--boundary
Content-Disposition: form-data; name="file"; filename="purchase_log.xes"
Content-Type: application/xml

<XES 파일 내용>
--boundary
Content-Disposition: form-data; name="name"

구매 프로세스 이벤트 로그
--boundary
Content-Disposition: form-data; name="description"

2025년 구매 프로세스 실행 이력
--boundary--
```

```json
// 응답 (202 Accepted)
{
  "event_log_id": "uuid",
  "status": "INGESTING",
  "file_name": "purchase_log.xes",
  "format": "XES",
  "file_size_bytes": 5242880,
  "message": "이벤트 로그 수집이 시작되었습니다. SSE 스트림으로 진행 상황을 확인할 수 있습니다."
}
```

#### DB 연결 요청 예시

```json
// POST /api/v1/event-logs/db-connect
{
  "name": "ERP 구매 프로세스 로그",
  "connection": {
    "type": "postgresql",
    "host": "erp-db.internal",
    "port": 5432,
    "database": "erp_prod",
    "schema": "process_log",
    "username": "readonly_user"
    // password는 Vault/Secrets Manager 참조
  },
  "query": {
    "table": "purchase_events",
    "case_id_column": "order_id",
    "activity_column": "step_name",
    "timestamp_column": "completed_at",
    "resource_column": "handler_name",
    "filters": {
      "date_from": "2025-01-01",
      "date_to": "2025-12-31"
    }
  }
}
```

#### 파일 업로드 제한

```
[결정] 단일 파일 최대 크기: 500MB
[결정] 지원 형식: XES (.xes, .xes.gz), CSV (.csv, .csv.gz)
[결정] CSV 업로드 시 컬럼 매핑 필수: case_id, activity, timestamp
[결정] 500MB 초과 파일은 EventLogWorker가 청킹하여 스트리밍 처리

[금지] 파일 내용을 메모리에 전체 로드하지 않는다 (스트리밍 파싱).
[필수] 업로드 완료 후 비동기 처리 (202 Accepted 즉시 반환).
[필수] 진행 상황은 Redis Streams를 통해 SSE로 실시간 전달.
```

### 7.3 프로세스 마이닝 API (`/api/v1/process-mining/*`)

프로세스 마이닝 요청은 Synapse로 직접 프록시한다.

| 메서드 | 경로 | 설명 | 타임아웃 | 상태 | 근거(구현/티켓) |
|--------|------|------|---------|------|------------------|
| POST | `/api/v1/process-mining/discover` | 프로세스 모델 발견 | 180s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/process-mining/conformance` | 적합성 검사 | 180s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/process-mining/bottlenecks` | 병목 분석 태스크 시작 (`202 Accepted`) | 180s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/process-mining/performance` | 성능 분석 태스크 시작 (`202 Accepted`) | 180s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/process-mining/variants` | 프로세스 변형(Variant) 목록 조회 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/process-mining/bottlenecks` | 병목 분석 결과 조회 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/process-mining/tasks/{task_id}` | 비동기 작업 폴링 (마이닝 태스크 상태) | 30s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/process-mining/tasks/{task_id}/result` | 비동기 작업 결과 조회 | 30s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/process-mining/results/{result_id}` | 마이닝 결과 조회 | 30s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/process-mining/statistics/{log_id}` | 이벤트 로그 기본 통계 조회 | 30s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/process-mining/bpmn/export` | 발견 모델을 BPMN으로 내보내기 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/process-mining/import-model` | 발견 모델을 BPM에 임포트 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |

> **참고**: `/api/v1/process-mining/bottlenecks`와 `/api/v1/process-mining/performance`는 서로 다른 분석 태스크를 생성한다. 두 경로 모두 `202 Accepted`를 반환하며, 결과는 `/tasks/{task_id}` 폴링으로 조회한다.

### 7.3.1 문서 추출 API (`/api/v1/extraction/*`)

문서 추출 요청은 Synapse `/api/v3/synapse/extraction/*`로 프록시한다.

| 메서드 | 경로 | 설명 | 타임아웃 | 상태 | 근거(구현/티켓) |
|--------|------|------|---------|------|------------------|
| POST | `/api/v1/extraction/documents/{doc_id}/extract-ontology` | 비동기 추출 작업 시작 | 180s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/extraction/documents/{doc_id}/ontology-status` | 추출 진행 상태 조회 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/extraction/documents/{doc_id}/ontology-result` | 추출 결과 조회 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| PUT | `/api/v1/extraction/ontology/{entity_id}/confirm` | HITL 개별 확정 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/extraction/cases/{case_id}/ontology/review` | HITL 일괄 검토 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| GET | `/api/v1/extraction/cases/{case_id}/review-queue` | HITL 검토 대기열 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/extraction/documents/{doc_id}/retry` | 추출 재시도 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |
| POST | `/api/v1/extraction/documents/{doc_id}/revert-extraction` | Saga 보상 롤백 | 60s | Implemented | `services/core/app/api/gateway/routes.py` |

### 7.3.2 그래프 검색 API (`/api/v1/graph/*`)

그래프 검색 요청은 Synapse `/api/v3/synapse/graph/*`로 프록시한다.

| 메서드 | 경로 | 대상 Synapse 경로 | 타임아웃 | 상태 |
|--------|------|-------------------|---------|------|
| POST | `/api/v1/graph/search` | `/api/v3/synapse/graph/search` | 180s | Implemented |
| POST | `/api/v1/graph/vector-search` | `/api/v3/synapse/graph/vector-search` | 180s | Implemented |
| POST | `/api/v1/graph/fk-path` | `/api/v3/synapse/graph/fk-path` | 180s | Implemented |
| POST | `/api/v1/graph/ontology-path` | `/api/v3/synapse/graph/ontology-path` | 180s | Implemented |
| GET | `/api/v1/graph/tables/{table_name}/related` | `/api/v3/synapse/graph/tables/{table_name}/related` | 60s | Implemented |
| GET | `/api/v1/graph/stats` | `/api/v3/synapse/graph/stats` | 60s | Implemented |

요청 예시:

```json
// POST /api/v1/graph/search
{
  "query": "프로세스 효율성",
  "case_id": "case-live-1",
  "options": {
    "vector_search": {"enabled": true, "table_top_k": 5, "min_score": 0.7},
    "fk_traversal": {"enabled": true, "max_hops": 3}
  }
}
```

응답 예시:

```json
{
  "success": true,
  "data": {
    "query": "프로세스 효율성",
    "tables": {
      "vector_matched": [],
      "fk_related": []
    }
  }
}
```

### 7.3.3 스키마 편집 API (`/api/v1/schema-edit/*`)

스키마 편집 요청은 Synapse `/api/v3/synapse/schema-edit/*`로 프록시한다.

| 메서드 | 경로 | 대상 Synapse 경로 | 타임아웃 | 상태 |
|--------|------|-------------------|---------|------|
| GET | `/api/v1/schema-edit/tables` | `/api/v3/synapse/schema-edit/tables` | 180s | Implemented |
| GET | `/api/v1/schema-edit/tables/{table_name}` | `/api/v3/synapse/schema-edit/tables/{table_name}` | 180s | Implemented |
| PUT | `/api/v1/schema-edit/tables/{table_name}/description` | `/api/v3/synapse/schema-edit/tables/{table_name}/description` | 180s | Implemented |
| PUT | `/api/v1/schema-edit/columns/{table_name}/{column_name}/description` | `/api/v3/synapse/schema-edit/columns/{table_name}/{column_name}/description` | 180s | Implemented |
| GET | `/api/v1/schema-edit/relationships` | `/api/v3/synapse/schema-edit/relationships` | 180s | Implemented |
| POST | `/api/v1/schema-edit/relationships` | `/api/v3/synapse/schema-edit/relationships` | 180s | Implemented |
| DELETE | `/api/v1/schema-edit/relationships/{rel_id}` | `/api/v3/synapse/schema-edit/relationships/{rel_id}` | 180s | Implemented |
| POST | `/api/v1/schema-edit/tables/{table_name}/embedding` | `/api/v3/synapse/schema-edit/tables/{table_name}/embedding` | 180s | Implemented |
| POST | `/api/v1/schema-edit/batch-update-embeddings` | `/api/v3/synapse/schema-edit/batch-update-embeddings` | 180s | Implemented |

### 7.3.4 온톨로지 API (`/api/v1/ontology/*`)

온톨로지 요청은 Synapse `/api/v3/synapse/ontology/*`로 프록시한다.

| 메서드 | 경로 | 대상 Synapse 경로 | 타임아웃 | 상태 |
|--------|------|-------------------|---------|------|
| GET | `/api/v1/ontology` | `/api/v3/synapse/ontology/` | 180s | Implemented |
| POST | `/api/v1/ontology/extract-ontology` | `/api/v3/synapse/ontology/extract-ontology` | 180s | Implemented |
| GET | `/api/v1/ontology/cases/{case_id}/ontology` | `/api/v3/synapse/ontology/cases/{case_id}/ontology` | 180s | Implemented |
| GET | `/api/v1/ontology/cases/{case_id}/ontology/summary` | `/api/v3/synapse/ontology/cases/{case_id}/ontology/summary` | 180s | Implemented |
| GET | `/api/v1/ontology/cases/{case_id}/ontology/{layer}` | `/api/v3/synapse/ontology/cases/{case_id}/ontology/{layer}` | 180s | Implemented |
| POST | `/api/v1/ontology/nodes` | `/api/v3/synapse/ontology/nodes` | 180s | Implemented |
| GET | `/api/v1/ontology/nodes/{node_id}` | `/api/v3/synapse/ontology/nodes/{node_id}` | 180s | Implemented |
| PUT | `/api/v1/ontology/nodes/{node_id}` | `/api/v3/synapse/ontology/nodes/{node_id}` | 180s | Implemented |
| DELETE | `/api/v1/ontology/nodes/{node_id}` | `/api/v3/synapse/ontology/nodes/{node_id}` | 180s | Implemented |
| POST | `/api/v1/ontology/relations` | `/api/v3/synapse/ontology/relations` | 180s | Implemented |
| DELETE | `/api/v1/ontology/relations/{relation_id}` | `/api/v3/synapse/ontology/relations/{relation_id}` | 180s | Implemented |
| GET | `/api/v1/ontology/nodes/{node_id}/neighbors` | `/api/v3/synapse/ontology/nodes/{node_id}/neighbors` | 180s | Implemented |
| GET | `/api/v1/ontology/nodes/{node_id}/path-to/{target_id}` | `/api/v3/synapse/ontology/nodes/{node_id}/path-to/{target_id}` | 180s | Implemented |

요청 예시:

```json
// POST /api/v1/ontology/nodes
{
  "id": "node-uuid-001",
  "case_id": "case-live-1",
  "layer": "resource",
  "labels": ["Company"],
  "properties": {
    "name": "ACME",
    "verified": true
  }
}
```

응답 예시:

```json
{
  "success": true,
  "data": {
    "id": "node-uuid-001",
    "case_id": "case-live-1",
    "layer": "resource",
    "labels": ["Company"],
    "properties": {"name": "ACME", "verified": true}
  }
}
```

#### 프로세스 마이닝 SSE 이벤트 유형

| SSE 이벤트 | 설명 | 데이터 |
|-----------|------|--------|
| `mining:progress` | 마이닝 진행률 업데이트 | `{"event_log_id": "uuid", "step": "discovering", "progress": 45}` |
| `mining:discovered` | 프로세스 모델 발견 완료 | `{"event_log_id": "uuid", "bpmn_url": "...", "fitness": 0.92}` |
| `mining:conformance` | 적합성 검사 완료 | `{"event_log_id": "uuid", "fitness": 0.89, "deviations_count": 15}` |
| `mining:bottleneck` | 병목 감지 | `{"event_log_id": "uuid", "bottlenecks": [...]}` |
| `mining:error` | 마이닝 오류 | `{"event_log_id": "uuid", "error": "..."}` |

### 7.4 에러 코드 (이벤트 로그/프로세스 마이닝/그래프/온톨로지)

| HTTP | 코드 | 설명 | 사용자 표시 |
|------|------|------|-----------|
| 400 | INVALID_EVENT_LOG_FORMAT | XES/CSV 형식 검증 실패 | "이벤트 로그 형식이 올바르지 않습니다" |
| 400 | MISSING_REQUIRED_COLUMNS | CSV 필수 컬럼 누락 | "case_id, activity, timestamp 컬럼이 필요합니다" |
| 413 | FILE_TOO_LARGE | 파일 크기 초과 (500MB) | "파일 크기가 제한을 초과합니다" |
| 422 | INSUFFICIENT_CASES | 마이닝에 필요한 최소 케이스 수 미달 | "최소 10개 이상의 케이스가 필요합니다" |
| 400 | INVALID_GRAPH_QUERY | 그래프 검색 요청 파라미터 오류 | "검색 요청을 확인해주세요" |
| 400 | INVALID_ONTOLOGY_PAYLOAD | 온톨로지 요청 본문 검증 실패 | "온톨로지 요청 형식을 확인해주세요" |
| 404 | ONTOLOGY_NODE_NOT_FOUND | 온톨로지 노드를 찾을 수 없음 | "온톨로지 노드를 찾을 수 없습니다" |
| 404 | GRAPH_TABLE_NOT_FOUND | FK 탐색 시작 테이블 없음 | "시작 테이블을 찾을 수 없습니다" |
| 502 | SYNAPSE_MINING_ERROR | Synapse 프로세스 마이닝 실행 오류 | "프로세스 마이닝 중 오류가 발생했습니다" |

### 7.5 속도 제한 (이벤트 로그/프로세스 마이닝)

| 경로 패턴 | 제한 | 단위 | 근거 |
|----------|------|------|------|
| `/api/v1/event-logs/upload` | 5 | 분당/사용자 | 대용량 파일 업로드 리소스 보호 |
| `/api/v1/process-mining/**` | 10 | 분당/사용자 | Synapse 컴퓨팅 리소스 보호 |
| `/api/v1/graph/**` | 30 | 분당/사용자 | 그래프 검색 남용 방지 |
| `/api/v1/ontology/**` | 20 | 분당/사용자 | 온톨로지 변경 API 보호 |

<!-- affects: frontend, backend, llm -->
<!-- requires-update: 04_frontend/process-mining-ui.md, 03_backend/worker-system.md -->

---

## 근거

- K-AIR 역설계 보고서 섹션 15.3 (process-gpt-completion API)
- process-gpt-gs-main/gateway 소스코드 (ForwardHostHeaderFilter.java, application.yml)
- ADR-001: FastAPI 선택 (Spring Boot Gateway 대체)
