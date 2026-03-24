# Axiom 크로스 프로젝트 도입 구현 계획서

> **작성일**: 2026-03-24
> **버전**: v2.0 (v1.4 보강본 피드백 전면 반영)
> **대상**: Axiom v5.2 (6개 마이크로서비스 + Canvas SPA)
> **참조**: Alparka v1.2.0, VibeSnack (6-microservice + Kafka)

---

## 1. 개요

Alparka와 VibeSnack 코드베이스를 세밀하게 분석한 결과,
Axiom에 도입할 가치가 있는 **총 25개 항목 + 6개 신규 플랫폼 기반 항목 = 31개 항목**을 식별했다.

- **Alparka 기원**: 18개 (보안, 프론트엔드, 인프라, 모니터링, 버전 관리)
- **VibeSnack 기원**: 7개 (Shared Library, Circuit Breaker, HMAC, SoftDelete, Token Blacklist, CI, Fail-Silent)
- **신규 플랫폼 기반**: 6개 (Request ID, Error Code, 서비스 CI, Health 표준화, Event Schema, Feature Flag)

본 문서는 이를 **Sprint 0~5 로드맵 (6개 Sprint)**으로 재구성한 실행 설계서다.

---

## 2. 도입 의사결정 원칙

본 계획의 모든 항목은 다음 원칙에 따라 채택 여부를 결정한다.

1. **서비스별 중복 구현보다 공통 기반화를 우선**한다.
2. **기능 추가보다 운영 안정성과 복구 가능성을 우선**한다.
3. **보안 정책은 일괄 강제보다 Report-Only/Feature Flag 기반 점진 전환을 우선**한다.
4. **관측 가능성이 없는 기능은 production 기본 활성화 대상으로 보지 않는다.**
5. **UI 시각화는 데이터 계약과 API가 안정화된 다음 도입**한다.
6. **다중 테넌트 경계, 감사 가능성, 롤백 가능성은 모든 설계의 공통 기준**으로 삼는다.

---

## 3. 버전 관리 비교 분석

### 3.1 Alparka: 파일 기반 델타 버전 관리

| 항목 | 설명 |
|------|------|
| **범위** | 앱 코드/스펙/에셋 파일 단위 |
| **저장** | EFS 파일 아카이브 + PostgreSQL 메타데이터 (JSONB) |
| **트리 구조** | `parent_id` FK → 브랜치 가능한 트리 |
| **델타** | SHA-256 해시 비교 → 변경/추가/삭제 파일만 아카이브 |
| **복원** | 3단계 폴백: 직접 복사 → no_changes 추적 → 조상 탐색 |
| **변경 추적** | `changes` JSONB: `[{type, path, name}]` |
| **동시성** | `SELECT ... FOR UPDATE` 행 잠금 |
| **폴백** | DB 실패 시 JSON 파일 기반 운영 |
| **UI** | SVG 인터랙티브 트리 그래프 (줌/팬/터치) |

### 3.2 Axiom: 시맨틱 스냅샷 불변성

| 항목 | 설명 |
|------|------|
| **범위** | 시맨틱 계약 계층 전체 (L2) |
| **저장** | PostgreSQL JSONB (스냅샷 헤더 + 4-part 아티팩트) |
| **구조** | `release_id` 선형 연결 (브랜치 없음) |
| **스냅샷** | 전체 물질화 (CONTRACT_INDEX, JOIN_GRAPH, CONTEXT_PACKS, SYNONYM_MAP) |
| **변경 추적** | content_hash (MD5) — 변경 목록 없음 |
| **동시성** | 낙관적 잠금 (30분 TTL 리스) |
| **폴백** | 없음 (DB 의존) |

### 3.3 도입할 4가지 버전 관리 패턴

| # | 패턴 | 가치 |
|---|------|------|
| V1 | **변경 목록 (changes JSONB)** | "이 스냅샷에서 뭐가 바뀌었는지" 즉시 확인 |
| V2 | **Object Storage 폴백** | DB 장애 시에도 마지막 스냅샷 서빙 |
| V3 | **릴리스 히스토리 시각화** | 릴리스 간 관계를 직관적 탐색 |
| V4 | **아티팩트 레벨 diff** | 두 스냅샷 간 정밀 비교 |

