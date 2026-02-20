# ADR-003: ContextVar 기반 멀티테넌트 격리

## 상태

Accepted

## 배경

K-AIR/Process-GPT 시스템은 멀티테넌트 데이터 격리를 위해 **ContextVar + RLS 조합**을 사용한다. 이 패턴은 `process-gpt-completion-main`의 `DBConfigMiddleware`에서 확인할 수 있다.

**K-AIR 현행 구조**:

```python
# process-gpt-completion-main/main.py - DBConfigMiddleware

class DBConfigMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # X-Forwarded-Host 헤더로 테넌트 결정
        forwarded_host = request.headers.get("x-forwarded-host", "")
        # 테넌트 DB 설정을 ContextVar에 저장
        db_config_var.set(tenant_config)
        response = await call_next(request)
        return response
```

**문제**:
1. Axiom은 FastAPI 단일 서비스로 통합하므로, Spring Gateway의 `ForwardHostHeaderFilter`가 없다.
2. 테넌트 식별 방법을 재설계해야 한다 (호스트 헤더 → JWT 페이로드).
3. Worker(백그라운드 작업)에서는 HTTP 요청이 없으므로 ContextVar 설정 방법이 달라야 한다.
4. Redis 캐시에서도 테넌트 격리가 필요하다.

## 검토한 옵션

### 옵션 1: 데이터베이스 분리 (Database per Tenant)

**장점**:
- 물리적 격리로 보안 최상
- 테넌트별 독립 백업/복원
- 테넌트별 성능 격리

**단점**:
- 테넌트 수가 늘어나면 DB 인스턴스 관리 비용 급증
- 스키마 마이그레이션을 모든 DB에 개별 적용해야 함
- 커넥션 풀이 테넌트 수에 비례하여 증가
- 비즈니스 프로세스 인텔리전스 도메인 특성상 테넌트 수가 분석 조직/컨설팅 조직 수로 제한적이지만, 각 테넌트의 데이터량이 크지 않아 DB 분리는 과도함

### 옵션 2: 스키마 분리 (Schema per Tenant)

**장점**:
- 단일 DB 인스턴스에서 논리적 격리
- 테넌트별 스키마로 데이터 분리
- pg_dump로 테넌트별 백업 가능

**단점**:
- 마이그레이션 복잡도 (모든 스키마에 적용)
- ORM 설정이 복잡해짐 (동적 스키마 전환)
- 크로스 테넌트 쿼리(admin용)가 어려움
- PostgreSQL search_path 동적 변경의 보안 위험

### 옵션 3: ContextVar + RLS (선택)

**장점**:
- 단일 DB, 단일 스키마로 관리 단순
- PostgreSQL RLS 정책으로 DB 레벨 강제 격리
- Python ContextVar로 요청 스코프 격리 (asyncio 안전)
- K-AIR에서 검증된 패턴 (이식 용이)
- 크로스 테넌트 쿼리(admin)를 별도 DB 역할로 지원
- 마이그레이션이 한 번만 실행됨

**단점**:
- 개발자가 ContextVar 설정을 잊으면 데이터 노출 위험 → RLS로 방어
- 테넌트별 성능 격리가 어려움 → 쿼리 타임아웃 + Rate Limiting으로 보완
- 테넌트 데이터량 극단적 차이 시 인덱스 효율 저하 가능

## 선택한 결정

**옵션 3: ContextVar + RLS 기반 멀티테넌트 격리**

K-AIR의 `DBConfigMiddleware` 패턴을 계승하되, 테넌트 식별을 `X-Forwarded-Host`에서 **JWT 페이로드의 `tenant_id`**로 변경한다.

## 근거

### 1. 4중 격리 모델

```
Layer 1: JWT 검증
  → 토큰에 tenant_id 포함, 서명 검증으로 위조 방지
  → 인증 실패 시 401 반환 (1차 차단)

Layer 2: ContextVar 설정
  → 미들웨어에서 JWT의 tenant_id를 ContextVar에 저장
  → 요청 스코프 격리 (asyncio 태스크 간 간섭 없음)
  → 잘못된 테넌트 접근 방지 (2차 차단)

Layer 3: PostgreSQL RLS 정책
  → DB 세션 시작 시 SET app.current_tenant_id 실행
  → 모든 SELECT/INSERT/UPDATE/DELETE에 자동 필터링
  → 개발자 실수 방지 (3차 차단, 최종 방어선)

Layer 4: 명시적 WHERE 조건
  → ORM 쿼리에 tenant_id 조건 명시
  → 코드 가독성 + 디버깅 편의 (4차 차단)
```

어느 한 계층이 실패해도 다른 계층이 보호한다 (Defense-in-Depth).

### 2. K-AIR 대비 개선점

| 항목 | K-AIR | Axiom |
|------|-------|-------|
| 테넌트 식별 | X-Forwarded-Host (헤더 기반) | JWT payload의 tenant_id (토큰 기반) |
| 격리 레이어 | 2중 (ContextVar + RLS) | 4중 (JWT + ContextVar + RLS + WHERE) |
| Worker 지원 | 미고려 | 이벤트 데이터에서 tenant_id 추출 |
| Redis 격리 | 미고려 | 모든 키에 `{tenant_id}:` 접두어 |
| 테넌트 식별 보안 | 헤더 조작 가능 | JWT 서명 검증 (위조 불가) |

