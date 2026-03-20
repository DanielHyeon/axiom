/**
 * FilePreview — 업로드된 파일 미리보기 (CSV/JSON 테이블)
 * 파일 내용을 파싱하여 테이블 형태로 미리보기를 제공한다.
 */

import React, { useMemo } from 'react';
import { FileText, Table2, X } from 'lucide-react';
import type { FilePreviewData } from '../types/ingestion';

interface FilePreviewProps {
  /** 파일 이름 */
  fileName: string;
  /** 미리보기 데이터 */
  data: FilePreviewData;
  /** 닫기 콜백 */
  onClose?: () => void;
}

export const FilePreview: React.FC<FilePreviewProps> = ({
  fileName,
  data,
  onClose,
}) => {
  /** 표시할 행 (최대 20행) */
  const displayRows = useMemo(() => data.rows.slice(0, 20), [data.rows]);

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Table2 className="h-4 w-4 text-blue-500" />
          <span className="text-sm font-semibold text-gray-900 font-[Sora]">
            미리보기
          </span>
          <span className="text-xs text-gray-500 font-[IBM_Plex_Mono]">
            {fileName}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[11px] text-gray-400 font-[IBM_Plex_Mono]">
            {data.columns.length}개 컬럼 / {data.totalRows.toLocaleString()}개 행
          </span>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              aria-label="미리보기 닫기"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* 테이블 */}
      {data.columns.length > 0 ? (
        <div className="overflow-auto max-h-[400px]">
          <table className="w-full text-left">
            <thead className="sticky top-0 bg-gray-50 z-10">
              <tr>
                <th className="px-3 py-2 text-[11px] font-medium text-gray-500 font-[IBM_Plex_Mono] border-b border-gray-200 w-10">
                  #
                </th>
                {data.columns.map((col) => (
                  <th
                    key={col}
                    className="px-3 py-2 text-[11px] font-medium text-gray-500 font-[IBM_Plex_Mono] uppercase border-b border-gray-200 whitespace-nowrap"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {displayRows.map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-blue-50/30 transition-colors">
                  <td className="px-3 py-1.5 text-[11px] text-gray-400 font-[IBM_Plex_Mono]">
                    {rowIdx + 1}
                  </td>
                  {data.columns.map((col) => (
                    <td
                      key={col}
                      className="px-3 py-1.5 text-[13px] text-gray-700 font-[IBM_Plex_Mono] whitespace-nowrap max-w-[200px] truncate"
                      title={String(row[col] ?? '')}
                    >
                      {row[col] == null ? (
                        <span className="text-gray-300 italic">null</span>
                      ) : (
                        String(row[col])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400 gap-2">
          <FileText className="h-8 w-8 opacity-30" />
          <p className="text-sm">미리보기할 데이터가 없습니다</p>
        </div>
      )}

      {/* 더 많은 행 안내 */}
      {data.totalRows > 20 && (
        <div className="px-4 py-2 bg-gray-50 border-t border-gray-200 text-center">
          <span className="text-[11px] text-gray-400">
            처음 20행만 표시됩니다. 전체 {data.totalRows.toLocaleString()}행.
          </span>
        </div>
      )}
    </div>
  );
};
