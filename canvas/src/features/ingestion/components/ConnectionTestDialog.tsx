/**
 * ConnectionTestDialog — 연결 테스트 다이얼로그
 * 데이터소스 연결 테스트 결과를 모달로 표시한다.
 */

import React, { useState, useCallback } from 'react';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  TestTubeDiagonal,
  X,
  Clock,
} from 'lucide-react';
// 연결 테스트 API는 shared를 통해 접근한다 (feature 간 의존 제거)
import { testConnection } from '@/shared/api/datasourceApi';
import { useTranslation } from 'react-i18next';

interface ConnectionTestDialogProps {
  /** 다이얼로그 표시 여부 */
  open: boolean;
  /** 닫기 콜백 */
  onClose: () => void;
  /** 테스트 대상 데이터소스 이름 */
  datasourceName: string;
}

interface TestResult {
  success: boolean;
  message: string;
  responseTimeMs?: number;
}

export const ConnectionTestDialog: React.FC<ConnectionTestDialogProps> = ({
  open,
  onClose,
  datasourceName,
}) => {
  const { t } = useTranslation();
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<TestResult | null>(null);

  const handleTest = useCallback(async () => {
    setTesting(true);
    setResult(null);
    try {
      const res = await testConnection(datasourceName);
      setResult({
        success: !!res.success,
        message: res.success ? t('ingestionExt.connectionSuccess') : (res.message ?? t('ingestionExt.connectionFailed')),
        responseTimeMs: res.response_time_ms,
      });
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : t('ingestionExt.connectionTestFailed'),
      });
    } finally {
      setTesting(false);
    }
  }, [datasourceName]);

  if (!open) return null;

  return (
    /* 오버레이 */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      role="dialog"
      aria-modal="true"
      aria-label={t('ingestionExt.connectionTestAria')}
    >
      <div className="w-full max-w-md bg-card rounded-2xl shadow-2xl overflow-hidden">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <TestTubeDiagonal className="h-5 w-5 text-blue-500" />
            <h2 className="text-base font-semibold text-gray-900 font-heading">
              {t('ingestionExt.connectionTestAria')}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            aria-label={t('ingestionExt.closeBtn')}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* 본문 */}
        <div className="px-6 py-5 space-y-4">
          {/* 대상 정보 */}
          <div className="px-4 py-3 bg-gray-50 rounded-lg">
            <span className="text-[11px] text-gray-400 font-mono uppercase">
              {t('ingestionF.md86641c9')}
            </span>
            <p className="text-sm font-semibold text-gray-900 mt-0.5 font-heading">
              {datasourceName}
            </p>
          </div>

          {/* 결과 표시 */}
          {result && (
            <div
              className={`flex items-start gap-3 px-4 py-3 rounded-lg border ${
                result.success
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}
            >
              {result.success ? (
                <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0 mt-0.5" />
              ) : (
                <XCircle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
              )}
              <div>
                <p className={`text-sm font-medium ${result.success ? 'text-green-700' : 'text-red-700'}`}>
                  {result.message}
                </p>
                {result.responseTimeMs != null && (
                  <p className="flex items-center gap-1 mt-1 text-[11px] text-gray-500">
                    <Clock className="h-3 w-3" />
                    {t('ingestionF.responseTime', { ms: result.responseTimeMs })}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 액션 */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-[13px] text-gray-600 bg-card border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors font-heading"
          >
            {t('lineageExt.closeDetail')}
          </button>
          <button
            type="button"
            onClick={handleTest}
            disabled={testing}
            className="flex items-center gap-1.5 px-4 py-2 text-[13px] font-medium text-primary-foreground bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-heading"
          >
            {testing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {t('ingestion.testing')}
              </>
            ) : (
              <>
                <TestTubeDiagonal className="h-3.5 w-3.5" />
                {t('dataQualityExt.runTest')}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
