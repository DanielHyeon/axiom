/**
 * FileDropZone — 드래그&드롭 파일 업로드 영역
 * KAIR DropZone.vue 기능을 React + Tailwind로 이식.
 * - 드래그&드롭 + 클릭으로 파일 선택
 * - 다중 파일 지원 (CSV, JSON, Excel)
 * - 파일 크기 제한 표시 (100MB)
 */

import React, { useCallback, useRef, useState } from 'react';
import { Upload, FileSpreadsheet, FileJson, FileText } from 'lucide-react';

interface FileDropZoneProps {
  /** 파일 드롭/선택 시 콜백 */
  onFilesDrop: (files: File[]) => void;
  /** 허용 확장자 목록 */
  acceptedExtensions?: string[];
  /** 최대 파일 크기 (bytes) */
  maxSize?: number;
  /** 비활성 상태 */
  disabled?: boolean;
}

/** 시스템/숨김 파일 필터 */
const IGNORED_FILES = ['.DS_Store', 'Thumbs.db', 'desktop.ini'];
const IGNORED_FOLDERS = ['__MACOSX', '.git', 'node_modules'];

function shouldIgnoreFile(filePath: string): boolean {
  const parts = filePath.split('/');
  const fileName = parts[parts.length - 1] || '';
  if (IGNORED_FILES.includes(fileName)) return true;
  for (const folder of IGNORED_FOLDERS) {
    if (parts.includes(folder)) return true;
  }
  return false;
}

/** accept 속성용 MIME 문자열 생성 */
function buildAcceptString(extensions: string[]): string {
  const mimeMap: Record<string, string> = {
    '.csv': 'text/csv',
    '.json': 'application/json',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.parquet': 'application/octet-stream',
    '.tsv': 'text/tab-separated-values',
  };
  return extensions.map((ext) => mimeMap[ext] || ext).join(',');
}

export const FileDropZone: React.FC<FileDropZoneProps> = ({
  onFilesDrop,
  acceptedExtensions = ['.csv', '.json', '.xlsx', '.xls', '.parquet', '.tsv'],
  maxSize = 100 * 1024 * 1024,
  disabled = false,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  /** 드래그 이벤트 핸들러 */
  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!disabled) setIsDragOver(true);
    },
    [disabled],
  );

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  /** 드롭 이벤트 — 시스템 파일 제외 후 콜백 */
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      if (disabled) return;

      const droppedFiles = Array.from(e.dataTransfer.files).filter(
        (f) => !shouldIgnoreFile(f.name),
      );
      if (droppedFiles.length > 0) onFilesDrop(droppedFiles);
    },
    [disabled, onFilesDrop],
  );

  /** 클릭으로 파일 선택 */
  const handleClick = useCallback(() => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  /** input change 핸들러 */
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        onFilesDrop(Array.from(files));
      }
      // 같은 파일 재선택 허용
      e.target.value = '';
    },
    [onFilesDrop],
  );

  const maxSizeMB = Math.round(maxSize / (1024 * 1024));

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="파일 업로드 영역"
      onClick={handleClick}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleClick(); }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`
        relative flex flex-col items-center justify-center gap-4 p-10
        rounded-xl border-2 border-dashed cursor-pointer
        transition-all duration-200 min-h-[260px]
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${isDragOver
          ? 'border-blue-500 bg-blue-50/60 shadow-lg scale-[1.01]'
          : 'border-gray-300 bg-white hover:border-blue-400 hover:bg-blue-50/30'}
      `}
    >
      {/* 숨겨진 파일 input */}
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={buildAcceptString(acceptedExtensions)}
        onChange={handleInputChange}
        className="hidden"
        aria-hidden="true"
      />

      {/* 드래그 오버레이 */}
      {isDragOver && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-blue-50/80 rounded-xl z-10">
          <Upload className="h-12 w-12 text-blue-500 animate-bounce" />
          <span className="text-base font-semibold text-blue-600">여기에 놓으세요</span>
        </div>
      )}

      {/* 기본 콘텐츠 */}
      <div className={`flex flex-col items-center text-center gap-3 ${isDragOver ? 'opacity-0' : ''}`}>
        <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-50 text-blue-500">
          <Upload className="h-8 w-8" />
        </div>

        <div>
          <p className="text-[15px] text-gray-600">
            파일을 <strong className="text-gray-900">드래그</strong>하거나{' '}
            <strong className="text-blue-600">클릭</strong>하여 업로드
          </p>
          <p className="text-xs text-gray-400 mt-1">
            최대 {maxSizeMB}MB / 다중 파일 지원
          </p>
        </div>

        {/* 허용 포맷 뱃지 */}
        <div className="flex items-center gap-2 mt-2">
          <FormatBadge icon={<FileSpreadsheet className="h-3.5 w-3.5" />} label="CSV" />
          <FormatBadge icon={<FileJson className="h-3.5 w-3.5" />} label="JSON" />
          <FormatBadge icon={<FileSpreadsheet className="h-3.5 w-3.5" />} label="Excel" />
          <FormatBadge icon={<FileText className="h-3.5 w-3.5" />} label="Parquet" />
        </div>
      </div>
    </div>
  );
};

/** 포맷 뱃지 서브 컴포넌트 */
function FormatBadge({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-mono text-gray-500 bg-gray-50 border border-gray-200 rounded-md">
      {icon}
      {label}
    </span>
  );
}
