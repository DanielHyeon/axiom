/**
 * ChatMessageList — 채팅 메시지 목록 렌더링
 *
 * 사용자 메시지와 어시스턴트 메시지를 말풍선 형태로 보여준다.
 * 어시스턴트 메시지에 결과 테이블이 있으면 미리보기(5행)도 표시한다.
 */
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/features/nl2sql/hooks/useNl2SqlChat';

interface ChatMessageListProps {
  /** 채팅 메시지 배열 */
  messages: ChatMessage[];
}

export function ChatMessageList({ messages }: ChatMessageListProps) {
  const { t } = useTranslation();

  if (messages.length === 0) return null;

  return (
    <>
      {messages.map((msg, i) => (
        <div
          key={i}
          className={cn(
            'rounded p-4',
            msg.role === 'user'
              ? 'bg-[#F5F5F5] ml-12'
              : msg.role === 'assistant' && 'isHilQuestion' in msg && msg.isHilQuestion
                ? 'border border-amber-300 bg-amber-50/50 mr-12'
                : 'border border-[#E5E5E5] mr-12',
          )}
        >
          {/* 역할 라벨 */}
          <span className="text-[11px] font-medium text-foreground/60 font-[IBM_Plex_Mono] uppercase">
            {msg.role === 'user'
              ? t('nl2sql.chatUser')
              : msg.role === 'assistant' && 'isHilQuestion' in msg && msg.isHilQuestion
                ? t('nl2sql.chatHilQuestion')
                : t('nl2sql.chatAssistant')}
          </span>

          {/* 메시지 본문 */}
          <p className="text-sm text-black mt-1">
            {msg.content ||
              (msg.role === 'assistant' && 'streaming' in msg && msg.streaming
                ? t('common.processing')
                : '')}
          </p>

          {/* 어시스턴트 메시지에 결과가 있으면 미니 테이블 표시 */}
          {msg.role === 'assistant' && msg.result?.result && msg.result.result.columns.length > 0 && (
            <div className="mt-3 overflow-auto">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr>
                    {msg.result.result.columns.map((col) => (
                      <th
                        key={col.name}
                        className="bg-[#F5F5F5] px-3 py-2 text-left text-[11px] font-medium text-muted-foreground font-[IBM_Plex_Mono] uppercase border-b border-[#E5E5E5]"
                      >
                        {col.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(msg.result.result.rows ?? []).slice(0, 5).map((row, ri) => (
                    <tr key={ri} className="border-b border-[#E5E5E5] last:border-0">
                      {row.map((cell, ci) => (
                        <td
                          key={ci}
                          className="px-3 py-2 text-[13px] text-[#333] font-[IBM_Plex_Mono]"
                        >
                          {cell == null ? '--' : String(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {/* 5행 초과 시 안내 메시지 */}
              {(msg.result.result.rows?.length ?? 0) > 5 && (
                <p className="text-xs text-foreground/60 mt-2">
                  {t('nl2sql.topRowsOnly', { count: msg.result.result.row_count })}
                </p>
              )}
            </div>
          )}
        </div>
      ))}
    </>
  );
}