---

## 4. 도입 시 기대 효과

### 4.1 엔터프라이즈 보안 감사 대응

- OWASP 헤더 + CVE 스캔 + API 비노출 → 보안 감사 지적 **80% 감소**
- 토큰 즉시 무효화 + 이벤트 HMAC → 인시던트 대응 **0초**

### 4.2 무중단 배포 안정성

- `lazyWithRetry` → 배포 후 ChunkLoadError **0건/주**
- Docker Healthcheck (liveness/readiness 분리) → 비정상 컨테이너 **즉시 감지**
- Circuit Breaker → 단일 서비스 장애 **격리, 전파 차단**

### 4.3 운영 가시성

- 구조화 JSON 로그 → 장애 원인 특정 **30분→5분**
- Rate Limit 헤더 → NL2SQL 429 에러 **90% 감소**
- Prometheus 자동 계측 → SLA 위반 **실시간 감지**

### 4.4 시맨틱 거버넌스 강화

- 스냅샷 changes → 변경 검토 **10분→1분**
- Object Storage 폴백 → 가용성 **99.99%**
- SoftDelete → 삭제 자산 **30일 복구** 가능

### 4.5 코드 중복 제거

- Shared Library → 6개 서비스 공통 코드 **~2,000 LOC 제거**
- 보안 패치 **1회 적용, 6개 서비스 자동 반영**

### 4.6 최종 통합 ROI

| 영역 | 투자 | 기대 효과 |
|------|------|----------|
| 플랫폼 기반 | Sprint 0 (3~5일) | 공통 기반 확립, 이후 Sprint 비용 절감 |
| 보안 | Sprint 1 (3~5일) | 감사 통과 + 즉시 무효화 + 이벤트 무결성 |
| 운영/관측 | Sprint 2 (5~7일) | 장애 격리 + 구조화 로그 + 보안 스캔 |
| 품질 | Sprint 3 (5~7일) | E2E 2층 + AI 비용 추적 |
| 거버넌스 | Sprint 4 (5~10일) | 스냅샷 diff + SoftDelete + 감사 추적 |
| UX/고도화 | Sprint 5 (3~5일) | 시각화 + CI 최적화 + HMAC |
| **총 투자** | **~6 Sprint (24~39일)** | **엔터프라이즈 프로덕션 완전 준비** |

---

## 5. 전체 항목 + Sprint 로드맵 (31개, 6 Sprint)

### Sprint 0: 플랫폼 기반 정리 (선행 공통 과제)

| # | 항목 | 우선순위 | 설명 |
|---|------|---------|------|
| **VS-1** | Shared Library 골격 | P0 | `services/shared/` 패키지 — JWT, middleware, events, DB session 중앙화 |
| **N1** | 공통 Request ID | P0 | 전 서비스 Request-Id 미들웨어 + 응답 헤더 + 로그 연결 |
| **N2** | 공통 에러 코드 체계 | P0 | `AXIOM_XXXX` 에러 코드 → 프론트/백/운영 동일 분류 |
| **N3** | 서비스별 최소 CI | P0 | 6개 서비스 lint + test + build 파이프라인 |
| **N4** | Health 엔드포인트 표준화 | P1 | `/health/live`, `/health/ready` 분리 (liveness ≠ readiness) |

### Sprint 1: 보안/배포 안전망

| # | 항목 | 우선순위 | 설명 |
|---|------|---------|------|
| **S1-1** | Security Headers 미들웨어 | P0 | CSP Report-Only + connect-src + 에지 우선 적용 원칙 |
| **S1-2** | Lazy Loading + Retry | P0 | sessionStorage 플래그로 무한 reload 방지 |
| **S1-3** | Rate Limit 응답 헤더 | P1 | X-RateLimit-* + Retry-After (429 시) |
| **S1-5** | Production Docs 비활성화 | P1 | `ENVIRONMENT=production` 시 /docs, /redoc, /openapi.json 차단 |
| **VS-5** | Token Blacklist | P1 | Redis JTI 블랙리스트 + 사용자 레벨 일괄 무효화 |
| **N6** | Feature Flag / Kill Switch | P1 | CSP enforce, blacklist, breaker 등 고위험 항목 안전 롤아웃 |

