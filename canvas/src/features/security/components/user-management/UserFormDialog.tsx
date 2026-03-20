/**
 * UserFormDialog — 사용자 생성/수정 다이얼로그
 *
 * 생성 모드: 이메일, 이름, 비밀번호, 역할을 입력받아 새 사용자를 생성.
 * 수정 모드: 이름, 역할, 상태를 변경 (이메일은 읽기 전용).
 * editingUser가 null이면 생성 모드, 있으면 수정 모드로 동작.
 */

import React from 'react';
import { X, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import type { SecurityUser, UserStatus } from '../../types/security';
import type { UserRole } from '@/types/auth.types';
import { ROLE_LABEL, STATUS_CONFIG, ALL_ROLES, ALL_STATUSES } from './constants';

export interface UserFormData {
  email: string;
  name: string;
  password: string;
  role: UserRole;
  status: UserStatus;
}

interface UserFormDialogProps {
  /** null이면 생성 모드, 있으면 수정 모드 */
  editingUser: SecurityUser | null;
  /** 폼 데이터 */
  formData: UserFormData;
  /** 폼 데이터 변경 핸들러 */
  onFormDataChange: (data: UserFormData) => void;
  /** 폼 제출 핸들러 */
  onSubmit: (e: React.FormEvent) => void;
  /** 다이얼로그 닫기 핸들러 */
  onClose: () => void;
  /** 제출 중 여부 */
  isPending: boolean;
}

export const UserFormDialog: React.FC<UserFormDialogProps> = ({
  editingUser,
  formData,
  onFormDataChange,
  onSubmit,
  onClose,
  isPending,
}) => {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
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
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* 폼 본문 + 푸터를 하나의 form으로 감싸 native validation 활성화 */}
        <form onSubmit={onSubmit}>
          <div className="p-6 flex flex-col gap-5 max-h-[60vh] overflow-y-auto">
            {/* 이메일 */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-muted-foreground">이메일</label>
              <Input
                type="email"
                placeholder="user@example.com"
                value={formData.email}
                onChange={(e) => onFormDataChange({ ...formData, email: e.target.value })}
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
                onChange={(e) => onFormDataChange({ ...formData, name: e.target.value })}
                required
              />
            </div>
            {/* 비밀번호 (생성 시에만 표시) */}
            {!editingUser && (
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-muted-foreground">비밀번호</label>
                <Input
                  type="password"
                  placeholder="비밀번호 입력 (최소 8자)"
                  value={formData.password}
                  onChange={(e) => onFormDataChange({ ...formData, password: e.target.value })}
                  required
                  minLength={8}
                />
              </div>
            )}
            {/* 역할 선택 */}
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-muted-foreground">역할</label>
              <Select
                value={formData.role}
                onValueChange={(v) => onFormDataChange({ ...formData, role: v as UserRole })}
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
            {/* 상태 (수정 시에만 표시) */}
            {editingUser && (
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-muted-foreground">상태</label>
                <Select
                  value={formData.status}
                  onValueChange={(v) => onFormDataChange({ ...formData, status: v as UserStatus })}
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
          </div>

          {/* 푸터 — form 내부에 배치하여 type="submit"이 native validation을 트리거 */}
          <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/30">
            <Button type="button" variant="outline" onClick={onClose}>
              취소
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
              {editingUser ? '수정' : '생성'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};
