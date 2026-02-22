# Axiom Core - JWT 인증 모델

> **최종 수정일**: 2026-02-22
> **상태**: Implemented (Core 내 인증·갱신·보호 경로 적용 완료)

**구현 근거**: `app/core/security.py` (JWT 발급/검증, get_current_user, ROLE_PERMISSIONS), `app/api/auth/routes.py` (login, refresh, Redis 블랙리스트), `app/main.py` (보호 라우터에 Depends(get_current_user)). User·Tenant 모델: `app/models/base_models.py`.

## 이 문서가 답하는 질문

- JWT 토큰은 어떻게 발급, 검증, 갱신되는가?
- RBAC 역할과 권한은 어떻게 구성되는가?
- 멀티테넌트 인증은 어떻게 동작하는가?
- 시스템 역할과 모듈별 역할의 매핑은?
- K-AIR의 Keycloak/JJWT에서 무엇을 이식하는가?

<!-- affects: api, backend -->
<!-- requires-update: 02_api/gateway-api.md -->

---

## 1. 인증 흐름

### 1.1 로그인 -> 토큰 발급

```
1. POST /api/v1/auth/login
   Body: { "email": "user@example.com", "password": "..." }

2. 서버 검증:
   a. 이메일/비밀번호 확인 (bcrypt)
   b. 사용자 활성 상태 확인
   c. 테넌트 활성 상태 확인

3. JWT 토큰 발급:
   Access Token (15분 유효):
   {
     "sub": "user-uuid",
     "email": "user@example.com",
     "tenant_id": "tenant-uuid",
     "role": "manager",
     "permissions": ["case:read", "case:write", "process:initiate"],
     "case_roles": {
       "case-uuid-1": "trustee",
       "case-uuid-2": "viewer"
     },
     "iat": 1708300000,
     "exp": 1708300900
   }

   Refresh Token (7일 유효):
   {
     "sub": "user-uuid",
     "type": "refresh",
     "iat": 1708300000,
     "exp": 1708904800
   }

   [SSOT] 이 JWT payload 구조가 Axiom 전체의 표준이다.
   - tenant_id: snake_case (camelCase 금지)
   - role: 단수형 문자열 (배열 금지)
   - case_roles: 케이스별 역할 dict (해당 사용자가 배정된 케이스만 포함)
   - permissions: 시스템 역할에서 파생된 권한 문자열 배열

4. 응답:
   { "access_token": "eyJ...", "refresh_token": "eyJ...", "expires_in": 900 }
```

### 1.2 요청 인증

```python
# app/core/security.py
# K-AIR gs-main/gateway의 JwtAuthFilter에서 이식

from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(
    credentials = Depends(security),
) -> dict:
    """JWT 토큰 검증 및 사용자 정보 추출"""
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],  # RS256 또는 HS256
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")

    # 만료 확인
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")

    return {
        "user_id": payload["sub"],
        "email": payload.get("email"),
        "tenant_id": payload["tenant_id"],
        "role": payload["role"],
        "permissions": payload.get("permissions", []),
        "case_roles": payload.get("case_roles", {}),
    }
```

---

## 2. RBAC (역할 기반 접근 제어)

### 2.1 시스템 역할 체계

| 역할 | 설명 | 주요 권한 |
|------|------|----------|
| **admin** | 시스템 관리자 | 모든 권한 |
| **manager** | 프로세스 분석가/책임자 | 케이스 관리, 프로세스 관리, 사용자 관리 |
| **attorney** | 도메인 전문가 | 케이스 읽기/쓰기, 문서 관리, 에이전트 사용 |
| **analyst** | 재무/데이터 분석가 | OLAP, What-if, NL2SQL, 분석 실행 |
| **engineer** | 데이터 엔지니어 | 데이터소스 관리, 온톨로지, NL2SQL |
| **staff** | 담당 직원 | 할당된 작업 처리, 문서 읽기 |
| **viewer** | 읽기 전용 | 조회만 가능 |

