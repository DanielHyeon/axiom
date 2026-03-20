/**
 * DataSourceManager — 데이터소스 선택/CRUD (간소화 버전)
 * 기존 DatasourcePage의 데이터소스 목록을 재사용하여
 * 업로드 시 대상 데이터소스를 선택할 수 있도록 한다.
 */

import React from 'react';
import { Database, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';

interface DataSourceItem {
  name: string;
  engine: string;
  status?: string;
}

interface DataSourceManagerProps {
  /** 데이터소스 목록 */
  datasources: DataSourceItem[];
  /** 선택된 데이터소스 이름 */
  selectedName: string | null;
  /** 선택 콜백 */
  onSelect: (name: string | null) => void;
  /** 로딩 중 */
  loading?: boolean;
  /** 새로고침 콜백 */
  onRefresh?: () => void;
}

export const DataSourceManager: React.FC<DataSourceManagerProps> = ({
  datasources,
  selectedName,
  onSelect,
  loading = false,
  onRefresh,
}) => {
  return (
    <div className="space-y-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-blue-500" />
          <h4 className="text-sm font-semibold text-gray-900 font-[Sora]">
            대상 데이터소스
          </h4>
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            title="새로고침"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        )}
      </div>

      {/* 선택 해제 옵션 */}
      <button
        type="button"
        onClick={() => onSelect(null)}
        className={`w-full text-left px-3 py-2 rounded-lg text-[13px] transition-colors ${
          selectedName === null
            ? 'bg-blue-50 border border-blue-200 text-blue-700 font-medium'
            : 'bg-white border border-gray-200 text-gray-500 hover:bg-gray-50'
        }`}
      >
        선택 안 함 (파일만 업로드)
      </button>

      {/* 데이터소스 리스트 */}
      {loading ? (
        <div className="flex items-center justify-center py-4 text-gray-400 gap-2">
          <RefreshCw className="h-4 w-4 animate-spin" />
          <span className="text-xs">로딩 중...</span>
        </div>
      ) : datasources.length === 0 ? (
        <p className="text-xs text-gray-400 text-center py-4">
          등록된 데이터소스가 없습니다
        </p>
      ) : (
        <div className="space-y-1.5 max-h-[200px] overflow-y-auto">
          {datasources.map((ds) => {
            const isSelected = selectedName === ds.name;
            const isConnected =
              ds.status?.toLowerCase() === 'connected' ||
              ds.status?.toLowerCase() === 'ok';

            return (
              <button
                key={ds.name}
                type="button"
                onClick={() => onSelect(isSelected ? null : ds.name)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-colors ${
                  isSelected
                    ? 'bg-blue-50 border border-blue-200'
                    : 'bg-white border border-gray-200 hover:bg-gray-50'
                }`}
              >
                {/* 상태 아이콘 */}
                {isConnected ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                ) : (
                  <XCircle className="h-3.5 w-3.5 text-gray-300 shrink-0" />
                )}

                {/* 이름 + 엔진 */}
                <div className="flex-1 min-w-0">
                  <span className="text-[13px] font-medium text-gray-900 font-[Sora] truncate block">
                    {ds.name}
                  </span>
                </div>
                <span className="text-[10px] text-gray-400 font-[IBM_Plex_Mono] uppercase shrink-0">
                  {ds.engine}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
