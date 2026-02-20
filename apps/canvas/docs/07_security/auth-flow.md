# JWT 인증 흐름, 토큰 관리, RBAC UI

<!-- affects: frontend, api, security -->
<!-- requires-update: 02_api/api-client.md, 04_frontend/routing.md -->

## 이 문서가 답하는 질문

- Canvas의 인증 흐름은 어떻게 동작하는가?
- JWT 토큰의 발급/갱신/만료 처리는?
- RBAC(Role-Based Access Control)은 UI에서 어떻게 반영되는가?
- K-AIR Keycloak 인증과 무엇이 달라지는가?

---

## 1. 인증 흐름

### 1.1 로그인 흐름

```
사용자                Canvas                Core API              인증 서비스
  │                     │                     │                      │
  │  이메일/비밀번호    │                     │                      │
  │ ──────────────────▶│                     │                      │
  │                     │  POST /auth/login   │                      │
  │                     │ ──────────────────▶ │                      │
  │                     │                     │  자격 증명 검증       │
  │                     │                     │ ────────────────────▶│
  │                     │                     │                      │
  │                     │                     │  검증 결과            │
  │                     │                     │ ◀────────────────────│
  │                     │                     │                      │
  │                     │  200 OK             │                      │
  │                     │  { accessToken,     │                      │
  │                     │    refreshToken,    │                      │
  │                     │    user }           │                      │
  │                     │ ◀────────────────── │                      │
  │                     │                     │                      │
  │                     │  authStore 업데이트  │                      │
  │                     │  sessionStorage     │                      │
  │                     │  /dashboard 이동    │                      │
  │ ◀──────────────────│                     │                      │
  │  대시보드 표시      │                     │                      │
```

### 1.2 토큰 갱신 흐름

```
[API 호출] ──→ [401 응답] ──→ [토큰 갱신 시도]
                                    │
                              ┌─────┴─────┐
                              │            │
                      [갱신 성공]      [갱신 실패]
                              │            │
                      [새 accessToken] [로그아웃]
                      [원래 요청 재시도] [/auth/login]
                              │
                      [성공 응답 반환]
```

### 1.3 토큰 구조

```typescript
// Access Token (JWT, 15분 만료)
// [SSOT] Core auth-model.md의 JWT payload 구조를 따른다.
interface AccessTokenPayload {
  sub: string;           // 사용자 ID
  email: string;
  role: UserRole;
  tenant_id: string;     // snake_case (Core SSOT)
  permissions: string[];
  case_roles: Record<string, CaseRole>;  // 케이스별 역할
  iat: number;           // 발급 시간
  exp: number;           // 만료 시간 (15분)
}

// Refresh Token (Opaque, 7일 만료)
// - 서버 측 저장 (Redis)
// - 1회 사용 (갱신 시 새 refresh token 발급)
```

---

## 2. 토큰 관리

### 2.1 저장소

| 토큰 | 저장소 | 이유 |
|------|--------|------|
| Access Token | sessionStorage + Zustand | 탭 종료 시 소멸, XSS 방어 |
| Refresh Token | httpOnly Cookie (권장) 또는 sessionStorage | CSRF 방어 |

### 2.2 자동 갱신

```typescript
// lib/api/createApiClient.ts (Auth Error Handler)

// 401 응답 시 자동 갱신 (1회만)
instance.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config;
    if (!original) return Promise.reject(error);

    // 401 + 첫 번째 시도 + 로그인 API가 아닌 경우만
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes('/auth/')
    ) {
      original._retry = true;

      try {
        const newToken = await useAuthStore.getState().refreshAccessToken();
        original.headers.Authorization = `Bearer ${newToken}`;
        return instance(original);  // 원래 요청 재시도
      } catch (refreshError) {
        // 갱신 실패 -> 로그아웃
        useAuthStore.getState().logout();
        window.location.href = '/auth/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

### 2.3 로그아웃 처리

```typescript
// stores/authStore.ts

logout: () => {
  // 1. 서버에 로그아웃 요청 (refresh token 무효화)
  coreApi.post('/auth/logout').catch(() => {});

  // 2. 로컬 상태 초기화
  set({ user: null, accessToken: null, refreshToken: null });

  // 3. sessionStorage 클리어
  sessionStorage.removeItem('axiom-auth');

  // 4. TanStack Query 캐시 전체 클리어
  queryClient.clear();

  // 5. WebSocket 연결 해제
  wsManager.disconnect();

  // 6. 로그인 페이지로 이동
  window.location.href = '/auth/login';
}
```

---

## 3. RBAC UI 구현

### 3.1 역할 정의

| 역할 | 설명 | 접근 가능 기능 |
|------|------|---------------|
| `admin` | 시스템 관리자 | 전체 + 사용자/권한 관리 |
| `manager` | 프로세스 분석가 | 대시보드, 문서 승인, Watch |
| `attorney` | 도메인 전문가 | 문서 CRUD, HITL 리뷰 |
| `analyst` | 재무 분석가 | OLAP, What-if, NL2SQL |
| `engineer` | 데이터 엔지니어 | 데이터소스, 온톨로지, NL2SQL |
| `staff` | 담당 직원 | 할당된 작업 처리, 문서 읽기 |
| `viewer` | 뷰어 | 읽기 전용 |

> **역할 이름 규칙**: Core auth-model.md의 시스템 역할 이름을 그대로 사용한다. UI 표시명은 별도 i18n 처리한다.

### 3.2 권한 체크 UI 패턴

```typescript
// shared/hooks/usePermission.ts

