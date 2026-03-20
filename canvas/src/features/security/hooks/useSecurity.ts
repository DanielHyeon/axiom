/**
 * 보안 관리 TanStack Query 훅
 * 사용자 목록, 역할, 감사 로그 등을 서버 상태로 관리
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getUsers,
  createUser,
  updateUser,
  deleteUser,
  getRoles,
  getAuditLogs,
  getTablePermissions,
  updateTablePermission,
} from '../api/securityApi';
import type {
  CreateUserRequest,
  UpdateUserRequest,
  AuditLogFilter,
} from '../types/security';

// ---------------------------------------------------------------------------
// 쿼리 키 상수 — 캐시 무효화에 사용
// ---------------------------------------------------------------------------

export const securityKeys = {
  /** 전체 보안 도메인 */
  all: ['security'] as const,
  /** 사용자 목록 */
  users: () => [...securityKeys.all, 'users'] as const,
  /** 역할 목록 */
  roles: () => [...securityKeys.all, 'roles'] as const,
  /** 감사 로그 (필터 포함) */
  auditLogs: (filter?: AuditLogFilter) =>
    [...securityKeys.all, 'audit-logs', filter ?? {}] as const,
  /** 테이블 권한 */
  tablePermissions: () => [...securityKeys.all, 'table-permissions'] as const,
};

// ---------------------------------------------------------------------------
// 사용자 관련 훅
// ---------------------------------------------------------------------------

/** 사용자 목록 조회 */
export function useUsers() {
  return useQuery({
    queryKey: securityKeys.users(),
    queryFn: getUsers,
    staleTime: 30_000, // 30초 캐시
  });
}

/** 사용자 생성 뮤테이션 */
export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateUserRequest) => createUser(data),
    onSuccess: () => {
      // 사용자 목록 + 역할(user_count 변경) 캐시 무효화
      qc.invalidateQueries({ queryKey: securityKeys.users() });
      qc.invalidateQueries({ queryKey: securityKeys.roles() });
    },
  });
}

/** 사용자 수정 뮤테이션 */
export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: UpdateUserRequest }) =>
      updateUser(userId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: securityKeys.users() });
      qc.invalidateQueries({ queryKey: securityKeys.roles() });
    },
  });
}

/** 사용자 삭제 뮤테이션 */
export function useDeleteUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => deleteUser(userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: securityKeys.users() });
      qc.invalidateQueries({ queryKey: securityKeys.roles() });
    },
  });
}

// ---------------------------------------------------------------------------
// 역할 관련 훅
// ---------------------------------------------------------------------------

/** 역할 목록 조회 */
export function useRoles() {
  return useQuery({
    queryKey: securityKeys.roles(),
    queryFn: getRoles,
    staleTime: 60_000, // 1분 캐시 — 역할은 자주 바뀌지 않음
  });
}

// ---------------------------------------------------------------------------
// 테이블 권한 관련 훅
// ---------------------------------------------------------------------------

/** 테이블 권한 매트릭스 조회 */
export function useTablePermissions() {
  return useQuery({
    queryKey: securityKeys.tablePermissions(),
    queryFn: getTablePermissions,
    staleTime: 60_000,
  });
}

/** 테이블 권한 업데이트 뮤테이션 */
export function useUpdateTablePermission() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      tableName,
      schema,
      roles,
    }: {
      tableName: string;
      schema: string;
      roles: Record<string, { read: boolean; write: boolean }>;
    }) => updateTablePermission(tableName, schema, roles),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: securityKeys.tablePermissions() });
    },
  });
}

// ---------------------------------------------------------------------------
// 감사 로그 관련 훅
// ---------------------------------------------------------------------------

/** 감사 로그 조회 (페이지네이션 + 필터) */
export function useAuditLogs(filter?: AuditLogFilter) {
  return useQuery({
    queryKey: securityKeys.auditLogs(filter),
    queryFn: () => getAuditLogs(filter),
    staleTime: 10_000, // 10초 — 감사 로그는 자주 갱신
  });
}
