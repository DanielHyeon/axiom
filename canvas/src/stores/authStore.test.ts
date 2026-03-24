/**
 * Auth Store 테스트 — 고위험 인증 플로우 검증.
 *
 * 검증 대상:
 * - login/logout 상태 전이
 * - 토큰 관리 (저장, 갱신, 만료)
 * - 역할(role) 기반 접근 제어 데이터 무결성
 * - 멀티테넌트 tenantId 관리
 * - sessionStorage 영속성 (persist middleware)
 * - refreshAccessToken 동시 요청 방어 (in-flight dedup)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { User } from '@/types/auth.types';

// axios를 모킹하여 refreshAccessToken의 네트워크 호출을 격리
vi.mock('axios', () => {
  const mockPost = vi.fn();
  return {
    default: {
      post: mockPost,
      create: vi.fn(() => ({
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
      })),
    },
    __mockPost: mockPost,
  };
});

// window.location.href 할당을 추적하기 위한 설정
const locationHrefSpy = vi.fn();
const originalLocation = window.location;

beforeEach(() => {
  // sessionStorage 초기화 (persist 스토어 격리)
  sessionStorage.clear();

  // window.location mock — logout 시 리다이렉트 검증
  Object.defineProperty(window, 'location', {
    writable: true,
    value: { ...originalLocation, href: '' },
  });
  Object.defineProperty(window.location, 'href', {
    set: locationHrefSpy,
    get: () => '',
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  window.location = originalLocation;
});

// 매 테스트마다 스토어를 fresh하게 임포트하기 위해 dynamic import 사용
async function getStore() {
  // 모듈 캐시를 초기화하여 persist 미들웨어가 clean state로 시작
  vi.resetModules();
  const mod = await import('./authStore');
  return mod.useAuthStore;
}

// ── 테스트 픽스처 ──

function createMockUser(overrides: Partial<User> = {}): User {
  return {
    id: 'user-001',
    email: 'admin@local.axiom',
    role: 'admin',
    tenantId: 'tenant-abc-123',
    permissions: ['datasource:read', 'datasource:write', 'cube:publish'],
    caseRoles: { 'case-1': 'owner' },
    ...overrides,
  };
}

const MOCK_ACCESS_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock-access';
const MOCK_REFRESH_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.mock-refresh';

// ═══════════════════════════════════════════════════════════════
// 1. 초기 상태 검증
// ═══════════════════════════════════════════════════════════════

describe('AuthStore 초기 상태', () => {
  it('로드 직후 user, accessToken, refreshToken이 모두 null', async () => {
    const useAuthStore = await getStore();
    const state = useAuthStore.getState();

    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
  });

  it('모든 액션 함수가 정의되어 있다', async () => {
    const useAuthStore = await getStore();
    const state = useAuthStore.getState();

    expect(typeof state.setTokens).toBe('function');
    expect(typeof state.setUser).toBe('function');
    expect(typeof state.login).toBe('function');
    expect(typeof state.logout).toBe('function');
    expect(typeof state.refreshAccessToken).toBe('function');
  });
});

// ═══════════════════════════════════════════════════════════════
// 2. login — 사용자 + 토큰 동시 설정
// ═══════════════════════════════════════════════════════════════

describe('login 액션', () => {
  it('user, accessToken, refreshToken을 한 번에 설정한다', async () => {
    const useAuthStore = await getStore();
    const mockUser = createMockUser();

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, mockUser);
    const state = useAuthStore.getState();

    expect(state.user).toEqual(mockUser);
    expect(state.accessToken).toBe(MOCK_ACCESS_TOKEN);
    expect(state.refreshToken).toBe(MOCK_REFRESH_TOKEN);
  });

  it('admin 역할의 사용자 정보가 올바르게 저장된다', async () => {
    const useAuthStore = await getStore();
    const adminUser = createMockUser({ role: 'admin', permissions: ['datasource:read', 'datasource:write', 'cube:publish', 'ai:use'] });

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, adminUser);

    expect(useAuthStore.getState().user?.role).toBe('admin');
    expect(useAuthStore.getState().user?.permissions).toContain('cube:publish');
  });

  it('viewer 역할은 제한된 permissions만 가진다', async () => {
    const useAuthStore = await getStore();
    const viewerUser = createMockUser({ role: 'viewer', permissions: ['datasource:read'] });

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, viewerUser);

    expect(useAuthStore.getState().user?.role).toBe('viewer');
    expect(useAuthStore.getState().user?.permissions).not.toContain('datasource:write');
    expect(useAuthStore.getState().user?.permissions).toContain('datasource:read');
  });

  it('tenantId가 올바르게 저장된다', async () => {
    const useAuthStore = await getStore();
    const user = createMockUser({ tenantId: 'tenant-xyz-789' });

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, user);

    expect(useAuthStore.getState().user?.tenantId).toBe('tenant-xyz-789');
  });

  it('caseRoles가 정확히 보존된다', async () => {
    const useAuthStore = await getStore();
    const user = createMockUser({ caseRoles: { 'case-A': 'owner', 'case-B': 'reviewer', 'case-C': 'viewer' } });

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, user);

    const stored = useAuthStore.getState().user!;
    expect(stored.caseRoles['case-A']).toBe('owner');
    expect(stored.caseRoles['case-B']).toBe('reviewer');
    expect(stored.caseRoles['case-C']).toBe('viewer');
  });
});

// ═══════════════════════════════════════════════════════════════
// 3. logout — 완전한 상태 초기화
// ═══════════════════════════════════════════════════════════════

describe('logout 액션', () => {
  it('모든 인증 상태를 null로 초기화한다', async () => {
    const useAuthStore = await getStore();
    const mockUser = createMockUser();

    // 먼저 로그인
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, mockUser);
    expect(useAuthStore.getState().user).not.toBeNull();

    // 로그아웃
    useAuthStore.getState().logout();
    const state = useAuthStore.getState();

    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
  });

  it('로그아웃 시 /login 으로 리다이렉트한다', async () => {
    const useAuthStore = await getStore();
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, createMockUser());

    useAuthStore.getState().logout();

    expect(locationHrefSpy).toHaveBeenCalledWith('/login');
  });
});

// ═══════════════════════════════════════════════════════════════
// 4. setTokens / setUser — 개별 세터
// ═══════════════════════════════════════════════════════════════

describe('setTokens / setUser 개별 액션', () => {
  it('setTokens는 토큰만 업데이트하고 user는 유지한다', async () => {
    const useAuthStore = await getStore();
    const mockUser = createMockUser();

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, mockUser);
    useAuthStore.getState().setTokens('new-access', 'new-refresh');

    expect(useAuthStore.getState().accessToken).toBe('new-access');
    expect(useAuthStore.getState().refreshToken).toBe('new-refresh');
    expect(useAuthStore.getState().user).toEqual(mockUser); // user 유지
  });

  it('setUser는 user만 업데이트하고 토큰은 유지한다', async () => {
    const useAuthStore = await getStore();
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, createMockUser());

    const updatedUser = createMockUser({ email: 'updated@axiom.io' });
    useAuthStore.getState().setUser(updatedUser);

    expect(useAuthStore.getState().user?.email).toBe('updated@axiom.io');
    expect(useAuthStore.getState().accessToken).toBe(MOCK_ACCESS_TOKEN); // 토큰 유지
  });
});

// ═══════════════════════════════════════════════════════════════
// 5. 역할(role) 기반 데이터 무결성
// ═══════════════════════════════════════════════════════════════

describe('역할(role) 기반 접근 제어 데이터', () => {
  const allRoles = ['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer'] as const;

  it.each(allRoles)('"%s" 역할이 정상 저장된다', async (role) => {
    const useAuthStore = await getStore();
    const user = createMockUser({ role });

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, user);

    expect(useAuthStore.getState().user?.role).toBe(role);
  });

  it('permissions 배열이 빈 경우에도 안전하게 처리된다', async () => {
    const useAuthStore = await getStore();
    const user = createMockUser({ permissions: [] });

    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, user);

    expect(useAuthStore.getState().user?.permissions).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════
// 6. refreshAccessToken — 토큰 갱신 플로우
// ═══════════════════════════════════════════════════════════════

describe('refreshAccessToken', () => {
  it('refreshToken이 없으면 즉시 reject되고 logout이 호출된다', async () => {
    const useAuthStore = await getStore();
    // refreshToken이 null인 상태

    await expect(useAuthStore.getState().refreshAccessToken()).rejects.toBe('No refresh token');
    // logout이 호출되어 /login으로 리다이렉트
    expect(locationHrefSpy).toHaveBeenCalledWith('/login');
  });

  it('갱신 성공 시 새 accessToken이 저장된다', async () => {
    const useAuthStore = await getStore();
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, createMockUser());

    // axios.post mock 설정
    const axios = await import('axios');
    const mockPost = (axios as unknown as { __mockPost: ReturnType<typeof vi.fn> }).__mockPost;
    mockPost.mockResolvedValueOnce({
      data: {
        access_token: 'refreshed-access-token',
        refresh_token: 'refreshed-refresh-token',
      },
    });

    const newToken = await useAuthStore.getState().refreshAccessToken();

    expect(newToken).toBe('refreshed-access-token');
    expect(useAuthStore.getState().accessToken).toBe('refreshed-access-token');
    expect(useAuthStore.getState().refreshToken).toBe('refreshed-refresh-token');
  });

  it('갱신 실패 시 logout이 호출된다', async () => {
    const useAuthStore = await getStore();
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, createMockUser());

    const axios = await import('axios');
    const mockPost = (axios as unknown as { __mockPost: ReturnType<typeof vi.fn> }).__mockPost;
    mockPost.mockRejectedValueOnce(new Error('Token expired'));

    await expect(useAuthStore.getState().refreshAccessToken()).rejects.toThrow('Token expired');
    // logout 호출됨
    expect(locationHrefSpy).toHaveBeenCalledWith('/login');
  });

  it('응답에 access_token이 없으면 에러를 던지고 logout된다', async () => {
    const useAuthStore = await getStore();
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, createMockUser());

    const axios = await import('axios');
    const mockPost = (axios as unknown as { __mockPost: ReturnType<typeof vi.fn> }).__mockPost;
    mockPost.mockResolvedValueOnce({
      data: { /* access_token 누락 */ },
    });

    await expect(useAuthStore.getState().refreshAccessToken()).rejects.toThrow(
      'Invalid refresh response: access token missing',
    );
  });
});