### Sprint 2: 운영/관측/통합 안전망

| # | 항목 | 우선순위 | 설명 |
|---|------|---------|------|
| **S2-1** | 구조화 Access Log | P1 | JSON 로그 + 심각도 기반 레벨 + 민감정보 마스킹 |
| **S2-2** | Trivy 보안 스캔 (CI) | P1 | 버전 고정 (`@0.28.0`), pip-audit/npm audit 병행 |
| **S2-3** | Docker Healthcheck | P1 | liveness/readiness 분리, Nginx wget 존재 확인 |
| **VS-2** | Circuit Breaker | P1 | timeout → bounded retry → breaker → fallback cache 체계 |
| **VS-7** | Fail-Silent 이벤트 발행 | P2 | 3초 타임아웃 + try/except, Outbox 재발행 보장 |
| **N5** | Event Schema Versioning | P1 | 이벤트 스키마 버전 + idempotency key + DLQ/재처리 |

### Sprint 3: 테스트/품질

| # | 항목 | 우선순위 | 설명 |
|---|------|---------|------|
| **S2-4** | Error Boundary 강화 | P2 | Retry 버튼 + 에러 리포팅 엔드포인트 |
| **S3-1** | E2E 테스트 (2층) | P1 | Mock E2E (PR 검증) + Stage Smoke E2E (배포 전 실 연동) |
| **S3-2** | Prometheus 자동 계측 | P2 | 기존 메트릭 감사 후 `prometheus-fastapi-instrumentator` 통합 |
| **S3-3** | Admin AI 사용량/감사 로그 | P2 | EventOutbox 감사 뷰어 + NL2SQL/LLM 비용 모니터링 |

### Sprint 4: 시맨틱 거버넌스

| # | 항목 | 우선순위 | 설명 |
|---|------|---------|------|
| **V1** | 스냅샷 변경 목록 | P1 | canonical sort + 필드별 diff + changed_fields 포함 |
| **V4** | 스냅샷 비교 API | P2 | `semantic_contract.py`에 추가, `asyncio.to_thread` 래핑 |
| **V2** | Object Storage 폴백 | P2 | S3/EFS 아티팩트 번들 (로컬 JSON보다 우선), L effort |
| **VS-4** | SoftDelete 선택 도입 | P2 | SemanticEntity, OntologyConcept 등 핵심 자산만 |

### Sprint 5: UX/운영 고도화

| # | 항목 | 우선순위 | 설명 |
|---|------|---------|------|
| **V3** | 릴리스 히스토리 시각화 | P2 | V1/V4 데이터 기반, Cytoscape/SVG 트리 |
| **VS-6** | Path-Filtered CI | P2 | 변경 서비스만 빌드, CI 시간 70% 단축 |
| **VS-3** | 이벤트 무결성 서명 | P2 | HMAC-SHA256, 거버넌스 고도화 단계 |
| **S1-4** | Input Sanitization (3단계) | P1 | 아래 상세 참조 |

### 미권장

| 항목 | 사유 |
|------|------|
| OAuth 소셜 로그인 | B2B → SAML/OIDC SSO 적합 |
| GSAP 애니메이션 | 데이터 중심 도구에 불필요 |
| Kustomize K8s | 프로덕션 전환 시점에 별도 검토 |

---

## 6. 상세 구현 명세

### 6.1 S1-1: Security Headers 미들웨어

> 보안 헤더는 가능하면 API 앱이 아니라 Gateway/Ingress에서 일괄 적용한다.
> FastAPI 미들웨어는 로컬 개발과 예외 경로 보완용으로 유지한다.
> CSP는 3단계로 진행: ①Report-Only ②nonce/hash 적용 ③enforcing 전환

