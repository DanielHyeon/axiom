/**
 * 보안/감사 관리 도메인 타입 정의
 * KAIR SecurityGuardTab에서 이식한 RBAC, 감사 로그, 보안 정책 타입
 */

import type { UserRole } from '@/types/auth.types';

// ---------------------------------------------------------------------------
// 사용자 (User)
// ---------------------------------------------------------------------------

/** 사용자 상태 */
export type UserStatus = 'active' | 'inactive' | 'locked';

/** 사용자 엔티티 — Core 서비스 /api/v3/core/users 응답 */
export interface SecurityUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  status: UserStatus;
  last_login?: string;
  created_at: string;
}

/** 사용자 생성 요청 */
export interface CreateUserRequest {
  email: string;
  name: string;
  password: string;
  role: UserRole;
}

/** 사용자 수정 요청 (부분 업데이트) */
export interface UpdateUserRequest {
  name?: string;
  role?: UserRole;
  status?: UserStatus;
}

// ---------------------------------------------------------------------------
// 역할 (Role)
// ---------------------------------------------------------------------------

/** 권한 액션 타입 */
export type PermissionAction = 'read' | 'write' | 'delete' | 'admin';

/** 개별 권한 (리소스 + 액션 조합) */
export interface Permission {
  resource: string;
  actions: PermissionAction[];
}

/** 역할 엔티티 — Core 서비스 /api/v3/core/roles 응답 */
export interface Role {
  id: string;
  name: string;
  description?: string;
  permissions: Permission[];
  user_count: number;
  is_system?: boolean;
}

// ---------------------------------------------------------------------------
// 테이블 권한 (Table Permissions)
// ---------------------------------------------------------------------------

/** 테이블별 역할 접근 권한 */
export interface TablePermission {
  table_name: string;
  schema: string;
  roles: Record<string, { read: boolean; write: boolean }>;
}

// ---------------------------------------------------------------------------
// 감사 로그 (Audit Log)
// ---------------------------------------------------------------------------

/** 감사 로그 상태 */
export type AuditLogStatus = 'allowed' | 'denied' | 'rewritten';

/** 감사 로그 엔트리 — Oracle 서비스 /api/v3/core/audit-logs 응답 */
export interface AuditLogEntry {
  id: string;
  user_id: string;
  user_email: string;
  action: string;
  resource: string;
  details: string;
  ip_address: string;
  timestamp: string;
  status?: AuditLogStatus;
  original_sql?: string;
  rewritten_sql?: string;
  execution_time_ms?: number;
}

/** 감사 로그 조회 필터 */
export interface AuditLogFilter {
  user_email?: string;
  action?: string;
  status?: AuditLogStatus;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
}

/** 페이지네이션 응답 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ---------------------------------------------------------------------------
// 보안 정책 (Security Policy)
// ---------------------------------------------------------------------------

/** 보안 정책 타입 */
export type SecurityPolicyType =
  | 'query_limit'
  | 'column_mask'
  | 'column_filter'
  | 'query_rewrite'
  | 'rate_limit';

/** 보안 정책 엔티티 */
export interface SecurityPolicy {
  name: string;
  policy_type: SecurityPolicyType;
  description: string;
  rules_json: string;
  priority: number;
  is_active: boolean;
}

// ---------------------------------------------------------------------------
// UI 탭 상태
// ---------------------------------------------------------------------------

/** 보안 관리 서브탭 */
export type SecurityTab = 'users' | 'roles' | 'table-permissions' | 'audit-logs';