K-AIR에서 `X-Forwarded-Host` 헤더로 테넌트를 식별하는 방식은 프록시 설정 오류나 헤더 조작으로 다른 테넌트 데이터에 접근할 수 있는 위험이 있었다. JWT 페이로드 기반으로 변경하면 서명 검증을 통해 위조가 원천 차단된다.

### 3. 구현 상세

#### 3.1 미들웨어 (JWT → ContextVar)

```python
# app/core/middleware.py

from contextvars import ContextVar

tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")
user_id_var: ContextVar[str] = ContextVar("user_id", default="")

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # JWT에서 tenant_id 추출 (security.py에서 검증 완료)
        token_data = request.state.token_data  # JWT 미들웨어에서 설정

        # ContextVar 설정 (요청 스코프)
        tenant_id_var.set(token_data["tenant_id"])
        user_id_var.set(token_data["user_id"])

        response = await call_next(request)
        return response
```

#### 3.2 DB 세션에 RLS 변수 주입

```python
# app/core/database.py

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        tenant_id = tenant_id_var.get()
        if tenant_id:
            # RLS 정책용 세션 변수 설정 (파라미터 바인딩 사용)
            await session.execute(
                text("SET app.current_tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)},
            )
        yield session
```

#### 3.3 Worker에서의 ContextVar 설정

```python
# app/workers/base.py

class BaseWorker:
    async def process_event(self, event: dict):
        # 이벤트 데이터에서 tenant_id 추출
        tenant_id = event["tenant_id"]

        # Worker 컨텍스트에 tenant_id 설정
        tenant_id_var.set(tenant_id)

        # 이후 DB 접근 시 RLS 자동 적용
        async with get_session() as session:
            await self.handle(session, event)
```

#### 3.4 Redis 키 격리

```python
# app/core/cache.py

def cache_key(key: str) -> str:
    """모든 Redis 키에 tenant_id 접두어 추가"""
    tenant_id = tenant_id_var.get()
    if not tenant_id:
        raise ValueError("tenant_id not set in ContextVar")
    return f"{tenant_id}:{key}"
```

### 4. asyncio 안전성

Python `ContextVar`는 asyncio에서 태스크 간 격리를 보장한다:

```
요청 A (tenant: alpha)          요청 B (tenant: beta)
  │                                │
  ├─ tenant_id_var.set("alpha")    ├─ tenant_id_var.set("beta")
  ├─ await db_query()              ├─ await db_query()
  │   └─ SET app.current_tenant_id │   └─ SET app.current_tenant_id
  │      = 'alpha'                 │      = 'beta'
  ├─ 결과: alpha 데이터만 반환     ├─ 결과: beta 데이터만 반환
```

동일 이벤트 루프에서 동시 실행되더라도 ContextVar는 각 코루틴 태스크에 독립적이다.

### 5. 비즈니스 프로세스 인텔리전스 도메인 적합성

비즈니스 프로세스 데이터는 **엄격한 비밀유지 의무**가 있다. 한 분석 조직의 대상 조직 정보가 다른 분석 조직에 노출되면 심각한 문제가 발생한다. 4중 격리는 이 요구사항을 충족한다.

테넌트 수는 분석 조직/컨설팅 조직 수로 제한되어 수십~수백 수준이므로, 단일 DB + RLS로 충분하다. 데이터베이스 분리는 과도한 인프라 비용을 초래한다.

## 결과

### 긍정적 영향
- 4중 격리로 데이터 보안 최상 (비밀유지 의무 충족)
- K-AIR 검증 패턴 기반으로 구현 위험 최소
- 단일 DB/스키마로 운영 단순화
- Worker에서도 일관된 격리 보장

### 부정적 영향
- 모든 DB 테이블에 tenant_id 컬럼 추가 필요
- RLS 정책을 모든 테이블에 적용해야 함 (CI 자동 검사 도입)
- 테넌트별 성능 격리가 부재 (대규모 테넌트가 전체 성능에 영향 가능)

### 마이그레이션 작업
- `process-gpt-completion-main/DBConfigMiddleware` → `app/core/middleware.py`
  - X-Forwarded-Host → JWT tenant_id 방식으로 변경
- `process-gpt-main/init.sql` RLS 정책 → Alembic 마이그레이션으로 이식
- Redis 캐시 키 패턴 추가 (tenant_id 접두어)
- 예상 공수: 2일

## 재평가 조건

- 테넌트 수가 1,000개를 초과하는 경우 → 스키마 분리 검토
- 특정 테넌트의 데이터량이 전체의 50% 이상을 차지하는 경우 → 해당 테넌트 전용 DB 분리 검토
- 규제 요구로 물리적 데이터 격리가 필요한 경우 → Database per Tenant 검토
- 테넌트별 SLA가 다른 경우 → 성능 격리를 위한 DB 분리 검토
