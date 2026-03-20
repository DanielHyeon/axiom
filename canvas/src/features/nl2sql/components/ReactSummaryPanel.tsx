/**
 * ReactSummaryPanel — ReAct 에이전트 실행 요약 패널.
 *
 * 에이전트 실행 상태, 부분 SQL, 최종 SQL, 경고 사항 등을 요약 표시.
 * KAIR ReactSummaryPanel.vue를 React+Tailwind 패턴으로 이식.
 *
 * 주요 기능:
 *  - 상태 배너 (idle/running/completed/error)
 *  - 부분 SQL / 최종 SQL / 검증 SQL 섹션 (복사 버튼)
 *  - 경고 목록
 *  - 수집된 메타데이터 (접기/펼치기)
 */

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import {
  Copy,
  Check,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Zap,
  MessageSquare,
  CheckCircle2,
  XCircle,
  Clock,
  Wrench,
} from 'lucide-react';
import type { ReactStreamStep } from '../api/oracleNl2sqlApi';

// ─── Props ────────────────────────────────────────────────

interface ReactSummaryPanelProps {
  /** ReAct 스트림 단계 목록 */
  steps: ReactStreamStep[];
  /** 실행 중 여부 */
  isRunning: boolean;
}

// ─── 상태 추출 유틸 ───────────────────────────────────────

type AgentStatus = 'idle' | 'running' | 'needs_user_input' | 'completed' | 'error';

function deriveStatus(steps: ReactStreamStep[], isRunning: boolean): AgentStatus {
  if (steps.length === 0) return 'idle';
  const last = steps[steps.length - 1];
  if (last.step === 'result') return 'completed';
  if (last.step === 'error') return 'error';
  if (last.step === 'needs_user_input') return 'needs_user_input';
  if (isRunning) return 'running';
  return 'idle';
}

function extractSql(steps: ReactStreamStep[], field: string): string | null {
  // 역순으로 탐색하여 최신 SQL 추출
  for (let i = steps.length - 1; i >= 0; i--) {
    const d = steps[i].data as Record<string, unknown> | undefined;
    if (d && typeof d[field] === 'string' && d[field]) {
      return d[field] as string;
    }
  }
  return null;
}

function extractWarnings(steps: ReactStreamStep[]): string[] {
  const warnings: string[] = [];
  for (const step of steps) {
    const d = step.data as Record<string, unknown> | undefined;
    if (d?.warnings && Array.isArray(d.warnings)) {
      for (const w of d.warnings) {
        if (typeof w === 'string') warnings.push(w);
      }
    }
    // guard_fixes도 경고로 표시
    if (d?.guard_fixes && Array.isArray(d.guard_fixes)) {
      for (const f of d.guard_fixes) {
        if (typeof f === 'string') warnings.push(`SQL Guard: ${f}`);
      }
    }
  }
  return warnings;
}

function extractLatestToolName(steps: ReactStreamStep[]): string | null {
  for (let i = steps.length - 1; i >= 0; i--) {
    const d = steps[i].data as Record<string, unknown> | undefined;
    if (d?.tool_call && typeof (d.tool_call as Record<string, unknown>).name === 'string') {
      return (d.tool_call as Record<string, unknown>).name as string;
    }
  }
  return null;
}

// ─── 상태 설정 맵 ─────────────────────────────────────────

const STATUS_CONFIG: Record<AgentStatus, { label: string; icon: React.ElementType; className: string }> = {
  idle: { label: '대기', icon: Clock, className: 'bg-[#F0F0F0] text-foreground/50' },
  running: { label: '에이전트 실행 중', icon: Zap, className: 'bg-blue-50 text-blue-600 animate-pulse' },
  needs_user_input: { label: '추가 입력 대기 중', icon: MessageSquare, className: 'bg-amber-50 text-amber-600' },
  completed: { label: '완료', icon: CheckCircle2, className: 'bg-green-50 text-green-600' },
  error: { label: '오류 발생', icon: XCircle, className: 'bg-red-50 text-red-600' },
};

// ─── 컴포넌트 ─────────────────────────────────────────────

