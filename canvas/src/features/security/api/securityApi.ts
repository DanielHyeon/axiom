/**
 * 보안 관리 API 클라이언트
 * Core 서비스의 RBAC 사용자/역할/감사 로그 엔드포인트 호출
 */

import { coreApi } from '@/lib/api/clients';
import type {
  SecurityUser,
  CreateUserRequest,
  UpdateUserRequest,
  Role,
  AuditLogEntry,
  AuditLogFilter,
  PaginatedResponse,
  TablePermission,
} from '../types/security';

// ---------------------------------------------------------------------------
// 사용자 관리 API
// ---------------------------------------------------------------------------

/** 사용자 목록 조회 */
export async function getUsers(): Promise<SecurityUser[]> {
  const res = await coreApi.get('/api/v3/core/users');
  return res as unknown as SecurityUser[];
}

/** 사용자 생성 */
export async function createUser(data: CreateUserRequest): Promise<SecurityUser> {
  const res = await coreApi.post('/api/v3/core/users', data);
  return res as unknown as SecurityUser;
}

/** 사용자 수정 (역할/상태 변경) */
export async function updateUser(
  userId: string,
  data: UpdateUserRequest,
): Promise<SecurityUser> {
  const res = await coreApi.patch(`/api/v3/core/users/${userId}`, data);
  return res as unknown as SecurityUser;
}

/** 사용자 삭제 */
export async function deleteUser(userId: string): Promise<void> {
  await coreApi.delete(`/api/v3/core/users/${userId}`);
}

// ---------------------------------------------------------------------------
// 역할 관리 API
// ---------------------------------------------------------------------------

/** 역할 목록 조회 */
export async function getRoles(): Promise<Role[]> {
  const res = await coreApi.get('/api/v3/core/roles');
  return res as unknown as Role[];
}

// ---------------------------------------------------------------------------
// 테이블 권한 API
// ---------------------------------------------------------------------------

/** 테이블 권한 매트릭스 조회 */
export async function getTablePermissions(): Promise<TablePermission[]> {
  const res = await coreApi.get('/api/v3/core/table-permissions');
  return res as unknown as TablePermission[];
}

/** 테이블 권한 업데이트 */
export async function updateTablePermission(
  tableName: string,
  schema: string,
  roles: Record<string, { read: boolean; write: boolean }>,
): Promise<void> {
  await coreApi.patch('/api/v3/core/table-permissions', {
    table_name: tableName,
    schema,
    roles,
  });
}

// ---------------------------------------------------------------------------
// 감사 로그 API
// ---------------------------------------------------------------------------

/** 감사 로그 조회 (페이지네이션 + 필터) */
export async function getAuditLogs(
  filter?: AuditLogFilter,
): Promise<PaginatedResponse<AuditLogEntry>> {
  // 쿼리 파라미터 구성
  const params = new URLSearchParams();
  if (filter?.user_email) params.set('user_email', filter.user_email);
  if (filter?.action) params.set('action', filter.action);
  if (filter?.status) params.set('status', filter.status);
  if (filter?.date_from) params.set('date_from', filter.date_from);
  if (filter?.date_to) params.set('date_to', filter.date_to);
  if (filter?.page) params.set('page', String(filter.page));
  if (filter?.page_size) params.set('page_size', String(filter.page_size));

  const query = params.toString();
  const url = `/api/v3/core/audit-logs${query ? `?${query}` : ''}`;
  const res = await coreApi.get(url);
  return res as unknown as PaginatedResponse<AuditLogEntry>;
}
