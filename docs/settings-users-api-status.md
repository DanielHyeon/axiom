# 설정 > 사용자 API 연동 현황

## 1. 조사 요약 및 책임 결정 (Phase B1)

| 구분 | 내용 |
|------|------|
| **문서에서 기대하는 API** | `POST /api/v1/users`(사용자 생성 시 Watch 구독 시드), `GET /users/me`, `GET/POST/PATCH /api/v1/admin/users` 등 |
| **책임 결정** | **Core 담당**: 인증(login/refresh), 현재 사용자 조회(`GET /api/v1/users/me`). **추후 확장**: 사용자 목록·생성·초대·admin 사용자 관리는 Core에 추가 구현 예정. 케이스 CRUD는 Gateway 프록시(Synapse 등) 유지. |

---

## 2. 백엔드 연결 상태

### 2.1 Core 서비스 (`services/core`)

- **등록된 라우터**: `health`, `auth`, `process`, `watch`, `agent`, `gateway`, `events`, `users`.
- **auth 라우터**: 구현됨. `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, JWT 검증.
- **users 라우터**: `GET /api/v1/users/me` 구현됨. 사용자 목록·생성·admin API는 미구현.
- **모델**: `User`, `Tenant` 테이블 존재. `WatchSubscription.user_id`, `WorkItem.assignee_id` 등은 사용자 ID 문자열 참조.

### 2.2 문서에서 언급된 API

| 문서 | 내용 |
|------|------|
| `services/core/docs/02_api/watch-api.md` | "사용자 생성 시(`POST /api/v1/users`) 역할에 따라 기본 구독이 자동 생성된다" — **계약 가정**이며, Core에 해당 엔드포인트 없음. |
| `apps/canvas/docs/04_frontend/admin-dashboard.md` | `GET /api/v1/admin/users`, `POST /api/v1/admin/users/invite`, `PATCH /api/v1/admin/users/:userId/role|status` — **스펙 기술**만 있음, 구현 없음. |
| `apps/canvas/docs/02_api/api-contracts.md` | `GET /users/me` (현재 사용자) — **계약 정의**만 있음. |

### 2.3 다른 서비스 (Vision / Oracle / Weaver)

- 각 서비스에 `app.core.auth` 존재. **JWT에서 현재 사용자(CurrentUser) 추출**만 수행.
- **사용자 목록·생성·수정 API**는 어느 서비스에도 없음.
- 로그인/토큰 발급은 이 리포지터리 밖(게이트웨이·외부 IdP 등)에서 처리되는 것으로 추정.

---

## 3. 구현 여부 결론

| API | 구현 여부 | 비고 |
|-----|------------|------|
| `GET /api/v1/users` (목록) | **미구현** | 추후 확장. |
| `POST /api/v1/users` (생성) | **미구현** | 추후 확장(Watch 구독 시드 연동). |
| `GET /api/v1/users/me` | **구현됨** | Core `app/api/users/routes.py`. JWT 인증 필수. |
| `GET/POST/PATCH /api/v1/admin/users` | **미구현** | admin-dashboard 스펙, 추후 확장. |

**프론트엔드**: 설정 > 사용자 페이지는 **authStore** 또는 **GET /api/v1/users/me** 호출로 현재 사용자 표시 가능.  
사용자 목록·초대·역할/상태 변경은 추후 Core API 추가 후 연동.

---

## 4. 권장 순서 (사용자 기능 확장 시)

1. **백엔드**: Core(또는 API Gateway)에 다음 중 하나 이상 구현.  
   - `GET /api/v1/users/me` — 현재 사용자 상세 (선택, JWT만 쓸 경우 불필요).  
   - `GET /api/v1/admin/users` — 목록 (역할/상태/검색).  
   - `POST /api/v1/admin/users/invite` — 초대.  
   - `PATCH /api/v1/admin/users/:userId/role`, `PATCH .../status` — 역할/상태 변경.  
2. **프론트**: `SettingsUsersPage`에서 위 API를 호출하는 클라이언트 추가 후, 목록·초대·편집 폼 연동.
