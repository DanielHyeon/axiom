/**
 * 사용자 관리 상수 정의
 *
 * 역할 배지 색상, 역할/상태 라벨, 날짜 포맷 유틸 등
 * UserManagementPanel 하위 컴포넌트들이 공통으로 사용하는 값.
 */
import type { UserStatus } from '../../types/security';
import type { UserRole } from '@/types/auth.types';
import type { SecurityUser } from '../../types/security';

// ── 역할 한글 라벨 ──

export const ROLE_LABEL: Record<string, string> = {
  admin: '관리자',
  manager: '매니저',
  attorney: '법무',
  analyst: '분석가',
  engineer: '엔지니어',
  staff: '직원',
  viewer: '뷰어',
};

// ── 상태 한글 라벨 + 스타일 ──

export const STATUS_CONFIG: Record<UserStatus, { label: string; className: string }> = {
  active: { label: '활성', className: 'bg-emerald-100 text-emerald-700' },
  inactive: { label: '비활성', className: 'bg-gray-100 text-gray-500' },
  locked: { label: '잠금', className: 'bg-red-100 text-red-600' },
};

// ── 사용 가능한 역할/상태 목록 ──

export const ALL_ROLES: UserRole[] = ['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer'];
export const ALL_STATUSES: UserStatus[] = ['active', 'inactive', 'locked'];

// ── 유틸리티 함수 ──

/** 날짜 문자열을 한국어 형식으로 포맷 */
export function formatDate(dateStr?: string): string {
  if (!dateStr) return '-';
  try {
    return new Date(dateStr).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

/** 사용자 이름 또는 이메일에서 아바타 이니셜 추출 */
export function getInitial(user: SecurityUser): string {
  return (user.name || user.email || '?')[0].toUpperCase();
}
