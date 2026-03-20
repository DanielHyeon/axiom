/**
 * IngestionHistory — 수집 이력 테이블
 * 파이프라인 실행 이력(성공/실패/처리 행 수/소요 시간)을 테이블로 표시.
 */

import React from 'react';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  History,
  RefreshCw,
} from 'lucide-react';
import type { IngestionRecord } from '../types/ingestion';

interface IngestionHistoryProps {
  /** 수집 이력 목록 */
  records: IngestionRecord[];
  /** 로딩 중 */
  loading?: boolean;
  /** 새로고침 콜백 */
  onRefresh?: () => void;
}

/** 상태 아이콘 */
function RecordStatusIcon({ status }: { status: IngestionRecord['status'] }) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'running':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    default:
      return null;
  }
}

/** 소요 시간 포맷 */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

/** 날짜 포맷 */
function formatDateTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleString('ko-KR', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export const IngestionHistory: React.FC<IngestionHistoryProps> = ({
  records,
  loading = false,
  onRefresh,
}) => {
  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-blue-500" />
          <h3 className="text-sm font-semibold text-gray-900 font-[Sora]">
            수집 이력
          </h3>
          <span className="text-xs text-gray-400 font-[IBM_Plex_Mono]">
            {records.length}건
          </span>
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="flex items-center gap-1 px-2 py-1 text-[11px] text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded transition-colors"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
            새로고침
          </button>
        )}
      </div>

      {/* 로딩 */}
      {loading && (
        <div className="flex items-center justify-center py-8 text-gray-400 gap-2">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">이력 로딩 중...</span>
        </div>
      )}

      {/* 빈 상태 */}
      {!loading && records.length === 0 && (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400 gap-2 border border-dashed border-gray-200 rounded-xl">
          <History className="h-8 w-8 opacity-30" />
          <p className="text-sm">수집 이력이 없습니다</p>
        </div>
      )}

      {/* 테이블 */}
      {!loading && records.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
          {/* 헤더 행 */}
          <div className="grid grid-cols-[40px_1fr_120px_100px_100px_80px] px-4 py-2.5 bg-gray-50 border-b border-gray-200">
            <span className="text-[10px] font-medium text-gray-500 font-[IBM_Plex_Mono] uppercase">
              #
            </span>
            <span className="text-[10px] font-medium text-gray-500 font-[IBM_Plex_Mono] uppercase">
              파이프라인
            </span>
            <span className="text-[10px] font-medium text-gray-500 font-[IBM_Plex_Mono] uppercase">
              시작 시각
            </span>
            <span className="text-[10px] font-medium text-gray-500 font-[IBM_Plex_Mono] uppercase">
              처리 행
            </span>
            <span className="text-[10px] font-medium text-gray-500 font-[IBM_Plex_Mono] uppercase">
              소요 시간
            </span>
            <span className="text-[10px] font-medium text-gray-500 font-[IBM_Plex_Mono] uppercase">
              상태
            </span>
          </div>

          {/* 데이터 행 */}
          <div className="divide-y divide-gray-100 max-h-[400px] overflow-y-auto">
            {records.map((record, idx) => (
              <div
                key={record.id}
                className="grid grid-cols-[40px_1fr_120px_100px_100px_80px] items-center px-4 py-2.5 hover:bg-gray-50/50 transition-colors"
              >
                <span className="text-[11px] text-gray-400 font-[IBM_Plex_Mono]">
                  {idx + 1}
                </span>
                <div className="min-w-0">
                  <span className="text-[13px] text-gray-900 font-[Sora] truncate block">
                    {record.pipelineName || record.pipelineId || record.datasource}
                  </span>
                  {record.error && (
                    <p className="text-[10px] text-red-500 truncate mt-0.5">
                      {record.error}
                    </p>
                  )}
                </div>
                <span className="text-[11px] text-gray-500 font-[IBM_Plex_Mono]">
                  {formatDateTime(record.startedAt)}
                </span>
                <span className="text-[11px] text-gray-700 font-[IBM_Plex_Mono]">
                  {record.rowsProcessed.toLocaleString()}
                </span>
                <span className="text-[11px] text-gray-500 font-[IBM_Plex_Mono]">
                  {formatDuration(record.duration)}
                </span>
                <RecordStatusIcon status={record.status} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
