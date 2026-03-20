/**
 * PipelineControlPanel — ETL 파이프라인 제어 패널
 * KAIR PipelineControlPanel.vue 기능을 React로 이식.
 * - 파이프라인 카드 목록 (이름, 상태, 마지막 실행)
 * - 실행/중지 버튼
 * - PipelineStepViewer 통합
 */

import React, { useState } from 'react';
import {
  Play,
  Square,
  RotateCw,
  Clock,
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  Zap,
} from 'lucide-react';
import type { Pipeline } from '../types/ingestion';
import { PipelineStepViewer } from './PipelineStepViewer';

interface PipelineControlPanelProps {
  /** 파이프라인 목록 */
  pipelines: Pipeline[];
  /** 로딩 중 */
  loading?: boolean;
  /** 실행 콜백 */
  onRun?: (id: string) => void;
  /** 중지 콜백 */
  onStop?: (id: string) => void;
  /** 삭제 콜백 */
  onDelete?: (id: string) => void;
  /** 생성 콜백 */
  onCreate?: () => void;
}

/** 상태별 뱃지 스타일 */
function statusBadge(status: Pipeline['status']): { label: string; className: string } {
  switch (status) {
    case 'running':
      return { label: '실행 중', className: 'bg-blue-100 text-blue-700' };
    case 'paused':
      return { label: '일시정지', className: 'bg-amber-100 text-amber-700' };
    case 'completed':
      return { label: '완료', className: 'bg-green-100 text-green-700' };
    case 'failed':
      return { label: '실패', className: 'bg-red-100 text-red-700' };
    case 'idle':
    default:
      return { label: '대기', className: 'bg-gray-100 text-gray-600' };
  }
}

/** 시간 포맷 (상대 시간) */
function formatRelativeTime(isoString?: string): string {
  if (!isoString) return '-';
  try {
    const date = new Date(isoString);
    const diff = Date.now() - date.getTime();
    if (diff < 60000) return '방금 전';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}분 전`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}시간 전`;
    return `${Math.floor(diff / 86400000)}일 전`;
  } catch {
    return isoString;
  }
}

export const PipelineControlPanel: React.FC<PipelineControlPanelProps> = ({
  pipelines,
  loading = false,
  onRun,
  onStop,
  onDelete,
  onCreate,
}) => {
  // 펼쳐진 파이프라인 ID Set
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="space-y-4">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Zap className="h-4 w-4 text-blue-500" />
          <h3 className="text-sm font-semibold text-gray-900 font-[Sora]">
            ETL 파이프라인
          </h3>
          <span className="text-xs text-gray-400 font-[IBM_Plex_Mono]">
            {pipelines.length}개
          </span>
        </div>
        {onCreate && (
          <button
            type="button"
            onClick={onCreate}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            파이프라인 생성
          </button>
        )}
      </div>

      {/* 로딩 */}
      {loading && (
        <div className="flex items-center justify-center py-8 text-gray-400 gap-2">
          <RotateCw className="h-4 w-4 animate-spin" />
          <span className="text-sm">파이프라인 목록 로딩 중...</span>
        </div>
      )}

      {/* 빈 상태 */}
      {!loading && pipelines.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400 gap-3 border border-dashed border-gray-200 rounded-xl">
          <Zap className="h-8 w-8 opacity-30" />
          <p className="text-sm">등록된 파이프라인이 없습니다</p>
          {onCreate && (
            <button
              type="button"
              onClick={onCreate}
              className="text-sm text-blue-600 hover:underline"
            >
              첫 번째 파이프라인 생성하기
            </button>
          )}
        </div>
      )}

      {/* 파이프라인 카드 목록 */}
      {!loading && pipelines.length > 0 && (
        <div className="space-y-3">
          {pipelines.map((pipeline) => {
            const badge = statusBadge(pipeline.status);
            const isExpanded = expandedIds.has(pipeline.id);
            const isRunning = pipeline.status === 'running';

            return (
              <div
                key={pipeline.id}
                className="rounded-xl border border-gray-200 bg-white overflow-hidden"
              >
                {/* 카드 헤더 */}
                <div className="flex items-center gap-3 px-4 py-3">
                  {/* 펼침 토글 */}
                  <button
                    type="button"
                    onClick={() => toggleExpand(pipeline.id)}
                    className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                    aria-label={isExpanded ? '접기' : '펼치기'}
                  >
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>

                  {/* 이름 + 메타 */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-[13px] font-semibold text-gray-900 font-[Sora] truncate">
                        {pipeline.name}
                      </span>
                      <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full ${badge.className}`}>
                        {badge.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 mt-0.5 text-[11px] text-gray-400 font-[IBM_Plex_Mono]">
                      <span>DS: {pipeline.datasourceId}</span>
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatRelativeTime(pipeline.lastRunAt)}
                      </span>
                      {pipeline.schedule && (
                        <span>cron: {pipeline.schedule}</span>
                      )}
                    </div>
                  </div>

                  {/* 액션 버튼 */}
                  <div className="flex items-center gap-1.5 shrink-0">
                    {isRunning ? (
                      <button
                        type="button"
                        onClick={() => onStop?.(pipeline.id)}
                        className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-red-600 bg-red-50 border border-red-200 rounded-md hover:bg-red-100 transition-colors"
                        title="중지"
                      >
                        <Square className="h-3 w-3" />
                        중지
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onRun?.(pipeline.id)}
                        className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] font-medium text-green-700 bg-green-50 border border-green-200 rounded-md hover:bg-green-100 transition-colors"
                        title="실행"
                      >
                        <Play className="h-3 w-3" />
                        실행
                      </button>
                    )}
                    {onDelete && (
                      <button
                        type="button"
                        onClick={() => onDelete(pipeline.id)}
                        className="p-1.5 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                        title="삭제"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* 확장 영역: 단계별 진행 */}
                {isExpanded && pipeline.steps.length > 0 && (
                  <div className="px-4 pb-4 pt-1 border-t border-gray-100">
                    <PipelineStepViewer steps={pipeline.steps} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
