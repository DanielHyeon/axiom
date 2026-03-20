/**
 * UserTable — 사용자 목록 테이블
 *
 * 사용자 정보(이름, 이메일, 역할, 상태, 날짜)를 테이블 형태로 표시한다.
 * 역할과 상태는 인라인 셀렉트로 바로 변경 가능.
 * 각 행에 수정/삭제 버튼을 제공.
 */

import React from 'react';
import { Pencil, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
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
import type { SecurityUser } from '../../types/security';
import {
  ROLE_LABEL,
  STATUS_CONFIG,
  ALL_ROLES,
  ALL_STATUSES,
  formatDate,
  getInitial,
} from './constants';

interface UserTableProps {
  /** 필터링된 사용자 목록 */
  users: SecurityUser[];
  /** 역할 인라인 변경 핸들러 */
  onRoleChange: (user: SecurityUser, newRole: string) => void;
  /** 상태 인라인 변경 핸들러 */
  onStatusChange: (user: SecurityUser, newStatus: string) => void;
  /** 사용자 수정 다이얼로그 열기 */
  onEdit: (user: SecurityUser) => void;
  /** 사용자 삭제 확인 다이얼로그 열기 */
  onDelete: (user: SecurityUser) => void;
}

export const UserTable: React.FC<UserTableProps> = ({
  users,
  onRoleChange,
  onStatusChange,
  onEdit,
  onDelete,
}) => {
  return (
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
          {users.map((user) => (
            <TableRow key={user.id}>
              {/* 사용자 정보: 아바타 + 이름 + 이메일 */}
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
                  onValueChange={(v) => onRoleChange(user, v)}
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
                  onValueChange={(v) => onStatusChange(user, v)}
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
              {/* 날짜 컬럼 */}
              <TableCell className="text-muted-foreground text-sm">
                {formatDate(user.created_at)}
              </TableCell>
              <TableCell className="text-muted-foreground text-sm">
                {formatDate(user.last_login)}
              </TableCell>
              {/* 액션 버튼 */}
              <TableCell>
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => onEdit(user)}
                    aria-label="수정"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                    onClick={() => onDelete(user)}
                    aria-label="삭제"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
          {/* 검색 결과 없음 */}
          {users.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                검색 결과가 없습니다
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
};