### 2.2 케이스 역할 체계

시스템 역할과 별개로, 사용자는 개별 케이스에 대한 케이스 역할을 부여받는다. JWT의 `case_roles` 필드에 포함된다.

| 케이스 역할 | 설명 | 권한 |
|------------|------|------|
| **trustee** | 케이스 담당자 | 해당 케이스의 CRUD, 분석 실행 |
| **reviewer** | 검토자 | 해당 케이스의 결과 조회, 승인 |
| **viewer** | 조회자 | 해당 케이스의 결과 조회만 |

### 2.3 권한 매트릭스

| 권한 | admin | manager | attorney | analyst | engineer | staff | viewer |
|------|:-----:|:-------:|:--------:|:-------:|:--------:|:-----:|:------:|
| case:create | O | O | X | X | X | X | X |
| case:read | O | O | O | O | O | O | O |
| case:write | O | O | O | X | X | X | X |
| case:delete | O | X | X | X | X | X | X |
| process:initiate | O | O | O | X | X | X | X |
| process:submit | O | O | O | O | X | O | X |
| process:approve | O | O | X | X | X | X | X |
| agent:chat | O | O | O | O | O | O | X |
| agent:feedback | O | O | O | O | X | X | X |
| watch:manage | O | O | O | X | X | O | X |
| mcp:configure | O | O | X | X | X | X | X |
| user:manage | O | O | X | X | X | X | X |
| tenant:manage | O | X | X | X | X | X | X |
| olap:query | O | O | O | O | O | O | O |
| olap:manage | O | X | X | X | X | X | X |
| nl2sql:query | O | O | O | O | O | O | X |
| datasource:manage | O | X | X | X | O | X | X |
| datasource:read | O | O | O | O | O | O | O |
| ontology:manage | O | X | X | X | O | X | X |
| ontology:read | O | O | O | O | O | O | O |
| schema:edit | O | X | X | X | O | X | X |
| schema:read | O | O | O | O | O | O | O |

### 2.4 권한 검사 구현

```python
# app/core/security.py

from functools import wraps

def require_permission(permission: str):
    """권한 검사 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, current_user=Depends(get_current_user), **kwargs):
            if permission not in current_user.get("permissions", []):
                if current_user["role"] != "admin":  # admin은 모든 권한
                    raise HTTPException(
                        status_code=403,
                        detail=f"Permission '{permission}' required"
                    )
            return await func(*args, current_user=current_user, **kwargs)
        return wrapper
    return decorator

# 사용 예시
@router.post("/cases")
@require_permission("case:create")
async def create_case(data: CaseCreate, current_user: dict = Depends(get_current_user)):
    ...
```

---

## 3. 멀티테넌트 인증

```
[결정] JWT payload에 tenant_id를 포함한다.
[결정] 모든 API 요청에서 JWT의 tenant_id와 ContextVar의 tenant_id가 일치하는지 검증한다.
[결정] 한 사용자는 하나의 테넌트에만 속한다.

보안 검증 체인:
  1. JWT 검증 (서명, 만료)
  2. tenant_id 추출 (JWT payload)
  3. ContextVar 설정 (미들웨어)
  4. RLS 세션 변수 설정 (DB 접근 시)
  5. 4중 격리: JWT -> ContextVar -> RLS -> 쿼리 WHERE
```

---

## 4. 토큰 갱신

```
[결정] Access Token은 15분, Refresh Token은 7일 유효.
[결정] Refresh Token은 1회 사용 후 새로 발급 (Token Rotation).
[결정] 로그아웃 시 Refresh Token을 블랙리스트에 등록 (Redis, TTL=7일).

갱신 흐름:
  POST /api/v1/auth/refresh
  Body: { "refresh_token": "eyJ..." }

  검증:
    1. Refresh Token 유효성 확인
    2. 블랙리스트 미등록 확인
    3. 기존 Refresh Token 블랙리스트 등록
    4. 새 Access Token + Refresh Token 발급
```