```python
# services/shared/middleware/security_headers.py
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_connect_src: str = "'self'"):
        super().__init__(app)
        self.allowed_connect_src = allowed_connect_src

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        is_docs = request.url.path in ("/docs", "/redoc", "/openapi.json")

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        if not is_docs:
            csp_header = "Content-Security-Policy-Report-Only"  # 1단계
            response.headers[csp_header] = (
                f"default-src 'self'; script-src 'self'; "
                f"style-src 'self' 'unsafe-inline'; "
                f"img-src 'self' data: blob:; font-src 'self'; "
                f"connect-src {self.allowed_connect_src}; "
                f"frame-ancestors 'none'; "
                f"report-uri /api/v1/security/csp-report"
            )

        is_https = (
            request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto") == "https"
        )
        if is_https:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response
```

**CSP 위반 수집 엔드포인트**: `/api/v1/security/csp-report` (POST) → 로그에 기록하여 피드백 루프 형성

---

### 6.2 S1-2: Lazy Loading + Retry

```typescript
// canvas/src/utils/lazyWithRetry.ts
import { lazy, type ComponentType } from 'react';

const RELOAD_KEY = 'axiom_chunk_reload';

export function lazyWithRetry<T extends ComponentType<unknown>>(
  factory: () => Promise<{ default: T }>,
  retries = 2,
  interval = 1500,
): React.LazyExoticComponent<T> {
  return lazy(async () => {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        sessionStorage.removeItem(RELOAD_KEY);
        return await factory();
      } catch (error) {
        if (attempt === retries) {
          if (sessionStorage.getItem(RELOAD_KEY)) {
            sessionStorage.removeItem(RELOAD_KEY);
            throw error; // ErrorBoundary에 위임
          }
          sessionStorage.setItem(RELOAD_KEY, '1');
          window.location.reload();
          throw error;
        }
        await new Promise((r) => setTimeout(r, interval));
      }
    }
    throw new Error('lazyWithRetry: unreachable');
  });
}
```

**적용**: `routeConfig.tsx`의 38개 `lazy()` → `lazyWithRetry()` 교체

---

### 6.3 S1-3: Rate Limit 응답 헤더

레이트 리밋은 `tenant_id + user_id` 조합을 기본 키로 하고, 익명 경로는 IP 기반 fallback을 적용한다.
429 응답에는 `Retry-After`를 포함하며, 클라이언트는 잔여 quota와 reset 시점을 기준으로 점진적으로 요청 속도를 조절한다.

- ASGI 미들웨어: `(b"x-ratelimit-limit", ...)` 튜플 형식
- BaseHTTPMiddleware: `response.headers["X-RateLimit-Limit"] = ...` 딕셔너리 형식

---

### 6.4 S1-4: Input Sanitization (3단계)

`sanitizeInput()` 단일 유틸만으로 XSS를 해결한다고 보지 않는다.
React 일반 JSX는 기본 escape를 제공하므로, 실제 방어 대상은 다음이다.

| 단계 | 대상 | 전략 |
|------|------|------|
| 1 | 기본 텍스트 필드 | 길이 제한 + 서버측 검증 |
| 2 | HTML/Markdown 렌더링 경로 | allowlist 기반 sanitizer (DOMPurify 권장) |
| 3 | URL/파일명/식별자 | 스키마/문자셋/길이 별도 검증 |

---

### 6.5 S1-5: Production Docs 비활성화

```python
import os
_is_prod = os.getenv("ENVIRONMENT", "dev") == "production"
app = FastAPI(
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)
```

---

### 6.6 S2-1: 구조화 Access Log

필수 필드: `request_id`, `tenant_id`, `user_id`, `method`, `path`, `route_template`, `status_code`, `duration_ms`, `client_ip`, `service_name`

필수 정책:
- `/health`, `/metrics`, 정적 파일은 샘플링 또는 제외
- Authorization, Cookie, 토큰, 프롬프트 원문은 마스킹
- 예외 발생 시에도 `try/finally`로 반드시 로그 기록

---

### 6.7 S2-2: Trivy 보안 스캔

```yaml
- name: Trivy 보안 스캔
  uses: aquasecurity/trivy-action@0.28.0  # 버전 고정
  with:
    image-ref: 'axiom-canvas:${{ github.sha }}'
    format: 'table'
    exit-code: '1'
    severity: 'CRITICAL,HIGH'
    ignore-unfixed: true
```

병행: `pip-audit` (Python), `npm audit` (Node.js) 별도 CI 스텝 추가

---

