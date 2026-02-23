import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import axios from 'axios';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import type { User, UserRole } from '@/types/auth.types';
import { loginSchema, type LoginFormValues } from './loginSchema';

interface LoginResponse {
  access_token?: string;
  refresh_token?: string;
  accessToken?: string;
  refreshToken?: string;
  user?: Partial<User>;
}

const coreBaseUrl = (import.meta.env.VITE_CORE_URL || 'http://localhost:8000').replace(/\/$/, '');
const authFallbackMock = import.meta.env.VITE_AUTH_FALLBACK_MOCK !== 'false';

/** Docker/개발용 테스트 계정 (Core SEED_DEV_USER=1 시 생성) */
const TEST_ACCOUNTS: { label: string; email: string; password: string }[] = [
  { label: 'Admin', email: 'admin@local.axiom', password: 'admin' },
];

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

export function LoginPage() {
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
          '로그인에 실패했습니다.';
        setError(String(reason));
        return;
      }
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

  const onTestAccount = (account: (typeof TEST_ACCOUNTS)[0]) => {
    onSubmit({ email: account.email, password: account.password });
  };

  return (
    <div className="relative flex h-screen w-full items-center justify-center bg-background px-4 overflow-hidden">
      {/* Ambient gradient blobs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-1/4 left-1/3 h-[500px] w-[500px] rounded-full bg-primary/8 blur-[100px]" />
        <div className="absolute bottom-1/4 right-1/4 h-[400px] w-[400px] rounded-full bg-blue-500/5 blur-[80px]" />
      </div>

      <div className="glass-card relative w-full max-w-sm rounded-2xl p-8">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-blue-400 shadow-lg shadow-primary/25">
            <span className="text-lg font-bold text-white">A</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground mb-2">Axiom Canvas</h1>
          <p className="text-sm text-muted-foreground">시스템에 접속하려면 로그인하세요</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-foreground" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              {...register('email')}
              className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 transition-all"
              placeholder="name@example.com"
            />
            {errors.email && <p className="text-sm text-destructive">{errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <label className="text-[13px] font-medium text-foreground" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              {...register('password')}
              className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 transition-all"
              placeholder="••••••••"
            />
            {errors.password && <p className="text-sm text-destructive">{errors.password.message}</p>}
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2.5 text-sm font-medium transition-all duration-200 mt-2 disabled:opacity-50"
          >
            {submitting ? '로그인 중...' : '로그인'}
          </button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>

        {TEST_ACCOUNTS.length > 0 && (
          <div className="mt-6 border-t border-border/30 pt-6">
            <p className="text-xs text-muted-foreground mb-2">테스트 계정 (Docker/개발)</p>
            <div className="flex flex-col gap-2">
              {TEST_ACCOUNTS.map((account) => (
                <button
                  key={account.email}
                  type="button"
                  disabled={submitting}
                  onClick={() => onTestAccount(account)}
                  className="w-full rounded-lg border border-border/30 bg-muted/40 px-4 py-2.5 text-sm text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-all duration-200 disabled:opacity-50"
                >
                  {account.label}으로 로그인 ({account.email})
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
