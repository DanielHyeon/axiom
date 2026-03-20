/**
 * UploadProgress — 업로드 파일 목록 + 진행률 바
 * 각 파일의 업로드 상태(pending/uploading/completed/failed)를 시각적으로 표시.
 */

import React from 'react';
import {
  FileText,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Trash2,
} from 'lucide-react';
import type { UploadFile } from '../types/ingestion';
import { formatFileSize } from '../hooks/useFileUpload';

interface UploadProgressProps {
  /** 업로드 파일 목록 */
  files: UploadFile[];
  /** 파일 제거 콜백 */
  onRemove?: (id: string) => void;
  /** 전체 초기화 콜백 */
  onClearAll?: () => void;
}

/** 상태별 아이콘 */
function StatusIcon({ status }: { status: UploadFile['status'] }) {
  switch (status) {
    case 'pending':
      return <Clock className="h-4 w-4 text-gray-400" />;
    case 'uploading':
    case 'processing':
      return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
    case 'completed':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'failed':
      return <XCircle className="h-4 w-4 text-red-500" />;
    default:
      return <FileText className="h-4 w-4 text-gray-400" />;
  }
}

/** 상태 텍스트 */
function statusLabel(status: UploadFile['status']): string {
  switch (status) {
    case 'pending': return '대기 중';
    case 'uploading': return '업로드 중';
    case 'processing': return '처리 중';
    case 'completed': return '완료';
    case 'failed': return '실패';
    default: return '';
  }
}

/** 진행률 바 색상 */
function progressColor(status: UploadFile['status']): string {
  switch (status) {
    case 'uploading':
    case 'processing':
      return 'bg-blue-500';
    case 'completed':
      return 'bg-green-500';
    case 'failed':
      return 'bg-red-500';
    default:
      return 'bg-gray-300';
  }
}

export const UploadProgress: React.FC<UploadProgressProps> = ({
  files,
  onRemove,
  onClearAll,
}) => {
  if (files.length === 0) return null;

  // 전체 통계
  const completed = files.filter((f) => f.status === 'completed').length;
  const failed = files.filter((f) => f.status === 'failed').length;
  const total = files.length;

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900 font-[Sora]">
            업로드 파일
          </span>
          <span className="text-xs text-gray-500 font-[IBM_Plex_Mono]">
            {completed}/{total} 완료
            {failed > 0 && <span className="text-red-500 ml-1">({failed} 실패)</span>}
          </span>
        </div>
        {onClearAll && (
          <button
            type="button"
            onClick={onClearAll}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors"
            title="전체 삭제"
          >
            전체 삭제
          </button>
        )}
      </div>

      {/* 파일 목록 */}
      <ul className="divide-y divide-gray-100 max-h-[320px] overflow-y-auto">
        {files.map((file) => (
          <li key={file.id} className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50/50 transition-colors">
            <StatusIcon status={file.status} />

            {/* 파일 정보 */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[13px] font-medium text-gray-900 truncate font-[Sora]">
                  {file.name}
                </span>
                <span className="text-[11px] text-gray-400 shrink-0 font-[IBM_Plex_Mono]">
                  {formatFileSize(file.size)}
                </span>
              </div>

              {/* 진행률 바 */}
              {(file.status === 'uploading' || file.status === 'processing') && (
                <div className="mt-1.5 h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${progressColor(file.status)}`}
                    style={{ width: `${file.progress}%` }}
                  />
                </div>
              )}

              {/* 에러 메시지 */}
              {file.status === 'failed' && file.error && (
                <p className="mt-1 text-[11px] text-red-500 truncate">{file.error}</p>
              )}
            </div>

            {/* 상태 라벨 + 진행률 */}
            <div className="flex items-center gap-2 shrink-0">
              {file.status === 'uploading' && (
                <span className="text-[11px] font-medium text-blue-600 font-[IBM_Plex_Mono]">
                  {file.progress}%
                </span>
              )}
              <span className={`text-[11px] ${
                file.status === 'completed' ? 'text-green-600' :
                file.status === 'failed' ? 'text-red-500' :
                'text-gray-400'
              }`}>
                {statusLabel(file.status)}
              </span>
            </div>

            {/* 삭제 버튼 */}
            {onRemove && (
              <button
                type="button"
                onClick={() => onRemove(file.id)}
                className="p-1 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                title="파일 제거"
                aria-label={`${file.name} 제거`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};