function usePermission(permission: string): boolean {
  const permissions = useAuthStore((s) => s.user?.permissions ?? []);
  return permissions.includes(permission);
}

function useRole(roles: UserRole[]): boolean {
  const role = useAuthStore((s) => s.user?.role);
  return role ? roles.includes(role) : false;
}

// 사용 예시
function DocumentActions({ docId }: { docId: string }) {
  const canApprove = usePermission('document:approve');
  const canEdit = usePermission('document:edit');

  return (
    <div>
      {canEdit && <Button onClick={() => edit(docId)}>수정</Button>}
      {canApprove && <Button onClick={() => approve(docId)}>승인</Button>}
    </div>
  );
}
```

### 3.3 라우트 레벨 권한

```typescript
// shared/components/RoleGuard.tsx

function RoleGuard({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const hasRole = useRole(roles);

  if (!hasRole) {
    return <ForbiddenPage />;  // "이 페이지에 접근할 권한이 없습니다"
  }

  return <>{children}</>;
}

// router.tsx 사용 예시
{
  path: 'data/datasources',
  element: (
    <RoleGuard roles={['admin', 'engineer']}>
      <DatasourcePage />
    </RoleGuard>
  ),
}
```

### 3.4 사이드바 메뉴 권한 필터

```typescript
// layouts/Sidebar/SidebarNav.tsx

const menuItems = [
  { path: '/dashboard', label: '대시보드', roles: ['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer'] },
  { path: '/cases', label: '케이스', roles: ['admin', 'manager', 'attorney', 'analyst', 'staff', 'viewer'] },
  { path: '/analysis/olap', label: 'OLAP 피벗', roles: ['admin', 'analyst', 'engineer'] },
  { path: '/analysis/nl2sql', label: '자연어 쿼리', roles: ['admin', 'analyst', 'engineer'] },
  { path: '/data/ontology', label: '온톨로지', roles: ['admin', 'engineer'] },
  { path: '/data/datasources', label: '데이터소스', roles: ['admin', 'engineer'] },
  { path: '/watch', label: 'Watch', roles: ['admin', 'manager'] },
  { path: '/settings', label: '설정', roles: ['admin'] },
];

// 현재 역할에 맞는 메뉴만 표시
const visibleItems = menuItems.filter(item =>
  item.roles.includes(currentUser.role)
);
```

---

## 4. K-AIR 인증 전환

| K-AIR (Keycloak) | Canvas (JWT) |
|-------------------|-------------|
| Keycloak 서버 별도 운영 | Core API가 인증 담당 |
| Keycloak JS 어댑터 | Axios 인터셉터 |
| Keycloak realm/client 설정 | 환경 변수 (Core URL) |
| 토큰 갱신: keycloak.updateToken() | authStore.refreshAccessToken() |
| 역할: Keycloak realm roles | JWT payload.role |
| 멀티테넌트: X-Forwarded-Host | X-Tenant-Id 헤더 |

---

## 결정 사항 (Decisions)

- Access Token 15분, Refresh Token 7일
  - 근거: 짧은 AT로 토큰 탈취 영향 최소화, 긴 RT로 사용자 편의

- Keycloak 제거, Core API 위임 인증
  - 근거: 인프라 단순화, Keycloak 운영 부담 제거
  - 재평가: SSO 요구사항 발생 시 Keycloak 재도입 검토

## 금지됨 (Forbidden)

- Access Token을 localStorage에 저장 (XSS 공격 위험)
- 프론트엔드에서 권한 체크만으로 API 호출 생략 (서버 측 권한 검증 필수)
- URL에 토큰 포함 (쿼리 파라미터로 토큰 전달 금지)

## 필수 (Required)

- 모든 API 호출에 Authorization 헤더 자동 첨부 (인터셉터)
- 로그아웃 시 모든 로컬 데이터 클리어 (캐시 + 스토어 + 스토리지)
- 역할 없는 사용자에게 UI 요소를 숨기되, 서버 측 검증도 병행

---

## 관련 문서

- [04_frontend/admin-dashboard.md](../04_frontend/admin-dashboard.md) (admin 역할 전용 관리자 대시보드, 사용자 관리 UI)
- [04_frontend/case-dashboard.md](../04_frontend/case-dashboard.md) (역할별 대시보드 합성 — §4, DashboardComposer, useRole 활용)
- Core 로깅 체계 (`services/core/docs/08_operations/logging-system.md`): 관리자 감사 로그, admin API 인증

---

## 변경 이력

| 날짜 | 버전 | 작성자 | 내용 |
|------|------|--------|------|
| 2026-02-19 | 1.0 | Axiom Team | 초기 작성 |
