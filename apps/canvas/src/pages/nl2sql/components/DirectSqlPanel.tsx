import { useState, useCallback } from 'react';
import MonacoEditor from 'react-monaco-editor';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ResultPanel } from './ResultPanel';
import { postDirectSql, type DirectSqlResponse } from '@/features/nl2sql/api/oracleNl2sqlApi';
import type { ExecutionMetadata } from '@/features/nl2sql/types/nl2sql';
import { AppError } from '@/lib/api/errors';
import {
  Play,
  ChevronDown,
  ChevronUp,
  ShieldAlert,
  Loader2,
} from 'lucide-react';

interface DirectSqlPanelProps {
  datasourceId: string;
}

export function DirectSqlPanel({ datasourceId }: DirectSqlPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [sql, setSql] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DirectSqlResponse['data'] | null>(null);

  const handleExecute = useCallback(async () => {
    const trimmed = sql.trim();
    if (!trimmed || !datasourceId || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await postDirectSql(trimmed, datasourceId);
      if (res.success && res.data) {
        setResult(res.data);
      } else {
        setError(res.error?.message ?? 'SQL 실행에 실패했습니다.');
      }
    } catch (err) {
      const msg =
        err instanceof AppError
          ? err.userMessage
          : (err as Error).message || 'SQL 실행에 실패했습니다.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [sql, datasourceId, loading]);

  // Normalize columns: backend returns string[], ResultPanel expects { name, type }[]
  const normalizedColumns =
    result?.result?.columns.map((c) =>
      typeof c === 'string' ? { name: c, type: 'unknown' } : (c as { name: string; type: string })
    ) ?? [];

  const metadata: ExecutionMetadata | null = result?.metadata
    ? {
        execution_time_ms: result.metadata.execution_time_ms,
        guard_status: result.metadata.guard_status,
        query_id: result.metadata.query_id,
      }
    : null;

  return (
    <div className="rounded border border-amber-200 bg-amber-50/50">
      {/* Collapse header */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-3 py-2 hover:bg-amber-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-amber-600" />
          <span className="text-sm font-medium text-amber-700 font-[Sora]">Direct SQL (Admin)</span>
          <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-600 font-[IBM_Plex_Mono]">
            ADMIN ONLY
          </Badge>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-amber-600" />
        ) : (
          <ChevronDown className="h-4 w-4 text-amber-600" />
        )}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3">
          {/* SQL Editor */}
          <div className="border border-[#E5E5E5] rounded-md overflow-hidden bg-[#1e1e1e]">
            <MonacoEditor
              language="sql"
              theme="vs-dark"
              value={sql}
              onChange={(value) => setSql(value)}
              width="100%"
              height={150}
              options={{
                readOnly: false,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                lineNumbers: 'on',
                fontSize: 13,
                wordWrap: 'on',
                folding: false,
                renderLineHighlight: 'gutter',
                overviewRulerLanes: 0,
                scrollbar: { vertical: 'auto', horizontal: 'auto' },
                contextmenu: true,
              }}
            />
          </div>

          {/* Execute button */}
          <div className="flex items-center gap-2">
            <Button
              onClick={handleExecute}
              disabled={loading || !sql.trim() || !datasourceId}
              className="gap-1.5 bg-amber-600 hover:bg-amber-700 text-white"
              size="sm"
            >
              {loading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Play className="h-3.5 w-3.5" />
              )}
              {loading ? '실행 중...' : 'SQL 실행'}
            </Button>
            {!datasourceId && (
              <span className="text-xs text-[#999] font-[IBM_Plex_Mono]">
                데이터소스를 먼저 선택하세요.
              </span>
            )}
          </div>

          {/* Error */}
          {error && (
            <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {/* Result */}
          {result && normalizedColumns.length > 0 && (
            <ResultPanel
              sql={sql}
              columns={normalizedColumns}
              rows={result.result.rows}
              rowCount={result.result.row_count}
              chartConfig={null}
              summary={null}
              metadata={metadata}
            />
          )}

          {/* Empty result */}
          {result && normalizedColumns.length === 0 && (
            <div className="text-sm text-[#999] py-2 font-[IBM_Plex_Mono]">
              실행 완료 (결과 없음, {result.result.row_count} rows affected)
            </div>
          )}
        </div>
      )}
    </div>
  );
}
