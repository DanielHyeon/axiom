/**
 * PipelineStepViewer — 파이프라인 단계별 진행 표시
 * KAIR PipelineControlPanel.vue의 phase-timeline을 React로 이식.
 * Extract -> Transform -> Load -> Validate 4단계를 타임라인으로 시각화.
 */

import React from 'react';
import {
  CheckCircle2,
  Loader2,
  Circle,
  XCircle,
  SkipForward,
  ArrowRight,
} from 'lucide-react';
import type { PipelineStep } from '../types/ingestion';

interface PipelineStepViewerProps {
  /** 파이프라인 단계 목록 */
  steps: PipelineStep[];
}

/** 단계 유형별 한글 라벨 */
const STEP_LABELS: Record<string, string> = {
  extract: '추출 (Extract)',
  transform: '변환 (Transform)',
  load: '적재 (Load)',
  validate: '검증 (Validate)',
};

/** 상태별 아이콘 */
function StepIcon({ status }: { status: PipelineStep['status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-5 w-5 text-green-500" />;
    case 'running':
      return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
    case 'failed':
      return <XCircle className="h-5 w-5 text-red-500" />;
    case 'skipped':
      return <SkipForward className="h-5 w-5 text-gray-300" />;
    case 'pending':
    default:
      return <Circle className="h-5 w-5 text-gray-300" />;
  }
}

/** 상태별 배경 스타일 */
function stepBgClass(status: PipelineStep['status']): string {
  switch (status) {
    case 'running':
      return 'bg-blue-50 border-blue-200';
    case 'completed':
      return 'bg-green-50/50 border-green-200';
    case 'failed':
      return 'bg-red-50/50 border-red-200';
    default:
      return 'bg-white border-gray-200';
  }
}

/** 소요 시간 포맷 */
function formatDuration(ms?: number): string {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

export const PipelineStepViewer: React.FC<PipelineStepViewerProps> = ({
  steps,
}) => {
  if (steps.length === 0) {
    return (
      <p className="text-sm text-gray-400 text-center py-4">
        파이프라인 단계 정보가 없습니다
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {steps.map((step, idx) => (
        <React.Fragment key={step.name}>
          {/* 단계 카드 */}
          <div
            className={`flex items-center gap-3 px-4 py-3 rounded-lg border transition-all ${stepBgClass(step.status)}`}
          >
            {/* 순서 + 아이콘 */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] font-bold text-gray-400 font-[IBM_Plex_Mono] w-4 text-center">
                {idx + 1}
              </span>
              <StepIcon status={step.status} />
            </div>

            {/* 단계 정보 */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-semibold text-gray-900 font-[Sora]">
                  {STEP_LABELS[step.type] ?? step.name}
                </span>
                {step.status === 'running' && (
                  <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium bg-blue-100 text-blue-700 rounded">
                    진행 중
                  </span>
                )}
              </div>
              {step.error && (
                <p className="mt-0.5 text-[11px] text-red-500 truncate">
                  {step.error}
                </p>
              )}
            </div>

            {/* 통계 */}
            <div className="flex items-center gap-3 shrink-0 text-[11px] text-gray-500 font-[IBM_Plex_Mono]">
              {step.rowsProcessed != null && step.rowsProcessed > 0 && (
                <span>{step.rowsProcessed.toLocaleString()} rows</span>
              )}
              {step.duration != null && (
                <span>{formatDuration(step.duration)}</span>
              )}
            </div>
          </div>

          {/* 단계 사이 화살표 (마지막 제외) */}
          {idx < steps.length - 1 && (
            <div className="flex justify-center">
              <ArrowRight className="h-4 w-4 text-gray-300 rotate-90" />
            </div>
          )}
        </React.Fragment>
      ))}
    </div>
  );
};
