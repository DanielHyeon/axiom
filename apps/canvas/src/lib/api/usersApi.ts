import { coreApi } from './clients';
import type { User } from '@/types/auth.types';

export interface CurrentUserResponse {
  id: string;
  email: string | null;
  role: string;
  tenantId: string;
  permissions: string[];
  caseRoles: Record<string, string>;
}

function toUser(r: CurrentUserResponse): User {
  return {
    id: r.id,
    email: r.email ?? '',
    role: r.role as User['role'],
    tenantId: r.tenantId,
    permissions: r.permissions ?? [],
    caseRoles: (r.caseRoles ?? {}) as User['caseRoles'],
  };
}

export async function getCurrentUser(): Promise<User> {
  const response = await coreApi.get<CurrentUserResponse>('/api/v1/users/me');
  return toUser(response as CurrentUserResponse);
}