### 6.8 S2-3: Docker Healthcheck (liveness/readiness 분리)

```python
# services/shared/api/health.py
@router.get("/health/live")
async def liveness():
    """프로세스 이벤트 루프 + HTTP 응답 가능 여부"""
    return {"status": "alive"}

@router.get("/health/ready")
async def readiness(db=Depends(get_db), redis=Depends(get_redis)):
    """DB, Redis, 내부 의존 서비스 연결 확인"""
    checks = {"db": True, "redis": True}
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        checks["db"] = False
    try:
        await redis.ping()
    except Exception:
        checks["redis"] = False

    all_ok = all(checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
```

오케스트레이터는 readiness 실패 시 트래픽만 차단, liveness 실패 시에만 재시작.

---

### 6.9 VS-2: Circuit Breaker

단독 기법이 아니라 `timeout → bounded retry → breaker → fallback cache` 순서의 보호 체계로 적용.

Oracle→Synapse 조회는 캐시된 마지막 활성 스냅샷을 fallback으로 사용.

---

### 6.10 VS-5: Token Blacklist

```python
# 로그아웃 시
await redis.setex(f"blacklist:{jti}", token_remaining_ttl, "1")
# 계정 정지 시 — 모든 토큰 무효화
await redis.setex(f"user_revoke:{user_id}", MAX_TOKEN_TTL, str(now()))
# 인증 미들웨어에서 검사
if await redis.exists(f"blacklist:{jti}"):
    raise HTTPException(401, "Token revoked")
```

**Redis 장애 시 fallback**: 인증 전체가 막히지 않도록 `token_version` 또는 `session_revoked_after` 대안 검토

---

### 6.11 V1: 스냅샷 변경 목록

- 비교 전 canonical sort 필수 (순서 변경 ≠ 변경)
- Change 항목에 `changed_fields` 포함 (단순 "Change"보다 정보량 높음)
- 대규모 계약 대비: 아티팩트 해시 비교 → 변경된 아티팩트만 세부 diff

---

### 6.12 V2: Object Storage 폴백

> 로컬 JSON보다 Object Storage(S3/EFS)를 우선 대상으로 한다.

- 활성 스냅샷 메타는 DB/Redis에 두고, 본문은 object storage 조회
- 다중 레플리카 환경에서 로컬 파일은 최후의 수단
- 스냅샷 activate 성공 시 비동기 갱신 + 원자적 쓰기 (tmp → rename)
- **L effort** — 별도 설계 문서 필요

---

### 6.13 S3-1: E2E 테스트 (2층)

| 층 | 용도 | 트리거 | 서비스 |
|----|------|--------|--------|
| Mock E2E | UI 회귀 확인 | PR마다 | API mock (Playwright route) |
| Stage Smoke E2E | 실 연동 확인 | 배포 전 | staging 실서비스 |

Mock만 통과해도 실제 API 계약 불일치가 숨을 수 있으므로, 배포 전 최소 3개 핵심 플로우는 stage 실연동 smoke 필수.

---

### 6.14 VS-1: Shared Library

- 개발 환경: `pip install -e ../shared` (editable)
- CI/production: 버전 고정된 내부 패키지 wheel 또는 monorepo package build
- 서비스 간 의존성 드리프트와 사용불가 빌드를 방지

---

## 7. 롤아웃 전략

모든 변경은 다음 순서로 점진 적용한다.

1. **dev 환경** 적용
2. **stage 환경**에서 1주 관측
3. **canary tenant** 또는 내부 관리자 대상 선택 오픈
4. **전 tenant** 확대

**토글 필수 항목** (Feature Flag로 제어):

- CSP enforce 전환
- lazyWithRetry 활성화
- compare API 공개
- 토큰 블랙리스트 강제 적용
- fail-silent 이벤트 발행 정책

---

## 8. 롤백 기준

| 항목 | 롤백 조건 | 롤백 방법 |
|------|----------|----------|
| CSP | API 실패율 증가 | Report-Only로 즉시 복귀 |
| Token Blacklist | 인증 실패율 급증 | revoke 검사 후크 비활성화 |
| Circuit Breaker | false open 빈발 | endpoint별 threshold 완화 또는 비활성화 |
| Healthcheck | 재시작 루프 발생 | readiness만 유지, liveness 보완 후 재적용 |
| Rate Limit 헤더 | 클라이언트 호환성 문제 | 헤더만 제거 (429 로직 유지) |

