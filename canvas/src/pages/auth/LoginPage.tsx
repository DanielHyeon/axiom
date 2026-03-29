import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useTranslation } from 'react-i18next';
import { zodResolver } from '@hookform/resolvers/zod';
import axios from 'axios';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import type { User, UserRole } from '@/types/auth.types';
import { loginSchema, type LoginFormValues } from './loginSchema';

/* ──────────────────────────────────────────────
 * 타입 & 상수 (기존 인증 로직 100% 보존)
 * ────────────────────────────────────────────── */

interface LoginResponse {
  access_token?: string;
  refresh_token?: string;
  accessToken?: string;
  refreshToken?: string;
  user?: Partial<User>;
}

const coreBaseUrl = (import.meta.env.VITE_CORE_URL || 'http://localhost:9002').replace(/\/$/, '');
const authFallbackMock = import.meta.env.VITE_AUTH_FALLBACK_MOCK !== 'false';

/** Docker/개발용 테스트 계정 (Core SEED_DEV_USER=1 시 생성) */
const TEST_ACCOUNTS: { label: string; email: string; password: string }[] = [
  { label: 'Admin', email: 'admin@local.axiom', password: 'admin' },
];

/* ── JWT 디코딩 헬퍼 ── */
const decodeJwtPayload = (token: string): Record<string, unknown> | null => {
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    const normalized = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(normalized));
  } catch {
    return null;
  }
};

/* ── 토큰에서 User 객체 추출 ── */
const toUserFromToken = (accessToken: string, emailFallback: string): User => {
  const payload = decodeJwtPayload(accessToken);
  const role = String(payload?.role || 'viewer') as UserRole;
  const permissions = Array.isArray(payload?.permissions) ? (payload?.permissions as string[]) : [];
  const caseRolesValue = payload?.case_roles;
  const caseRoles =
    caseRolesValue && typeof caseRolesValue === 'object'
      ? (caseRolesValue as Record<string, 'owner' | 'reviewer' | 'viewer'>)
      : {};
  return {
    id: String(payload?.sub || 'unknown-user'),
    email: String(payload?.email || emailFallback),
    tenantId: String(payload?.tenant_id || '12345678-1234-5678-1234-567812345678'),
    role,
    permissions,
    caseRoles,
  };
};

/* ──────────────────────────────────────────────
 * 로그인 페이지 — .pen 디자인 기반 split-panel 레이아웃
 * 왼쪽: 브랜드 패널 (560px, 검은 배경)
 * 오른쪽: 폼 패널 (나머지, 흰 배경)
 * 모바일: 세로 스택 (브랜드 위, 폼 아래)
 * ────────────────────────────────────────────── */
