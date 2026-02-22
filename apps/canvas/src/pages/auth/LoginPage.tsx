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

  const { register, handleSubmit, formState } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });
  const { errors, isSubmitting } = formState;

  const onSubmit = async (data: LoginFormValues) => {
    setError(null);
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
    }
  };

  return (
    <div className="flex h-screen w-full items-center justify-center bg-neutral-950 px-4">
      <div className="w-full max-w-sm rounded-lg border border-neutral-800 bg-neutral-900 p-8 shadow-xl">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight text-white mb-2">Axiom Canvas</h1>
          <p className="text-sm text-neutral-400">Enter your credentials to access the system</p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-neutral-300" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              {...register('email')}
              className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="name@example.com"
            />
            {errors.email && <p className="text-sm text-red-400">{errors.email.message}</p>}
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-neutral-300" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              {...register('password')}
              className="w-full rounded-md border border-neutral-700 bg-neutral-950 px-3 py-2 text-sm text-white placeholder:text-neutral-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••"
            />
            {errors.password && <p className="text-sm text-red-400">{errors.password.message}</p>}
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-white text-black hover:bg-neutral-200 px-4 py-2 text-sm font-medium transition-colors mt-2"
          >
            {isSubmitting ? 'Signing In...' : 'Sign In'}
          </button>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </form>
      </div>
    </div>
  );
}
