/**
 * DeleteConfirmDialog — 사용자 삭제 확인 다이얼로그
 *
 * 사용자 삭제 전 최종 확인을 받는 경고 다이얼로그.
 * 삭제 대상 사용자의 이름과 이메일을 표시하고,
 * 되돌릴 수 없다는 경고 메시지를 노출한다.
 */

import React from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { SecurityUser } from '../../types/security';

interface DeleteConfirmDialogProps {
  /** 삭제 대상 사용자 */
  user: SecurityUser;
  /** 삭제 확인 핸들러 */
  onConfirm: () => void;
  /** 다이얼로그 닫기 핸들러 */
  onClose: () => void;
  /** 삭제 처리 중 여부 */
  isPending: boolean;
}

export const DeleteConfirmDialog: React.FC<DeleteConfirmDialogProps> = ({
  user,
  onConfirm,
  onClose,
  isPending,
}) => {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="alertdialog"
      aria-modal="true"
      aria-label="사용자 삭제 확인"
    >
      <div className="bg-card border border-border rounded-2xl w-[400px] overflow-hidden shadow-2xl">
        <div className="p-6 flex flex-col gap-4">
          {/* 경고 아이콘 + 제목 */}
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-destructive/10 flex items-center justify-center">
              <AlertTriangle className="h-5 w-5 text-destructive" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">사용자 삭제</h3>
              <p className="text-sm text-muted-foreground">이 작업은 되돌릴 수 없습니다</p>
            </div>
          </div>
          {/* 삭제 대상 안내 */}
          <p className="text-sm text-foreground">
            <strong>{user.name}</strong> ({user.email}) 사용자를 정말
            삭제하시겠습니까?
          </p>
        </div>
        {/* 푸터 */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-border bg-muted/30">
          <Button variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
            disabled={isPending}
          >
            {isPending && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
            삭제
          </Button>
        </div>
      </div>
    </div>
  );
};