---

## 9. 운영 승인 기준 (Go/No-Go)

production 확대를 승인하는 조건:

- 7일간 P1 장애 **0건**
- 인증 실패율 증가 **없음** (기준 대비 +0.5%p 이내)
- 429 비율 **30% 이상 감소**
- stage 기준 E2E 통과율 **100%**
- rollback rehearsal **1회 성공**
- 보안 헤더 및 docs 비활성화 점검 **완료**

---

## 10. Entry/Exit 기준

### Sprint 진입 기준

- 이전 Sprint PR 머지 완료
- CI 통과 (tsc -b 0 errors, 기존 테스트 전체 통과)
- 해당 Sprint 파일 목록 확정

### Sprint 완료 기준

- 모든 항목 구현 + tsc -b 0 errors
- **기존 테스트 회귀 없음 (전체 통과 — 상대 기준)**
- 신규 항목에 대한 테스트 추가 (항목당 최소 3건)
- 코드 리뷰 완료 (code-reviewer 에이전트)
- PR CI 통과 + 머지

---

## 11. 리스크 및 완화

| 리스크 | 영향 | 완화 |
|--------|------|------|
| CSP가 마이크로서비스 API 호출 차단 | Canvas→Backend 실패 | Report-Only + connect-src + CSP report 엔드포인트 |
| Lazy Retry 무한 새로고침 | 사용자 브라우저 루프 | sessionStorage 1회 플래그 + ErrorBoundary 위임 |
| Rate Limit 헤더 ASGI 호환 | 서비스별 구현 차이 | shared 라이브러리 + ASGI/BaseHTTPMiddleware 가이드 |
| Circuit Breaker false open | 정상 요청 차단 | Feature Flag + endpoint별 threshold 조절 |
| DB 폴백 다중 레플리카 불일치 | 다른 스냅샷 서빙 | S3/EFS 공유 + 원자적 쓰기 |
| Token Blacklist Redis 장애 | 인증 전체 차단 | token_version fallback + Redis 장애 시 검사 skip |
| Shared Library 버전 드리프트 | 서비스 간 불일치 | CI에서 shared 변경 시 전체 빌드 |
| SoftDelete 쿼리 누락 | 삭제된 데이터 노출 | `WHERE deleted_at IS NULL` 글로벌 필터 + 코드 리뷰 체크리스트 |

---

## 12. 추가 검토 사항

| 항목 | 상태 | 비고 |
|------|------|------|
| CORS 표준화 | 미포함 | 서비스별 설정 불일치 — 별도 이슈 추적 |
| Graceful Shutdown | 미포함 | SIGTERM 처리 — Healthcheck와 함께 검토 |
| pip-audit / npm audit | Sprint 2 병행 | Trivy 보완 |
| CSP nonce/hash 전략 | Sprint 1 이후 | 2단계에서 상세 설계 |
| Event DLQ/재처리 정책 | Sprint 2 N5 | 스키마 버전 + idempotency와 함께 |

---

## 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2026-03-24 | v1.0 | 초안 — Alparka 18개 항목 + 버전 관리 비교 |
| 2026-03-24 | v1.1 | 코드 리뷰 반영 (CSP, lazyWithRetry, 파일 경로, E2E, 타입 호환) |
| 2026-03-24 | v1.2 | 도입 장점 분석 추가 |
| 2026-03-24 | v1.3 | VibeSnack 7개 항목 추가 (총 25개, Sprint 5) |
| 2026-03-24 | v2.0 | v1.4 보강본 전면 반영: 의사결정 원칙, 플랫폼 기반 Sprint 0 신설, 31개 항목 재구성, 롤아웃/롤백/운영승인 기준 추가, CSP edge-first + report URI, Sanitization 3단계, Healthcheck liveness/readiness 분리, E2E 2층, V2 Object Storage 우선, Shared Library CI/prod 빌드 전략, 에러코드/RequestID/Feature Flag 신규 항목 |
