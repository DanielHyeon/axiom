/**
 * CPipelineProgress — C-Pipeline 실행 진행 상황 표시 컴포넌트
 *
 * NL2SQL ReAct 스트림에서 수신되는 c_pipeline 단계를 시각적으로 표시한다.
 * 3개 파이프라인 단계(탐색 → 수렴 → 탈출)를 컬러 도트와 함께 표시하고,
 * 클릭으로 세부 정보를 접고 펼칠 수 있다.
 */
import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { CPipelineStep, ReactStreamStep } from '@/features/nl2sql/api/oracleNl2sqlApi';

// ─── 파이프라인 단계 정의 ────────────────────────────────────

/** 파이프라인 단계별 한글 이름 및 스타일 */
const PHASE_CONFIG: Record<string, { label: string; color: string; bgColor: string; lightBg: string }> = {
  exploration: { label: '탐색', color: 'text-blue-600', bgColor: 'bg-blue-500', lightBg: 'bg-blue-50' },
  convergence: { label: '수렴', color: 'text-amber-600', bgColor: 'bg-amber-500', lightBg: 'bg-amber-50' },
  escape: { label: '탈출', color: 'text-green-600', bgColor: 'bg-green-500', lightBg: 'bg-green-50' },
};

/** 파이프라인 단계 순서 */
const PHASE_ORDER = ['exploration', 'convergence', 'escape'] as const;

// ─── Props ────────────────────────────────────────────────

interface CPipelineProgressProps {
  /** ReAct 스트림 단계 목록 (c_pipeline 단계를 필터링) */
  steps: ReactStreamStep[];
  /** 현재 실행 중 여부 */
  isRunning: boolean;
}

// ─── 유틸 ─────────────────────────────────────────────────

/** 스트림 단계에서 C-Pipeline 단계만 추출 */
function extractCPipelineSteps(steps: ReactStreamStep[]): CPipelineStep[] {
  return steps
    .filter((s) => s.step === 'c_pipeline' && s.data)
    .map((s) => {
      const d = s.data as Record<string, unknown>;
      return {
        phase: String(d.phase ?? ''),
        detail: String(d.detail ?? ''),
        sql: d.sql != null ? String(d.sql) : undefined,
        score: typeof d.score === 'number' ? d.score : undefined,
        count: typeof d.count === 'number' ? d.count : undefined,
      };
    });
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function CPipelineProgress({ steps, isRunning }: CPipelineProgressProps) {
  const [isOpen, setIsOpen] = useState(true);

  // c_pipeline 단계만 추출
  const pipelineSteps = useMemo(() => extractCPipelineSteps(steps), [steps]);

  // 빈 상태 — c_pipeline 단계가 없으면 렌더링하지 않음
  if (pipelineSteps.length === 0) return null;

  // 완료된 단계 추적
  const completedPhases = new Set(pipelineSteps.map((s) => s.phase));
  const currentPhase = pipelineSteps[pipelineSteps.length - 1]?.phase ?? '';

  return (
    <div className="rounded border border-[#E5E5E5] overflow-hidden">
      {/* 헤더 — 클릭으로 접기/펼치기 */}
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-center justify-between w-full px-3 py-2 hover:bg-[#FAFAFA] transition-colors"
      >
        <div className="flex items-center gap-2">
          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5 text-foreground/40" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-foreground/40" />
          )}
          <span className="text-[12px] font-semibold font-[IBM_Plex_Mono] text-foreground/70">
            C-Pipeline
          </span>
          {/* 단계 진행 도트 */}
          <div className="flex items-center gap-1.5 ml-2">
            {PHASE_ORDER.map((phase) => {
              const config = PHASE_CONFIG[phase];
              const isDone = completedPhases.has(phase) && phase !== currentPhase;
              const isCurrent = phase === currentPhase;
              const isPending = !completedPhases.has(phase);
              return (
                <div key={phase} className="flex items-center gap-1">
                  <div
                    className={cn(
                      'h-2 w-2 rounded-full transition-colors',
                      isDone && config.bgColor,
                      isCurrent && cn(config.bgColor, isRunning && 'animate-pulse'),
                      isPending && 'bg-gray-300',
                    )}
                  />
                  <span
                    className={cn(
                      'text-[10px] font-[IBM_Plex_Mono]',
                      isDone && config.color,
                      isCurrent && cn(config.color, 'font-semibold'),
                      isPending && 'text-gray-400',
                    )}
                  >
                    {config.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
        <Badge variant="secondary" className="text-[10px] font-[IBM_Plex_Mono]">
          {pipelineSteps.length}단계
        </Badge>
      </button>

      {/* 세부 내용 — 접기/펼치기 */}
      {isOpen && (
        <div className="border-t border-[#E5E5E5] px-3 py-2 space-y-1.5">
          {pipelineSteps.map((step, idx) => {
            const config = PHASE_CONFIG[step.phase] ?? {
              label: step.phase,
              color: 'text-foreground/60',
              bgColor: 'bg-gray-400',
            };
            return (
              <div key={idx} className="flex items-start gap-2 text-[11px] font-[IBM_Plex_Mono]">
                {/* 단계 배지 */}
                <span
                  className={cn(
                    'shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold',
                    config.color,
                    config.bgColor.replace('bg-', 'bg-').replace('500', '50'),
                  )}
                  style={{
                    backgroundColor: `color-mix(in srgb, currentColor 10%, transparent)`,
                  }}
                >
                  {config.label}
                </span>
                {/* 설명 */}
                <span className="text-foreground/60 flex-1">{step.detail}</span>
                {/* 점수 (있는 경우) */}
                {step.score != null && (
                  <span className="shrink-0 text-foreground/40">
                    점수: <strong className="text-foreground/60">{step.score.toFixed(2)}</strong>
                  </span>
                )}
                {/* 건수 (있는 경우) */}
                {step.count != null && (
                  <span className="shrink-0 text-foreground/40">
                    {step.count}건
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
