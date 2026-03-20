/**
 * UserManagementPanel — 사용자 관리 패널 (오케스트레이터)
 *
 * 사용자 목록 테이블, 생성/수정 다이얼로그, 삭제 확인 다이얼로그를
 * 조합하여 전체 사용자 관리 UI를 구성한다.
 * 실제 UI는 user-management/ 디렉토리의 개별 컴포넌트에 위임.
 */

import React, { useState, useCallback } from 'react';
import { Search, Plus, RefreshCw, Loader2, UserPlus, AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  useUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
} from '../hooks/useSecurity';
import { useSecurityStore } from '../store/useSecurityStore';
import type { SecurityUser, UserStatus, CreateUserRequest, UpdateUserRequest } from '../types/security';
import type { UserRole } from '@/types/auth.types';
import { UserTable } from './user-management/UserTable';
import { UserFormDialog } from './user-management/UserFormDialog';
import type { UserFormData } from './user-management/UserFormDialog';
import { DeleteConfirmDialog } from './user-management/DeleteConfirmDialog';

export const UserManagementPanel: React.FC = () => {
  // 서버 상태
  const { data: users = [], isLoading, isError, error, refetch } = useUsers();
  const createMutation = useCreateUser();
  const updateMutation = useUpdateUser();
  const deleteMutation = useDeleteUser();

  // UI 상태 (Zustand store)
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
  const [formData, setFormData] = useState<UserFormData>({
    email: '',
    name: '',
    password: '',
    role: 'viewer',
    status: 'active',
  });

  // 검색 필터 적용
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

  // 폼 제출 (생성 또는 수정)
  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (editingUser) {
        const updateData: UpdateUserRequest = {};
        if (formData.name !== editingUser.name) updateData.name = formData.name;
        if (formData.role !== editingUser.role) updateData.role = formData.role;
        if (formData.status !== editingUser.status) updateData.status = formData.status;
        await updateMutation.mutateAsync({ userId: editingUser.id, data: updateData });
      } else {
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
      updateMutation.mutate({ userId: user.id, data: { role: newRole as UserRole } });
    },
    [updateMutation],
  );

  // 인라인 상태 변경
  const handleInlineStatusChange = useCallback(
    (user: SecurityUser, newStatus: string) => {
      updateMutation.mutate({ userId: user.id, data: { status: newStatus as UserStatus } });
    },
    [updateMutation],
  );

  return (
    <div className="flex flex-col gap-5">
      {/* 툴바: 검색 + 액션 버튼 */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative w-80">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="사용자 검색..."
            className="pl-9"
          />
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()} disabled={isLoading} aria-label="새로고침">
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
        <UserTable
          users={filteredUsers}
          onRoleChange={handleInlineRoleChange}
          onStatusChange={handleInlineStatusChange}
          onEdit={handleOpenEdit}
          onDelete={openDeleteConfirm}
        />
      )}

      {/* 사용자 생성/수정 다이얼로그 */}
      {isUserDialogOpen && (
        <UserFormDialog
          editingUser={editingUser}
          formData={formData}
          onFormDataChange={setFormData}
          onSubmit={handleSubmit}
          onClose={closeUserDialog}
          isPending={createMutation.isPending || updateMutation.isPending}
        />
      )}

      {/* 삭제 확인 다이얼로그 */}
      {deletingUser && (
        <DeleteConfirmDialog
          user={deletingUser}
          onConfirm={handleConfirmDelete}
          onClose={closeDeleteConfirm}
          isPending={deleteMutation.isPending}
        />
      )}
    </div>
  );
};
