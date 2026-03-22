/**
 * ConversationIndicator — 멀티턴 대화 상태 표시 컴포넌트
 *
 * 채팅 영역 상단에 현재 대화 상태를 표시한다.
 * 멀티턴 대화 진행 중일 때 턴 수와 "새 대화" 버튼을 보여준다.
 * 단일 턴(첫 번째 질문)일 때는 아무것도 렌더링하지 않는다.
 */
import { MessageSquare, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

// ─── Props ────────────────────────────────────────────────

interface ConversationIndicatorProps {
  /** 현재 턴 수 */
  turnCount: number;
  /** 멀티턴 대화 여부 */
  isMultiTurn: boolean;
  /** 새 대화 시작 — 대화 상태 초기화 + 채팅 메시지 클리어 */
  onNewConversation: () => void;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function ConversationIndicator({
  turnCount,
  isMultiTurn,
  onNewConversation,
}: ConversationIndicatorProps) {
  // 멀티턴이 아니면 표시하지 않음
  if (!isMultiTurn) return null;

  return (
    <div
      className={cn(
        'flex items-center justify-between',
        'rounded-lg border border-indigo-200 bg-indigo-50/50',
        'px-3 py-2',
      )}
    >
      {/* 대화 상태 배지 */}
      <div className="flex items-center gap-2">
        <MessageSquare className="h-3.5 w-3.5 text-indigo-500" />
        <Badge variant="outline" className="text-[11px] font-[IBM_Plex_Mono] border-indigo-300 text-indigo-600">
          대화 {turnCount}턴 진행 중
        </Badge>
      </div>

      {/* 새 대화 버튼 */}
      <button
        type="button"
        onClick={onNewConversation}
        className={cn(
          'flex items-center gap-1',
          'px-2 py-1 rounded',
          'text-[11px] font-semibold font-[IBM_Plex_Mono]',
          'text-indigo-500 hover:text-indigo-700 hover:bg-indigo-100',
          'transition-colors',
        )}
      >
        <X className="h-3 w-3" />
        새 대화
      </button>
    </div>
  );
}