export function ReactSummaryPanel({ steps, isRunning }: ReactSummaryPanelProps) {
  const status = deriveStatus(steps, isRunning);
  const partialSql = extractSql(steps, 'partial_sql');
  const finalSql = extractSql(steps, 'sql');
  const validatedSql = extractSql(steps, 'validated_sql');
  const warnings = extractWarnings(steps);
  const latestToolName = extractLatestToolName(steps);
  const currentStep = steps[steps.length - 1]?.iteration ?? 0;
  const remainingCalls = 5 - currentStep; // 기본 max_iterations = 5

  // 빈 상태
  if (steps.length === 0) return null;

  const statusConfig = STATUS_CONFIG[status];
  const StatusIcon = statusConfig.icon;

  return (
    <div className="rounded border border-[#E5E5E5] space-y-3 p-3">
      {/* 상태 배너 */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-semibold font-[IBM_Plex_Mono]',
              statusConfig.className
            )}
          >
            <StatusIcon className="h-3.5 w-3.5" />
            {statusConfig.label}
          </span>
          {currentStep > 0 && (
            <span className="px-2 py-1 bg-blue-50 border border-blue-200 rounded-full text-[10px] font-semibold text-blue-600 font-[IBM_Plex_Mono]">
              Step {currentStep}
            </span>
          )}
        </div>

        {/* 메타 정보 */}
        <div className="flex items-center gap-3 text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
          <span>남은 호출: <strong className="text-foreground/60">{Math.max(0, remainingCalls)}</strong></span>
          {latestToolName && (
            <span className="flex items-center gap-1">
              <Wrench className="h-3 w-3" />
              <strong className="text-foreground/60">{latestToolName}</strong>
            </span>
          )}
        </div>
      </div>

      {/* 부분 SQL */}
      {partialSql && !finalSql && (
        <SqlSection title="현재 SQL 스냅샷" sql={partialSql} variant="default" />
      )}

      {/* 최종 SQL */}
      {finalSql && (
        <SqlSection title="최종 SQL" sql={finalSql} variant="success" />
      )}

      {/* 검증된 SQL (최종과 다른 경우만) */}
      {validatedSql && validatedSql !== finalSql && (
        <SqlSection title="검증된 SQL" sql={validatedSql} variant="info" />
      )}

      {/* 경고 */}
      {warnings.length > 0 && (
        <div className="bg-amber-50/50 border-l-2 border-amber-400 p-3 rounded-r">
          <div className="flex items-center gap-1.5 text-[12px] text-amber-600 font-semibold font-[IBM_Plex_Mono] mb-1">
            <AlertTriangle className="h-3.5 w-3.5" />
            경고 ({warnings.length})
          </div>
          <ul className="space-y-0.5">
            {warnings.map((w, i) => (
              <li key={i} className="text-[11px] text-foreground/60 font-[IBM_Plex_Mono] pl-5">
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── SQL 섹션 ─────────────────────────────────────────────

interface SqlSectionProps {
  title: string;
  sql: string;
  variant: 'default' | 'success' | 'info';
}

const VARIANT_STYLES = {
  default: 'bg-[#F5F5F5] border-foreground/10',
  success: 'bg-green-50/50 border-green-200',
  info: 'bg-blue-50/50 border-blue-200',
};

const HEADER_STYLES = {
  default: 'text-foreground/50',
  success: 'text-green-600',
  info: 'text-blue-600',
};

function SqlSection({ title, sql, variant }: SqlSectionProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [sql]);

  return (
    <div className={cn('rounded border overflow-hidden', VARIANT_STYLES[variant])}>
      <div className="flex items-center justify-between px-3 py-1.5">
        <span className={cn('text-[11px] font-semibold font-[IBM_Plex_Mono]', HEADER_STYLES[variant])}>
          {title}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 px-2 py-0.5 text-[10px] text-foreground/40 hover:text-foreground/60 rounded transition-colors"
        >
          {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3" />}
          {copied ? '복사됨' : '복사'}
        </button>
      </div>
      <div className="px-3 pb-2 max-h-[200px] overflow-auto">
        <pre className="text-[11px] text-foreground/70 font-[IBM_Plex_Mono] whitespace-pre-wrap break-words">
          {sql}
        </pre>
      </div>
    </div>
  );
}
