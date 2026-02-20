# Axiom Core - 동시성 정책과 멀티테넌트

## 이 문서가 답하는 질문

- ContextVar 기반 멀티테넌트는 어떻게 동작하는가?
- 비동기(async) 환경에서 요청 격리는 어떻게 보장되는가?
- 동시 요청, 동시 워커 실행 시 데이터 일관성은 어떻게 유지하는가?

<!-- affects: backend, security -->
<!-- requires-update: 07_security/data-isolation.md -->

---

## 1. ContextVar 멀티테넌트

### 1.1 설계 근거

```
[사실] K-AIR의 process-gpt-completion-main은 ContextVar로 멀티테넌트를 구현한다.
[결정] Axiom은 이 패턴을 그대로 이식한다.
[근거] Python asyncio 환경에서 ContextVar는 Task(코루틴) 단위로 격리된다.
       쓰레드 기반의 ThreadLocal과 달리 비동기 코루틴 간 안전하게 격리된다.
       FastAPI의 각 요청은 별도 asyncio Task이므로, 요청 간 테넌트 격리가 보장된다.
```

### 1.2 동작 원리

```python
# app/core/middleware.py

from contextvars import ContextVar

# 요청 스코프 변수들
_tenant_id: ContextVar[str] = ContextVar("tenant_id", default="")
_user_id: ContextVar[str] = ContextVar("user_id", default="")
_request_id: ContextVar[str] = ContextVar("request_id", default="")

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # X-Forwarded-Host에서 테넌트 식별 (K-AIR 패턴 이식)
        tenant_id = extract_tenant_id(request)

        # ContextVar 설정
        token = _tenant_id.set(tenant_id)

        try:
            response = await call_next(request)
            return response
        finally:
            # 요청 완료 후 반드시 리셋
            _tenant_id.reset(token)
```

### 1.3 격리 보장 범위

```
ContextVar 격리:
  + 같은 요청 내 모든 코루틴에서 동일한 tenant_id 참조
  + 다른 요청의 코루틴과 완전히 격리
  + Service -> Repository -> EventPublisher 체인에서 일관된 tenant_id

ContextVar가 보장하지 않는 것:
  - DB 레벨 격리 (RLS 정책으로 보완)
  - Worker 프로세스 간 격리 (Worker는 이벤트에 tenant_id를 명시적으로 포함)
  - Redis 키 격리 (키 접두어에 tenant_id를 포함)
```

---

## 2. DB 접근 동시성

### 2.1 Connection Pool 관리

```python
# app/core/database.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,           # 기본 연결 수
    max_overflow=80,        # 최대 추가 연결 (총 100)
    pool_timeout=30,        # 연결 대기 타임아웃
    pool_recycle=3600,      # 1시간마다 연결 재생성 (PostgreSQL idle timeout 대응)
    pool_pre_ping=True,     # 사용 전 연결 유효성 검사
)
```

### 2.2 RLS + ContextVar 이중 격리

```sql
-- PostgreSQL RLS 정책
CREATE POLICY tenant_isolation ON cases
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- 세션 시작 시 tenant_id 설정
SET app.current_tenant_id = 'tenant-uuid';
```

```python
# app/core/database.py

@asynccontextmanager
async def get_session():
    async with async_session_factory() as session:
        # RLS를 위한 세션 변수 설정 (파라미터 바인딩 사용)
        tenant_id = get_current_tenant_id()
        await session.execute(
            text("SET app.current_tenant_id = :tenant_id"),
            {"tenant_id": str(tenant_id)},
        )
        yield session
```

---

## 3. Worker 동시성

### 3.1 Worker 간 작업 분배

```
[결정] Redis Streams Consumer Group으로 Worker 간 작업을 분배한다.
[근거] 여러 Worker 인스턴스가 같은 스트림을 소비할 때, Consumer Group이
       메시지를 자동으로 분배하여 중복 처리를 방지한다.

Worker A: XREADGROUP ... "axiom:workers" ">" --> 메시지 1, 3, 5
Worker B: XREADGROUP ... "axiom:workers" ">" --> 메시지 2, 4, 6
```

### 3.2 Worker 멱등성 보장

```python
# app/workers/base.py

class BaseWorker:
    async def process_message(self, message_id: str, data: dict):
        """멱등성 보장 래퍼"""
        redis = await get_redis()

        # 중복 처리 체크
        dedup_key = f"processed:{message_id}"
        if await redis.exists(dedup_key):
            logger.info(f"Skipping duplicate message: {message_id}")
            return

        # 처리
        await self._handle(data)

        # 처리 완료 표시 (7일 TTL)
        await redis.set(dedup_key, "1", ex=7 * 86400)
```

---

## 4. 동시성 규칙 요약

```
[필수] 모든 DB 세션은 RLS용 tenant_id를 설정한 후 사용한다.
[필수] ContextVar는 미들웨어에서만 set/reset한다 (다른 곳에서 변경 금지).
[필수] Worker는 멱등성을 보장한다 (같은 메시지 2번 처리해도 결과 동일).
[필수] Connection Pool 설정은 예상 동시 요청 수의 2배 이상으로 설정한다.
[금지] 글로벌 변수에 요청별 상태 저장 (ContextVar 사용).
[금지] Worker에서 ContextVar 직접 참조 (이벤트 데이터에서 tenant_id 추출).
```

---

## 근거

- K-AIR process-gpt-completion-main (DBConfigMiddleware, ContextVar 패턴)
- ADR-003: ContextVar 기반 멀티테넌트
- 07_security/data-isolation.md (RLS 정책)
- [08_operations/performance-monitoring.md](../08_operations/performance-monitoring.md) (Connection Pool 모니터링, DB 쿼리 지연 메트릭, 용량 계획)