export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const login = useAuthStore((state) => state.login);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const { register, handleSubmit, formState } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });
  const { errors } = formState;

  /* ── 로그인 제출 (서버 인증 → 실패 시 mock 폴백) ── */
  const onSubmit = async (data: LoginFormValues) => {
    setError(null);
    setSubmitting(true);
    const redirectTo = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname || '/dashboard';
    try {
      const response = await axios.post<LoginResponse>(`${coreBaseUrl}/api/v1/auth/login`, {
        email: data.email,
        password: data.password,
      });
      const payload = response.data || {};
      const accessToken = payload.access_token || payload.accessToken;
      const refreshToken = payload.refresh_token || payload.refreshToken;
      if (!accessToken || !refreshToken) throw new Error('Invalid login response');
      const user = payload.user
        ? ({ ...toUserFromToken(accessToken, data.email), ...payload.user } as User)
        : toUserFromToken(accessToken, data.email);
      login(accessToken, refreshToken, user);
      navigate(redirectTo, { replace: true });
      return;
    } catch (err: unknown) {
      if (!authFallbackMock) {
        const reason =
          (err as { response?: { data?: { detail?: string }; message?: string } })?.response?.data?.detail ||
          (err as Error)?.message ||
          t('auth.loginFailed');
        setError(String(reason));
        return;
      }
      // mock 인증 폴백 — 개발 환경에서 서버 없이 로그인 가능
      login('mock_token_admin', 'mock_refresh_token_admin', {
        id: 'usr-1',
        email: data.email,
        tenantId: '12345678-1234-5678-1234-567812345678',
        role: 'admin',
        caseRoles: {},
        permissions: ['case:read', 'case:write', 'document:write', 'watch:manage', 'olap:query', 'nl2sql:query'],
      });
      navigate(redirectTo, { replace: true });
    } finally {
      setSubmitting(false);
    }
  };

  /* ── 테스트 계정 원클릭 로그인 ── */
  const onTestAccount = (account: (typeof TEST_ACCOUNTS)[0]) => {
    onSubmit({ email: account.email, password: account.password });
  };

  return (
    <div className="flex min-h-screen w-full flex-col lg:flex-row">
      {/* ─── 왼쪽: 브랜드 패널 (검은 배경, 가운데 정렬) ─── */}
      <div className="flex w-full shrink-0 flex-col items-center justify-center bg-black px-8 py-12 lg:w-[560px] lg:py-16">
        {/* 로고 텍스트 — Sora 48px bold, 흰색, letterSpacing -2px */}
        <h1
          className="font-heading text-[48px] font-bold leading-none tracking-[-2px] text-white"
        >
          AXIOM
        </h1>

        {/* 태그라인 — Geist 18px, 다크모드 대응 */}
        <p className="mt-6 max-w-[320px] text-center font-secondary text-lg leading-[1.5] text-text-tertiary">
          Ontology-Driven{'\n'}Digital Twin Platform
        </p>

        {/* 설명 — Geist 14px, 다크모드 대응 플레이스홀더 색상 */}
        <p className="mt-4 max-w-[320px] text-center font-secondary text-sm leading-[1.6] text-text-placeholder">
          Enterprise data integration, analysis, and decision support powered by semantic intelligence.
        </p>
      </div>

      {/* ─── 오른쪽: 폼 패널 (흰 배경, 가운데 정렬) ─── */}
      <div className="flex flex-1 items-center justify-center bg-card p-8 lg:p-16">
        {/* 폼 카드 — 400px 너비, 24px 간격 세로 스택 */}
        <div className="flex w-full max-w-[400px] flex-col gap-6">
          {/* 제목 — Sora 24px semibold, 다크모드 대응 */}
          <div className="flex flex-col gap-2">
            <h2
              className="font-heading text-2xl font-semibold tracking-[-0.5px] text-foreground"
            >
              Sign in to Axiom
            </h2>
            {/* 부제 — Geist 14px, 다크모드 대응 보조 텍스트 */}
            <p className="font-secondary text-sm text-text-secondary">
              Enter your credentials to access the platform
            </p>
          </div>

          {/* ── 로그인 폼 ── */}
          <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
            {/* 이메일 필드 */}
            <div className="flex flex-col gap-1.5">
              <label
                className="font-secondary text-[13px] font-medium text-foreground"
                htmlFor="email"
              >
                Email
              </label>
              <input
                id="email"
                type="email"
                {...register('email')}
                className="h-11 w-full rounded-lg border border-border bg-card px-3.5 font-secondary text-sm text-foreground placeholder:text-text-placeholder focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all"
                placeholder="admin@local.axiom"
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email.message}</p>
              )}
            </div>

            {/* 비밀번호 필드 */}
            <div className="flex flex-col gap-1.5">
              <label
                className="font-secondary text-[13px] font-medium text-foreground"
                htmlFor="password"
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                {...register('password')}
                className="h-11 w-full rounded-lg border border-border bg-card px-3.5 font-secondary text-sm text-foreground placeholder:text-text-placeholder focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all"
                placeholder="••••••••"
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password.message}</p>
              )}
            </div>

            {/* 로그인 버튼 — 44px, primary, 8px radius */}
            <button
              type="submit"
              disabled={submitting}
              className="mt-1 h-11 w-full rounded-lg bg-primary font-secondary text-sm font-semibold text-primary-foreground transition-all duration-200 hover:bg-primary/90 disabled:opacity-50"
            >
              {submitting ? t('auth.loggingIn') : 'Sign In'}
            </button>

            {/* 에러 메시지 */}
            {error && (
              <p className="text-center text-sm text-destructive">{error}</p>
            )}
          </form>

          {/* ── 테스트 계정 (개발 환경) ── */}
          {TEST_ACCOUNTS.length > 0 && (
            <div className="border-t border-border pt-5">
              <p className="mb-2 font-secondary text-xs text-text-placeholder">
                {t('auth.testAccounts')}
              </p>
              <div className="flex flex-col gap-2">
                {TEST_ACCOUNTS.map((account) => (
                  <button
                    key={account.email}
                    type="button"
                    disabled={submitting}
                    onClick={() => onTestAccount(account)}
                    className="w-full rounded-lg border border-border bg-background px-4 py-2.5 font-secondary text-sm text-text-secondary transition-all duration-200 hover:bg-muted hover:text-foreground disabled:opacity-50"
                  >
                    {t('auth.loginAs', { label: account.label, email: account.email })}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 푸터 — Geist 12px, 다크모드 대응 */}
          <p className="text-center font-secondary text-xs text-text-placeholder">
            Axiom v5.2 — &copy; 2026 Axipient
          </p>
        </div>
      </div>
    </div>
  );
}
