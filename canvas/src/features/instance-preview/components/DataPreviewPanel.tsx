/**
 * DataPreviewPanel — 온톨로지 그래프에서 노드 클릭 시 표시되는 데이터 프리뷰 사이드 패널
 *
 * 기능:
 * - 헤더: 노드 이름 + 전체 레코드 수 뱃지
 * - 데이터 테이블: 컬럼 헤더(타입 뱃지 포함) + 샘플 행
 * - "더 보기" 페이지네이션
 * - 데이터 바인딩 없을 때 빈 상태 표시
 */
import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import { X, ChevronDown, Database, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';

import { getSampleData } from '../api/instanceApi';
import type { SampleDataResponse, ColumnType } from '../types/instance';
import { useTranslation } from 'react-i18next';

// ─── 상수 ──────────────────────────────────────────────────

/** 한 번에 요청하는 행 수 */
const PAGE_SIZE = 50;

/** 컬럼 타입별 뱃지 색상 */
const TYPE_COLORS: Record<ColumnType, string> = {
  text: 'bg-blue-100 text-blue-700',
  number: 'bg-green-100 text-green-700',
  date: 'bg-amber-100 text-amber-700',
  boolean: 'bg-purple-100 text-purple-700',
  json: 'bg-orange-100 text-orange-700',
  unknown: 'bg-gray-100 text-gray-500',
};

// ─── Props ────────────────────────────────────────────────

interface DataPreviewPanelProps {
  /** 선택된 노드 ID */
  nodeId: string;
  /** 노드 표시 이름 */
  nodeName: string;
  /** 스키마 이름 (선택) */
  schema?: string;
  /** 테이블 이름 (선택) */
  table?: string;
  /** 패널 닫기 콜백 */
  onClose: () => void;
}

// ─── 컴포넌트 ────────────────────────────────────────────

export function DataPreviewPanel({
  nodeId,
  nodeName,
  schema,
  table,
  onClose,
}: DataPreviewPanelProps) {
  const { t } = useTranslation();
  // 데이터 상태
  const [data, setData] = useState<SampleDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // 현재 표시 행 수 (페이지네이션용)
  const [limit, setLimit] = useState(PAGE_SIZE);

  // ─── 데이터 로드 ───────────────────────────────────────────

  const fetchData = useCallback(
    async (requestLimit: number) => {
      try {
        const result = await getSampleData(nodeId, requestLimit, schema, table);
        setData(result);
      } catch {
        toast.error(t('instancePreview.previewError'));
        setData(null);
      }
    },
    [nodeId, schema, table],
  );

  // 초기 로드
  useEffect(() => {
    setLoading(true);
    setLimit(PAGE_SIZE);
    fetchData(PAGE_SIZE).finally(() => setLoading(false));
  }, [fetchData]);

  // "더 보기" — 추가 데이터 로드 (에러 시에도 로딩 해제)
  const handleLoadMore = async () => {
    const newLimit = limit + PAGE_SIZE;
    setLoadingMore(true);
    try {
      await fetchData(newLimit);
      setLimit(newLimit);
    } catch {
      toast.error(t('instancePreview.loadMoreError'));
    } finally {
      setLoadingMore(false);
    }
  };

  // 더 보기 가능 여부
  const hasMore = data ? data.preview.length < data.total_count : false;

  // ─── 렌더링 ───────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full border-l border-border bg-card w-[480px] shrink-0">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Database className="h-4 w-4 text-foreground/40 shrink-0" />
          <span className="text-sm font-semibold truncate">{nodeName}</span>
          {data && (
            <Badge variant="secondary" className="text-[10px] shrink-0">
              {t('instancePreview.recordCount', { num: data.total_count.toLocaleString() })}
            </Badge>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-foreground/40 hover:text-foreground shrink-0 ml-2"
          aria-label={t('instancePreview.panelClose')}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* 본문 */}
      <div className="flex-1 overflow-auto">
        {/* 로딩 */}
        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
          </div>
        )}

        {/* 빈 상태 — 데이터 바인딩 없음 */}
        {!loading && !data && (
          <div className="flex flex-col items-center justify-center py-16 text-foreground/30 gap-2">
            <Database className="h-8 w-8" />
            <p className="text-sm">{t('instancePreview.noBinding')}</p>
            <p className="text-xs text-foreground/20">{t('instancePreview.connectDatasource')}</p>
          </div>
        )}

        {/* 빈 결과 — 데이터는 있지만 행이 없음 */}
        {!loading && data && data.preview.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-foreground/30 gap-2">
            <Database className="h-8 w-8" />
            <p className="text-sm">{t('instancePreview.noTableData')}</p>
          </div>
        )}

        {/* 데이터 테이블 */}
        {!loading && data && data.preview.length > 0 && (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  {data.columns.map((col) => (
                    <TableHead key={col} className="whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <span>{col}</span>
                        <span
                          className={`
                            inline-flex px-1.5 py-0.5 rounded text-[9px] font-medium
                            ${TYPE_COLORS[data.column_types[col] ?? 'unknown']}
                          `}
                        >
                          {data.column_types[col] ?? 'unknown'}
                        </span>
                      </div>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.preview.map((row, rowIdx) => (
                  <TableRow key={rowIdx}>
                    {row.map((cell, colIdx) => (
                      <TableCell
                        key={colIdx}
                        className="whitespace-nowrap text-xs font-mono max-w-[200px] truncate"
                        title={cell != null ? String(cell) : ''}
                      >
                        {cell != null ? (
                          String(cell)
                        ) : (
                          <span className="text-foreground/20 italic">NULL</span>
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* "더 보기" 버튼 */}
            {hasMore && (
              <div className="flex justify-center py-3 border-t border-border">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleLoadMore}
                  disabled={loadingMore}
                  className="h-7 text-xs text-foreground/50 hover:text-foreground/70 gap-1"
                >
                  {loadingMore ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <ChevronDown className="h-3 w-3" />
                  )}
                  {t('instancePreview.loadMore')}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