---

## 5. 크로스 모듈 역할 매핑

Core 시스템 역할은 각 모듈에서 모듈별 권한으로 매핑된다. 아래 테이블은 **Core SSOT 역할**과 각 모듈 문서의 역할 간 매핑이다.

### 5.1 시스템 역할 → 모듈별 권한 매핑

| Core 시스템 역할 | Canvas UI 접근 | Vision 권한 | Synapse 권한 | Oracle 권한 | Weaver 권한 |
|-----------------|---------------|-------------|-------------|-------------|-------------|
| admin | 전체 + 사용자/권한 관리 | 모든 작업, 큐브 관리, ETL | 전체 CRUD + 배치 작업 | 전체 (SQL Guard 관리) | 전체 (데이터소스 관리) |
| manager | 대시보드, 문서 승인, Watch | 시나리오 생성/수정, 분석 | 소속 케이스 CRUD | NL2SQL 쿼리 | 읽기 전용 |
| attorney | 문서 CRUD, HITL 리뷰 | 담당 케이스 시나리오 CRUD | 소속 케이스 CRUD | NL2SQL 쿼리 | 읽기 전용 |
| analyst | OLAP, What-if, NL2SQL | 담당 케이스 분석 실행 | 읽기 전용 | NL2SQL 쿼리 | 읽기 전용 |
| engineer | 데이터소스, 온톨로지, NL2SQL | 읽기 전용 | 스키마 편집 | NL2SQL 쿼리 | 데이터소스 관리 |
| staff | 할당 작업 처리 | 읽기 전용 | 읽기 전용 | 읽기 전용 | 읽기 전용 |
| viewer | 읽기 전용 | 결과 조회만 | 읽기 전용 | 읽기 전용 | 읽기 전용 |

### 5.2 케이스 역할 → 모듈별 권한 매핑

| 케이스 역할 | Vision | Synapse |
|------------|--------|---------|
| trustee | 시나리오 CRUD, 분석 실행 | 온톨로지 CRUD (해당 케이스) |
| reviewer | 결과 조회, 승인 | HITL 검토 (해당 케이스) |
| viewer | 결과 조회만 | 읽기 전용 (해당 케이스) |

### 5.3 Synapse 모듈 역할 → Core 매핑

Synapse는 API 레벨에서 모듈별 역할 이름을 사용한다. Core 시스템 역할에서 파생된다.

| Synapse 모듈 역할 | Core 시스템 역할 원천 | 설명 |
|-------------------|---------------------|------|
| admin | admin | 동일 |
| case_editor | manager, attorney + 케이스 trustee | 소속 케이스 편집 |
| case_viewer | analyst, staff, viewer + 케이스 viewer | 소속 케이스 읽기 |
| hitl_reviewer | 케이스 reviewer | HITL 검토 전용 |
| schema_editor | engineer | 스키마 편집 전용 |
| schema_viewer | (모든 인증된 사용자) | 스키마 읽기 전용 |

---

## 관련 문서

- `apps/canvas/docs/04_frontend/case-dashboard.md` (역할별 대시보드 합성 — §4, 7개 역할 → 패널 매핑)
- `apps/canvas/docs/04_frontend/admin-dashboard.md` (admin 전용 시스템 관리 대시보드)
- `apps/canvas/docs/07_security/auth-flow.md` (Canvas 프론트엔드 인증 흐름, RoleGuard 구현)

---

## 근거

- K-AIR process-gpt-gs-main/gateway (JwtAuthFilter, ForwardHostHeaderFilter)
- K-AIR process-gpt-vue3-main (keycloak-js 24.0.2, @casl/vue)
- K-AIR 역설계 보고서 섹션 5.1 (인증 기술 스택)
