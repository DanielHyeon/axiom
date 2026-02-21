# Weaver - 데이터 접근 제어 및 요청 보호

> **최종 수정일**: 2026-02-21
> **상태**: Implemented
> **근거 코드**: `app/core/auth.py`, `app/services/request_guard.py`, `app/main.py`

## 1. 인증 및 권한

### 1.1 인증

- 모든 보호 API는 `Authorization` 헤더를 사용한다.
- `Authorization: Bearer <jwt>` 형식을 강제한다.
- JWT는 `JWT_SECRET_KEY`, `JWT_ALGORITHM`으로 검증한다.
- 필수 claim: `sub`, `tenant_id`, `role`.
- 검증 실패 시 `401`을 반환한다.

### 1.2 권한 단위

- `datasource:read`
- `datasource:write`
- `query:read`
- `query:execute`
- `metadata:read`
- `metadata:write`
- `metadata:admin`

### 1.3 역할 매핑 (현재 구현)

| 역할 | 권한 |
|------|------|
| `admin` | 전체 권한 |
| `staff` | `datasource:read/write`, `query:read/execute`, `metadata:read/write` |
| `analyst` | `datasource:read`, `query:read/execute`, `metadata:read` |
| `viewer` | `datasource:read`, `query:read/execute`, `metadata:read` |

`metadata:admin`은 `admin`만 가진다.

## 2. 요청 보호

### 2.1 Request ID

- 전역 미들웨어가 모든 요청에 `X-Request-Id`를 보장한다.
- 클라이언트가 `X-Request-Id`를 보내면 그대로 사용한다.
- 없으면 서버가 `req-<uuid>` 형식으로 생성하고 응답 헤더에 반환한다.
- 감사 로그 이벤트는 이 값을 `request_id`로 기록한다.

### 2.2 Rate Limit

- 기본은 메모리 제한기, `WEAVER_REQUEST_GUARD_REDIS_MODE=true` 시 Redis 제한기 사용.
- 키: `user_id + path + operation`.
- 기본 정책:
- 데이터소스/메타데이터 write: 분당 60회.
- 쿼리 실행: 분당 120회.
- 초과 시 `429`와 `detail.code=RATE_LIMITED` 반환.

### 2.3 Idempotency

- write API는 `Idempotency-Key`를 지원한다.
- 첫 요청은 키를 `in_progress`로 예약(reserve)한다.
- 동일 키 + 동일 payload면 이전 응답을 재사용한다.
- 동일 키 + 다른 payload면 `409`와 `detail.code=IDEMPOTENCY_KEY_REUSE_MISMATCH`.
- 동일 키가 아직 처리 중이면 `409`와 `detail.code=IDEMPOTENCY_IN_PROGRESS`.
- TTL 기본 600초 (`WEAVER_REQUEST_GUARD_IDEMPOTENCY_TTL_SECONDS`로 조정 가능).

## 3. 민감정보 및 감사

- 데이터소스 응답에서 `connection.password`는 항상 제거한다.
- write 이벤트는 `audit_log_service.emit()`으로 감사 로그를 남긴다.
- 표준 필드: `action`, `actor_id`, `tenant_id`, `resource_type`, `resource_id`, `request_id`, `duration_ms`.

## 4. 테넌트 격리

- In-memory 저장소 키는 tenant 스코프를 포함한다.
- Metadata(Postgres/Neo4j) 저장소 연산은 `tenant_id` 필터를 강제한다.
- 동일한 `case_id`/`datasource`/`term_id` 값이 다른 테넌트에 존재해도 교차 조회/수정되지 않는다.
- `Idempotency-Key`는 내부적으로 `tenant_id` prefix를 사용해 테넌트 간 충돌을 차단한다.

## 5. 외부 의존성 에러 형식

MindsDB/Neo4j/Postgres 연동 에러는 다음 형식을 사용한다.

```json
{
  "detail": {
    "code": "MINDSDB_UNAVAILABLE",
    "service": "mindsdb",
    "message": "connection refused"
  }
}
```

## 6. 구현 한계 (현재 버전)

- Redis 모드 비활성화 시 Rate limit / idempotency 저장소는 프로세스 메모리 기반이다.
- 다중 인스턴스 환경에서는 공통 저장소(Redis 등)로 치환이 필요하다.
- Redis 모드 활성화 시 Redis 장애가 발생하면 서버는 경고 로그 후 메모리 모드로 폴백한다.

## 7. 관측 지표

- `GET /metrics` (Prometheus text format) 제공
- 주요 카운터:
- `weaver_request_guard_rate_limited_total`
- `weaver_request_guard_idempotency_in_progress_total`
- `weaver_request_guard_idempotency_mismatch_total`
- 라벨:
- `mode`: `memory` 또는 `redis`
- `endpoint`: 요청 경로 (idempotency 키에서 추출 불가 시 `unknown`)
- `operation`: rate limit 이벤트의 동작 타입 (`read`/`write`/`execute`)
