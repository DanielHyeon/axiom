/**
 * WatchAgentPanel — LLM 기반 모니터링 규칙 자동 생성 패널
 *
 * 채팅 형태 인터페이스:
 * 1. 사용자가 모니터링 대상을 자연어로 설명
 * 2. LLM이 규칙 제안 (이름, SQL, 조건, 임계값, 심각도, 설명)
 * 3. "확인 및 생성" 또는 "취소"로 최종 결정
 */
import { useState } from 'react';
import { toast } from 'sonner';
import { Send, Check, X, Loader2, Bot, User, Sparkles } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';

import { generateRule, confirmRule } from '../api/watchAgentApi';
import type { RuleProposal } from '../api/watchAgentApi';

// ─── 메시지 타입 ──────────────────────────────────────────

interface Message {
  role: 'user' | 'agent';
  content: string;
  /** agent 메시지일 때만 — 규칙 제안 데이터 */
  proposal?: RuleProposal;
}

// ─── 심각도 뱃지 색상 ─────────────────────────────────────

const severityVariant = (s: string): 'destructive' | 'default' | 'secondary' => {
  if (s === 'critical') return 'destructive';
  if (s === 'warning') return 'default';
  return 'secondary';
};

// ─── 컴포넌트 ────────────────────────────────────────────

export function WatchAgentPanel() {
  // 대화 이력
  const [messages, setMessages] = useState<Message[]>([]);

  // 입력 상태
  const [input, setInput] = useState('');
  const [generating, setGenerating] = useState(false);

  // 현재 확인 대기 중인 제안
  const [pendingProposal, setPendingProposal] = useState<RuleProposal | null>(null);
  const [confirming, setConfirming] = useState(false);

  // ─── 규칙 생성 요청 ───────────────────────────────────────

  const handleGenerate = async () => {
    const desc = input.trim();
    if (!desc) return;

    // 사용자 메시지 추가
    setMessages((prev) => [...prev, { role: 'user', content: desc }]);
    setInput('');
    setGenerating(true);

    try {
      const proposal = await generateRule(desc);
      // 에이전트 메시지 + 제안 카드
      setMessages((prev) => [
        ...prev,
        {
          role: 'agent',
          content: proposal.explanation,
          proposal,
        },
      ]);
      setPendingProposal(proposal);
    } catch {
      toast.error('규칙 생성에 실패했습니다. 다시 시도해 주세요.');
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: '죄송합니다. 규칙 생성 중 오류가 발생했습니다.' },
      ]);
    } finally {
      setGenerating(false);
    }
  };

  // ─── 제안 확인 (실제 규칙 생성) ─────────────────────────

  const handleConfirm = async () => {
    if (!pendingProposal) return;
    setConfirming(true);

    try {
      const result = await confirmRule(pendingProposal);
      toast.success(`규칙 "${result.name}"이(가) 생성되었습니다`);
      setMessages((prev) => [
        ...prev,
        { role: 'agent', content: `규칙 "${result.name}"이(가) 성공적으로 생성되었습니다.` },
      ]);
      setPendingProposal(null);
    } catch {
      toast.error('규칙 확인에 실패했습니다');
    } finally {
      setConfirming(false);
    }
  };

  // ─── 제안 취소 ─────────────────────────────────────────

  const handleCancel = () => {
    setPendingProposal(null);
    setMessages((prev) => [...prev, { role: 'agent', content: '규칙 생성이 취소되었습니다.' }]);
  };

  // ─── Enter 키 전송 ────────────────────────────────────

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  };

  return (
    <div className="flex flex-col h-full max-w-2xl mx-auto">
      {/* 헤더 */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-[#E5E5E5]">
        <Sparkles className="h-4 w-4 text-purple-500" />
        <h2 className="text-base font-semibold">Watch Agent</h2>
        <Badge variant="ai" className="text-[10px]">AI</Badge>
      </div>

      {/* 대화 영역 */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* 빈 상태 안내 */}
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-foreground/30 text-sm gap-2">
            <Bot className="h-8 w-8" />
            <p>모니터링하고 싶은 조건을 자연어로 설명하세요</p>
            <p className="text-xs text-foreground/20">
              예: "재고가 10개 미만이면 경고해줘"
            </p>
          </div>
        )}

        {/* 메시지 목록 */}
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-2.5 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {/* 에이전트 아바타 */}
            {msg.role === 'agent' && (
              <div className="shrink-0 h-7 w-7 rounded-full bg-purple-100 flex items-center justify-center">
                <Bot className="h-4 w-4 text-purple-600" />
              </div>
            )}

            <div
              className={`
                max-w-[80%] rounded-lg px-3.5 py-2.5 text-sm
                ${msg.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-[#F5F5F5] text-foreground'}
              `}
            >
              {/* 텍스트 내용 */}
              <p className="whitespace-pre-wrap">{msg.content}</p>

              {/* 제안 카드 — agent 메시지에만 */}
              {msg.proposal && (
                <Card className="mt-3 p-3 bg-white border-[#E5E5E5] text-foreground">
                  <div className="flex flex-col gap-2 text-xs">
                    {/* 규칙 이름 */}
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-sm">{msg.proposal.name}</span>
                      <Badge variant={severityVariant(msg.proposal.severity)}>
                        {msg.proposal.severity}
                      </Badge>
                    </div>

                    {/* SQL 쿼리 */}
                    <div className="rounded bg-[#FAFAFA] border border-[#E5E5E5] p-2 font-mono text-[11px] overflow-x-auto">
                      {msg.proposal.sql_query}
                    </div>

                    {/* 조건 + 임계값 */}
                    <div className="flex gap-4 text-foreground/60">
                      <span>조건: {msg.proposal.condition_type}</span>
                      <span>임계값: {msg.proposal.threshold}</span>
                    </div>
                  </div>
                </Card>
              )}
            </div>

            {/* 사용자 아바타 */}
            {msg.role === 'user' && (
              <div className="shrink-0 h-7 w-7 rounded-full bg-blue-100 flex items-center justify-center">
                <User className="h-4 w-4 text-blue-600" />
              </div>
            )}
          </div>
        ))}

        {/* 생성 중 인디케이터 */}
        {generating && (
          <div className="flex gap-2.5">
            <div className="shrink-0 h-7 w-7 rounded-full bg-purple-100 flex items-center justify-center">
              <Bot className="h-4 w-4 text-purple-600" />
            </div>
            <div className="bg-[#F5F5F5] rounded-lg px-4 py-3 text-sm text-foreground/50 flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              규칙을 생성하고 있습니다...
            </div>
          </div>
        )}
      </div>

      {/* 제안 확인 버튼 영역 */}
      {pendingProposal && (
        <div className="flex items-center justify-center gap-2 px-5 py-3 border-t border-[#E5E5E5] bg-[#FAFAFA]">
          <Button onClick={handleConfirm} disabled={confirming} className="gap-1.5">
            {confirming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            확인 및 생성
          </Button>
          <Button variant="outline" onClick={handleCancel} disabled={confirming} className="gap-1.5">
            <X className="h-4 w-4" />
            취소
          </Button>
        </div>
      )}

      {/* 입력 영역 */}
      <div className="flex items-end gap-2 px-5 py-3 border-t border-[#E5E5E5]">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="모니터링 조건을 설명하세요..."
          rows={2}
          disabled={generating}
          className="flex-1 resize-none text-sm"
        />
        <Button
          size="sm"
          onClick={handleGenerate}
          disabled={generating || !input.trim()}
          className="h-9 w-9 p-0 shrink-0"
        >
          {generating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>
    </div>
  );
}
