/**
 * UserManagementPanel — 사용자 관리 패널
 * KAIR UserManagement.vue에서 이식
 * - 사용자 테이블 (이름, 이메일, 역할, 상태, 마지막 로그인)
 * - 사용자 추가/수정 다이얼로그
 * - 역할 변경 (인라인 셀렉트)
 * - 상태 변경 (활성/비활성/잠금)
 * - 삭제 확인 다이얼로그
 */

import React, { useState, useCallback } from 'react';
import {
  Search,
  Plus,
  Pencil,
  Trash2,
  RefreshCw,
  X,
  Loader2,
  UserPlus,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
  useRoles,
} from '../hooks/useSecurity';
import { useSecurityStore } from '../store/useSecurityStore';
import type {
  SecurityUser,
  UserStatus,
  CreateUserRequest,
  UpdateUserRequest,
} from '../types/security';
import type { UserRole } from '@/types/auth.types';

// ---------------------------------------------------------------------------
// 역할 배지 색상 매핑
// ---------------------------------------------------------------------------

const ROLE_VARIANT: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  admin: 'destructive',
  manager: 'default',
  attorney: 'default',
  analyst: 'secondary',
  engineer: 'secondary',
  staff: 'outline',
  viewer: 'outline',
};

// 역할 한글 라벨
const ROLE_LABEL: Record<string, string> = {
  admin: '관리자',
  manager: '매니저',
  attorney: '법무',
  analyst: '분석가',
  engineer: '엔지니어',
  staff: '직원',
  viewer: '뷰어',
};

// 상태 한글 라벨 + 스타일
const STATUS_CONFIG: Record<UserStatus, { label: string; className: string }> = {
  active: { label: '활성', className: 'bg-emerald-100 text-emerald-700' },
  inactive: { label: '비활성', className: 'bg-gray-100 text-gray-500' },
  locked: { label: '잠금', className: 'bg-red-100 text-red-600' },
};

// 사용 가능한 역할 목록
const ALL_ROLES: UserRole[] = ['admin', 'manager', 'attorney', 'analyst', 'engineer', 'staff', 'viewer'];
const ALL_STATUSES: UserStatus[] = ['active', 'inactive', 'locked'];

// ---------------------------------------------------------------------------
// 날짜 포맷 유틸
// ---------------------------------------------------------------------------

