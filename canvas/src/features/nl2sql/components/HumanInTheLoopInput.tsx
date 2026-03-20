/**
 * HumanInTheLoopInput — 에이전트가 사용자 입력을 요청할 때 표시하는 UI.
 *
 * 지원하는 입력 유형:
 *  - select: 라디오 버튼 그룹 (에이전트가 제시하는 옵션 중 선택)
 *  - confirm: 예/아니오 버튼
 *  - text: 자유 텍스트 입력
 *
 * 에이전트 질문과 컨텍스트를 카드 형태로 표시하고,
 * 사용자 답변을 session_state와 함께 부모로 전달한다.
 */
import { useState } from 'react';
import type { HilRequest, HilResponse } from '@/features/nl2sql/types/nl2sql';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MessageSquare, Send, X, HelpCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface HumanInTheLoopInputProps {
  /** 에이전트가 보낸 HIL 요청 데이터 */
  request: HilRequest;
  /** 사용자 답변 제출 핸들러 */
  onSubmit: (response: HilResponse) => void;
  /** 취소 (HIL 세션 중단) 핸들러 */
  onCancel: () => void;
  /** 제출 진행 중 여부 */
  isSubmitting: boolean;
}

export function HumanInTheLoopInput({
  request,
  onSubmit,
  onCancel,
  isSubmitting,
}: HumanInTheLoopInputProps) {
  // 선택된 값 (select/confirm) 또는 입력 텍스트
  const [selectedValue, setSelectedValue] = useState('');
  const [textValue, setTextValue] = useState('');

  /** 응답 제출 */
  const handleSubmit = () => {
    let response = '';
    if (request.type === 'select') {
      response = selectedValue;
    } else if (request.type === 'confirm') {
      response = selectedValue; // 'yes' | 'no'
    } else {
      response = textValue.trim();
    }
    if (!response) return;

    onSubmit({
      session_state: request.session_state,
      user_response: response,
    });
  };

  /** 제출 버튼 비활성화 조건 */
  const isDisabled =
    isSubmitting ||
    (request.type === 'select' && !selectedValue) ||
    (request.type === 'confirm' && !selectedValue) ||
    (request.type === 'text' && !textValue.trim());

  return (
    <Card
      className={cn(
        'border-amber-300 bg-amber-50/50 animate-in fade-in slide-in-from-bottom-2 duration-300',
      )}
    >
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-amber-800">
          <HelpCircle className="h-4 w-4" />
          에이전트가 추가 정보를 요청합니다
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 에이전트 질문 */}
        <div className="flex items-start gap-2">
          <MessageSquare className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
          <p className="text-sm text-amber-900 leading-relaxed">{request.question}</p>
        </div>

        {/* 컨텍스트 (있는 경우) */}
        {request.context && (
          <div className="rounded bg-amber-100/50 px-3 py-2 text-xs text-amber-700 font-[IBM_Plex_Mono]">
            {request.context}
          </div>
        )}

        {/* 입력 유형별 UI */}
        {request.type === 'select' && request.options && (
          <div className="space-y-2">
            {request.options.map((opt) => (
              <label
                key={opt.value}
                className={cn(
                  'flex items-start gap-3 rounded-md border px-3 py-2.5 cursor-pointer transition-colors',
                  selectedValue === opt.value
                    ? 'border-amber-500 bg-amber-100/70'
                    : 'border-amber-200 bg-white hover:border-amber-300',
                )}
              >
                <input
                  type="radio"
                  name="hil-select"
                  value={opt.value}
                  checked={selectedValue === opt.value}
                  onChange={() => setSelectedValue(opt.value)}
                  className="mt-0.5 accent-amber-600"
                />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-amber-900">{opt.label}</span>
                  {opt.description && (
                    <p className="text-xs text-amber-600 mt-0.5">{opt.description}</p>
                  )}
                </div>
              </label>
            ))}
          </div>
        )}

        {request.type === 'confirm' && (
          <div className="flex gap-3">
            <Button
              variant={selectedValue === 'yes' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedValue('yes')}
              className={cn(
                selectedValue === 'yes' && 'bg-amber-600 hover:bg-amber-700 text-white',
              )}
            >
              예
            </Button>
            <Button
              variant={selectedValue === 'no' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedValue('no')}
              className={cn(
                selectedValue === 'no' && 'bg-amber-600 hover:bg-amber-700 text-white',
              )}
            >
              아니오
            </Button>
          </div>
        )}

        {request.type === 'text' && (
          <Input
            placeholder="추가 정보를 입력하세요..."
            value={textValue}
            onChange={(e) => setTextValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !isDisabled) handleSubmit();
            }}
            className="border-amber-300 focus-visible:ring-amber-400"
          />
        )}

        {/* 액션 버튼 */}
        <div className="flex items-center justify-end gap-2 pt-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={onCancel}
            disabled={isSubmitting}
            className="text-amber-700 hover:text-amber-900 hover:bg-amber-100"
          >
            <X className="h-3.5 w-3.5 mr-1" />
            중단
          </Button>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={isDisabled}
            className="bg-amber-600 hover:bg-amber-700 text-white"
          >
            <Send className="h-3.5 w-3.5 mr-1" />
            {isSubmitting ? '전송 중...' : '답변 전송'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