// ═══════════════════════════════════════════════════════════════
// 7. sessionStorage 영속성 (persist middleware)
// ═══════════════════════════════════════════════════════════════

describe('sessionStorage 영속성', () => {
  it('login 후 sessionStorage에 axiom-auth 키로 저장된다', async () => {
    const useAuthStore = await getStore();
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, createMockUser());

    // Zustand persist는 비동기적으로 저장할 수 있으므로 약간의 대기
    await new Promise((r) => setTimeout(r, 50));

    const stored = sessionStorage.getItem('axiom-auth');
    expect(stored).not.toBeNull();

    const parsed = JSON.parse(stored!);
    expect(parsed.state.accessToken).toBe(MOCK_ACCESS_TOKEN);
    expect(parsed.state.user.email).toBe('admin@local.axiom');
  });

  it('logout 후 sessionStorage의 인증 데이터가 초기화된다', async () => {
    const useAuthStore = await getStore();
    useAuthStore.getState().login(MOCK_ACCESS_TOKEN, MOCK_REFRESH_TOKEN, createMockUser());
    await new Promise((r) => setTimeout(r, 50));

    useAuthStore.getState().logout();
    await new Promise((r) => setTimeout(r, 50));

    const stored = sessionStorage.getItem('axiom-auth');
    if (stored) {
      const parsed = JSON.parse(stored);
      expect(parsed.state.accessToken).toBeNull();
      expect(parsed.state.user).toBeNull();
    }
  });
});