function formatDate(dateStr?: string): string {
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

// ---------------------------------------------------------------------------
// 아바타 이니셜 추출
// ---------------------------------------------------------------------------

function getInitial(user: SecurityUser): string {
  return (user.name || user.email || '?')[0].toUpperCase();
}

// ---------------------------------------------------------------------------
// UserManagementPanel 컴포넌트
// ---------------------------------------------------------------------------

export const UserManagementPanel: React.FC = () => {
  // 서버 상태
  const { data: users = [], isLoading, isError, error, refetch } = useUsers();
  const createMutation = useCreateUser();
  const updateMutation = useUpdateUser();
  const deleteMutation = useDeleteUser();

  // UI 상태
  const {
    editingUser,
    isUserDialogOpen,
    deletingUser,
    openCreateUserDialog,
    openEditUserDialog,
    closeUserDialog,
    openDeleteConfirm,
    closeDeleteConfirm,
  } = useSecurityStore();

  const [searchQuery, setSearchQuery] = useState('');

  // 폼 상태
  const [formData, setFormData] = useState<{
    email: string;
    name: string;
    password: string;
    role: UserRole;
    status: UserStatus;
  }>({
    email: '',
    name: '',
    password: '',
    role: 'viewer',
    status: 'active',
  });

  // 검색 필터
  const filteredUsers = users.filter((u) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      u.email.toLowerCase().includes(q) ||
      u.name.toLowerCase().includes(q) ||
      u.role.toLowerCase().includes(q)
    );
  });

  // 사용자 생성 다이얼로그 열기
  const handleOpenCreate = useCallback(() => {
    setFormData({ email: '', name: '', password: '', role: 'viewer', status: 'active' });
    openCreateUserDialog();
  }, [openCreateUserDialog]);

  // 사용자 수정 다이얼로그 열기
  const handleOpenEdit = useCallback(
    (user: SecurityUser) => {
      setFormData({
        email: user.email,
        name: user.name,
        password: '',
        role: user.role,
        status: user.status,
      });
      openEditUserDialog(user);
    },
    [openEditUserDialog],
  );

  // 폼 제출
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (editingUser) {
        // 수정
        const updateData: UpdateUserRequest = {};
        if (formData.name !== editingUser.name) updateData.name = formData.name;
        if (formData.role !== editingUser.role) updateData.role = formData.role;
        if (formData.status !== editingUser.status) updateData.status = formData.status;
        await updateMutation.mutateAsync({ userId: editingUser.id, data: updateData });
      } else {
        // 생성
        const createData: CreateUserRequest = {
          email: formData.email,
          name: formData.name,
          password: formData.password,
          role: formData.role,
        };
        await createMutation.mutateAsync(createData);
      }
      closeUserDialog();
    },
    [editingUser, formData, createMutation, updateMutation, closeUserDialog],
  );

  // 삭제 확인
  const handleConfirmDelete = useCallback(async () => {
    if (!deletingUser) return;
    await deleteMutation.mutateAsync(deletingUser.id);
    closeDeleteConfirm();
  }, [deletingUser, deleteMutation, closeDeleteConfirm]);

  // 인라인 역할 변경
  const handleInlineRoleChange = useCallback(
    (user: SecurityUser, newRole: string) => {
      updateMutation.mutate({
        userId: user.id,
        data: { role: newRole as UserRole },
      });
    },
    [updateMutation],
  );

  // 인라인 상태 변경
  const handleInlineStatusChange = useCallback(
    (user: SecurityUser, newStatus: string) => {
      updateMutation.mutate({
        userId: user.id,
        data: { status: newStatus as UserStatus },
      });
    },
    [updateMutation],
  );

  return (
    <div className="flex flex-col gap-5">
      {/* 툴바 */}
      <div className="flex items-center justify-between gap-4">
        {/* 검색 */}
        <div className="relative w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="사용자 검색..."
            className="pl-9"
          />
        </div>
        {/* 액션 버튼 */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="icon"
            onClick={() => refetch()}
            disabled={isLoading}
            aria-label="새로고침"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>
          <Button onClick={handleOpenCreate}>
            <Plus className="h-4 w-4 mr-1" />
            사용자 추가
          </Button>
        </div>
      </div>

      {/* 에러 상태 */}
      {isError && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>
            사용자 데이터를 불러오는 데 실패했습니다.{' '}
            {(error as Error)?.message || '백엔드 서버가 실행 중인지 확인하세요.'}
          </span>
        </div>
      )}

      {/* 로딩 상태 */}
      {isLoading && !isError && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-sm">데이터 로딩 중...</span>
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && !isError && users.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <UserPlus className="h-10 w-10" />
          <p className="font-medium">등록된 사용자가 없습니다</p>
          <span className="text-sm">사용자를 추가하여 시작하세요</span>
        </div>
      )}

      {/* 사용자 테이블 */}
      {!isLoading && !isError && users.length > 0 && (
        <div className="border border-border rounded-xl overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>사용자</TableHead>
                <TableHead>역할</TableHead>
                <TableHead>상태</TableHead>
                <TableHead>생성일</TableHead>
                <TableHead>마지막 로그인</TableHead>
                <TableHead className="w-24">작업</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredUsers.map((user) => (
                <TableRow key={user.id}>
                  {/* 사용자 정보 */}
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <div className="h-9 w-9 rounded-full bg-gradient-to-br from-primary to-indigo-500 text-white flex items-center justify-center text-sm font-semibold shrink-0">
                        {getInitial(user)}
                      </div>
                      <div className="flex flex-col">
                        <span className="font-medium text-foreground">{user.name}</span>
                        <span className="text-xs text-muted-foreground">{user.email}</span>
                      </div>
                    </div>
                  </TableCell>
                  {/* 역할 — 인라인 셀렉트 */}
                  <TableCell>
                    <Select
                      value={user.role}
                      onValueChange={(v) => handleInlineRoleChange(user, v)}
                    >
                      <SelectTrigger className="h-8 w-28 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ALL_ROLES.map((r) => (
                          <SelectItem key={r} value={r}>
                            {ROLE_LABEL[r] || r}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  {/* 상태 — 인라인 셀렉트 */}
                  <TableCell>
                    <Select
                      value={user.status}
                      onValueChange={(v) => handleInlineStatusChange(user, v)}
                    >
                      <SelectTrigger className="h-8 w-24 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ALL_STATUSES.map((s) => (
                          <SelectItem key={s} value={s}>
                            <span
                              className={`inline-flex items-center gap-1.5 ${STATUS_CONFIG[s].className} px-2 py-0.5 rounded-full text-xs font-medium`}
                            >
                              {STATUS_CONFIG[s].label}
                            </span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  {/* 날짜 */}
                  <TableCell className="text-muted-foreground text-sm">
                    {formatDate(user.created_at)}
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {formatDate(user.last_login)}
                  </TableCell>
                  {/* 액션 */}
                  <TableCell>
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleOpenEdit(user)}
                        aria-label="수정"
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                        onClick={() => openDeleteConfirm(user)}
                        aria-label="삭제"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {/* 검색 결과 없음 */}
              {filteredUsers.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    검색 결과가 없습니다
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 사용자 생성/수정 다이얼로그 */}
      {/* ----------------------------------------------------------------- */}
      {isUserDialogOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeUserDialog();
          }}
          role="dialog"
          aria-modal="true"
          aria-label={editingUser ? '사용자 수정' : '사용자 추가'}
        >
          <div className="bg-card border border-border rounded-2xl w-[480px] max-h-[90vh] overflow-hidden shadow-2xl">
            {/* 헤더 */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-border">
              <h3 className="text-lg font-semibold text-foreground">
                {editingUser ? '사용자 수정' : '사용자 추가'}
              </h3>
              <Button variant="ghost" size="icon" onClick={closeUserDialog}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            {/* 본문 */}
            <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-5 max-h-[60vh] overflow-y-auto">
              {/* 이메일 */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-muted-foreground">이메일</label>
                <Input
                  type="email"
                  placeholder="user@example.com"
                  value={formData.email}
                  onChange={(e) => setFormData((p) => ({ ...p, email: e.target.value }))}
                  disabled={!!editingUser}
                  required
                />
              </div>
              {/* 이름 */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-muted-foreground">이름</label>
                <Input
                  type="text"
                  placeholder="사용자명"
                  value={formData.name}
                  onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                  required
                />
              </div>
              {/* 비밀번호 (생성 시에만) */}
              {!editingUser && (
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-muted-foreground">비밀번호</label>
                  <Input
                    type="password"
                    placeholder="비밀번호 입력"
                    value={formData.password}
                    onChange={(e) => setFormData((p) => ({ ...p, password: e.target.value }))}
                    required
                  />
                </div>
              )}
              {/* 역할 선택 */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-muted-foreground">역할</label>
                <Select
                  value={formData.role}
                  onValueChange={(v) => setFormData((p) => ({ ...p, role: v as UserRole }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ALL_ROLES.map((r) => (
                      <SelectItem key={r} value={r}>
                        {ROLE_LABEL[r] || r}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {/* 상태 (수정 시에만) */}
              {editingUser && (
                <div className="flex flex-col gap-2">
                  <label className="text-sm font-medium text-muted-foreground">상태</label>
                  <Select
                    value={formData.status}
                    onValueChange={(v) => setFormData((p) => ({ ...p, status: v as UserStatus }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ALL_STATUSES.map((s) => (
                        <SelectItem key={s} value={s}>
                          {STATUS_CONFIG[s].label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </form>
            {/* 푸터 */}
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/30">
              <Button variant="outline" onClick={closeUserDialog}>
                취소
              </Button>
              <Button
                type="button"
                onClick={() => {
                  const fakeEvent = { preventDefault: () => {} } as React.FormEvent;
                  handleSubmit(fakeEvent);
                }}
                disabled={createMutation.isPending || updateMutation.isPending}
              >
                {(createMutation.isPending || updateMutation.isPending) && (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                )}
                {editingUser ? '수정' : '생성'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 삭제 확인 다이얼로그 */}
      {/* ----------------------------------------------------------------- */}
      {deletingUser && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
          onClick={(e) => {
            if (e.target === e.currentTarget) closeDeleteConfirm();
          }}
          role="alertdialog"
          aria-modal="true"
          aria-label="사용자 삭제 확인"
        >
          <div className="bg-card border border-border rounded-2xl w-[400px] overflow-hidden shadow-2xl">
            <div className="p-6 flex flex-col gap-4">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-destructive/10 flex items-center justify-center">
                  <AlertTriangle className="h-5 w-5 text-destructive" />
                </div>
                <div>
                  <h3 className="font-semibold text-foreground">사용자 삭제</h3>
                  <p className="text-sm text-muted-foreground">이 작업은 되돌릴 수 없습니다</p>
                </div>
              </div>
              <p className="text-sm text-foreground">
                <strong>{deletingUser.name}</strong> ({deletingUser.email}) 사용자를 정말
                삭제하시겠습니까?
              </p>
            </div>
            <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/30">
              <Button variant="outline" onClick={closeDeleteConfirm}>
                취소
              </Button>
              <Button
                variant="destructive"
                onClick={handleConfirmDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending && (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                )}
                삭제
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
