/**
 * DataPreviewPanel — 테이블 데이터 프리뷰 패널.
 *
 * 선택한 테이블의 실제 데이터 행을 미리 보여준다.
 * 테이블명/스키마명을 파라미터로 전달하여 백엔드에서 안전하게 쿼리를 생성한다.
 */
import { useState, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { X, Database, Loader2, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { oracleApi } from '@/lib/api/clients';

// ─── Props ────────────────────────────────────────────────

interface DataPreviewPanelProps {
  /** 프리뷰할 테이블명 */
  tableName: string;
  /** 스키마명 */
  schema: string;
  /** 데이터소스 이름 */
  datasource?: string;
  /** 닫기 핸들러 */
  onClose: () => void;
}

interface PreviewData {
  columns: string[];
  rows: (string | number | null)[][];
  rowCount: number;
}

// 테이블/스키마명 유효성 검사 패턴 — SQL 인젝션 방지
const SAFE_IDENTIFIER = /^[a-zA-Z_][a-zA-Z0-9_.]*$/;

// ─── 데이터 조회 함수 ─────────────────────────────────────

interface PreviewApiResponse {
  data?: {
    columns?: string[];
    rows?: (string | number | null)[][];
    row_count?: number;
  };
}

async function fetchPreviewData(
  tableName: string,
  schema: string,
  datasource?: string,
): Promise<PreviewData> {
  // 입력값 안전성 검증 — SQL 인젝션 방지 (C1 수정)
  if (!SAFE_IDENTIFIER.test(tableName)) {
    throw new Error(`유효하지 않은 테이블명: ${tableName}`);
  }
  if (schema && !SAFE_IDENTIFIER.test(schema)) {
    throw new Error(`유효하지 않은 스키마명: ${schema}`);
  }

  // 파라미터 기반 프리뷰 요청 — 백엔드에서 쿼리를 안전하게 생성
  const res: PreviewApiResponse = await oracleApi.post('/text2sql/execute', {
    table_name: tableName,
    schema_name: schema || 'public',
    datasource_name: datasource || '',
    preview: true,
    limit: 10,
  });

  const data = res?.data;
  return {
    columns: data?.columns || [],
    rows: data?.rows || [],
    rowCount: data?.row_count || 0,
  };
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function DataPreviewPanel({
  tableName,
  schema,
  datasource,
  onClose,
}: DataPreviewPanelProps) {
  const [data, setData] = useState<PreviewData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  // 데이터 로드 — retryCount 변경 시에도 재요청 (M2 수정)
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    fetchPreviewData(tableName, schema, datasource)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || '데이터 조회에 실패했습니다');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => { cancelled = true; };
  }, [tableName, schema, datasource, retryCount]);

  return (
    <div className="flex flex-col h-full bg-white border-l border-[#E5E5E5] w-[400px]">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 h-10 border-b border-[#E5E5E5] shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Database className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
          <span className="text-[12px] font-semibold text-black font-[Sora] truncate">
            {tableName}
          </span>
          <span className="text-[10px] text-foreground/40 font-[IBM_Plex_Mono] shrink-0">
            프리뷰
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1 rounded hover:bg-[#F0F0F0] transition-colors"
          aria-label="닫기"
        >
          <X className="h-3.5 w-3.5 text-foreground/40" />
        </button>
      </div>

      {/* 본문 */}
      <div className="flex-1 overflow-auto">
        {/* 로딩 */}
        {isLoading && (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <Loader2 className="h-5 w-5 text-foreground/30 animate-spin" />
            <span className="text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
              데이터 조회 중...
            </span>
          </div>
        )}

        {/* 에러 */}
        {error && !isLoading && (
          <div className="flex flex-col items-center justify-center py-12 gap-2 px-4">
            <AlertCircle className="h-5 w-5 text-red-400" />
            <span className="text-[11px] text-red-500 font-[IBM_Plex_Mono] text-center">
              {error}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setRetryCount((c) => c + 1)}
              className="mt-2 text-[10px]"
            >
              재시도
            </Button>
          </div>
        )}

        {/* 데이터 테이블 */}
        {data && !isLoading && !error && (
          <div className="overflow-x-auto">
            {/* 행 수 표시 */}
            <div className="px-4 py-1.5 bg-[#FAFAFA] border-b border-[#E5E5E5] text-[9px] text-foreground/40 font-[IBM_Plex_Mono]">
              {data.rowCount > 10
                ? `상위 10행 / 전체 ${data.rowCount.toLocaleString()}행`
                : `${data.rows.length}행`}
            </div>

            <table className="w-full text-[10px] font-[IBM_Plex_Mono]">
              <thead>
                <tr className="bg-[#F5F5F5] border-b border-[#E5E5E5]">
                  {data.columns.map((col) => (
                    <th
                      key={col}
                      className="px-3 py-1.5 text-left text-foreground/60 font-medium whitespace-nowrap"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, rowIdx) => (
                  <tr
                    key={rowIdx}
                    className={cn(
                      'border-b border-[#F0F0F0] hover:bg-[#FAFAFA] transition-colors',
                      rowIdx % 2 === 0 ? 'bg-white' : 'bg-[#FCFCFC]'
                    )}
                  >
                    {row.map((cell, colIdx) => (
                      <td
                        key={colIdx}
                        className="px-3 py-1 text-foreground/70 whitespace-nowrap max-w-[200px] truncate"
                        title={cell != null ? String(cell) : 'NULL'}
                      >
                        {cell != null ? (
                          String(cell)
                        ) : (
                          <span className="text-foreground/20 italic">NULL</span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>

            {/* 빈 데이터 */}
            {data.rows.length === 0 && (
              <div className="py-8 text-center text-[11px] text-foreground/30 font-[IBM_Plex_Mono]">
                데이터가 없습니다
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
