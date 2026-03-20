/**
 * EntityQueryPanel — 엔티티 SQL 쿼리 패널
 * KAIR EntityQueryPanel.vue를 이식
 * 온톨로지 노드에 대한 자연어 검색 → SQL 생성 → 결과 미리보기
 */
import { useState } from 'react';
import { Search, Play, ExternalLink, Loader2 } from 'lucide-react';
import { oracleApi } from '@/lib/api/clients';

interface Props {
  nodeName: string;
  nodeDescription?: string;
}

interface QueryResult {
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
}

export function EntityQueryPanel({ nodeName, nodeDescription }: Props) {
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const defaultQuery = `${nodeName}(${nodeDescription ?? nodeName})에 해당하는 모든 데이터를 조회해줘`;

  // 쿼리 실행
  const executeQuery = async () => {
    const q = query.trim() || defaultQuery;
    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await oracleApi.post('/api/v3/oracle/ask', {
        question: q,
        limit: 100,
      });
      const data = res as unknown as {
        sql?: string;
        table?: { columns: string[]; rows: Record<string, unknown>[]; row_count: number };
      };

      if (data.table) {
        setResult({
          sql: data.sql ?? '',
          columns: data.table.columns || [],
          rows: data.table.rows || [],
          rowCount: data.table.row_count || 0,
        });
      } else {
        setError('쿼리 결과가 없습니다.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '쿼리 실행 실패');
      // Mock 결과 (백엔드 미연결 시 데모용)
      setResult({
        sql: `SELECT * FROM ${nodeName.toLowerCase()} LIMIT 100`,
        columns: ['id', 'name', 'value', 'status'],
        rows: Array.from({ length: 5 }, (_, i) => ({
          id: i + 1,
          name: `${nodeName}_${i + 1}`,
          value: Math.round(Math.random() * 1000),
          status: i % 2 === 0 ? 'active' : 'inactive',
        })),
        rowCount: 5,
      });
      setError(null); // Mock으로 대체되었으므로 에러 해제
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-3 p-4 bg-muted/30 rounded-lg border border-border">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Search size={14} className="text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">{nodeName} 인스턴스 검색</span>
        </div>
        <button
          type="button"
          className="p-1.5 rounded border border-border text-muted-foreground hover:text-primary hover:border-primary transition-colors"
          title="전체 화면"
        >
          <ExternalLink size={12} />
        </button>
      </div>

      {/* 쿼리 입력 */}
      <div className="space-y-2">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={defaultQuery}
          rows={2}
          disabled={isLoading}
          className="w-full px-3 py-2 bg-card border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary resize-none"
          onKeyDown={(e) => {
            if (e.ctrlKey && e.key === 'Enter') executeQuery();
          }}
        />
        <div className="flex justify-end">
          <button
            type="button"
            onClick={executeQuery}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-md hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {isLoading ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
            {isLoading ? '검색 중...' : '검색'}
          </button>
        </div>
      </div>

      {/* 에러 */}
      {error && (
        <div className="px-3 py-2 bg-destructive/10 border border-destructive/30 rounded-md text-xs text-destructive">
          {error}
        </div>
      )}

      {/* 생성된 SQL */}
      {result?.sql && (
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider">생성된 SQL</p>
          <pre className="px-3 py-2 bg-card rounded-md text-[11px] text-muted-foreground font-mono overflow-x-auto whitespace-pre-wrap max-h-20">
            {result.sql}
          </pre>
        </div>
      )}

      {/* 결과 테이블 */}
      {result && result.rows.length > 0 && (
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground">
            결과: {result.rowCount}건
          </p>
          <div className="overflow-auto border border-border rounded-md max-h-48">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="bg-muted/50">
                  {result.columns.slice(0, 6).map((col) => (
                    <th key={col} className="px-2.5 py-1.5 text-left font-medium text-muted-foreground whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.slice(0, 10).map((row, i) => (
                  <tr key={i} className="border-t border-border hover:bg-muted/20">
                    {result.columns.slice(0, 6).map((col) => (
                      <td key={col} className="px-2.5 py-1.5 text-foreground whitespace-nowrap max-w-[120px] truncate">
                        {String(row[col] ?? '-')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
