/**
 * PivotSqlPreview — SQL 미리보기 패널.
 *
 * 생성된 SQL을 읽기 전용으로 표시하고, 복사 기능을 제공한다.
 */
import { useState, useCallback } from 'react';
import { Copy, Check, Code } from 'lucide-react';
import { useTranslation } from 'react-i18next';

// ─── Props ────────────────────────────────────────────────

interface PivotSqlPreviewProps {
  sql: string;
  isLoading: boolean;
}

// ─── 컴포넌트 ────────────────────────────────────────────

export function PivotSqlPreview({ sql, isLoading }: PivotSqlPreviewProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  /** 클립보드에 SQL 복사 — 실패 시 경고만 출력 */
  const handleCopy = useCallback(async () => {
    if (!sql) return;
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      console.warn('[PivotSqlPreview] 클립보드 복사 실패');
    }
  }, [sql]);

  return (
    <div className="flex flex-col h-full bg-card rounded-lg overflow-hidden">
      {/* 헤더 — 타이틀 + 복사 버튼 */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted border-b border-border">
        <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground font-mono">
          <Code className="h-3 w-3" />
          SQL 미리보기
        </div>
        <button
          type="button"
          onClick={handleCopy}
          disabled={!sql}
          className="flex items-center gap-1 text-[9px] text-muted-foreground hover:text-primary-foreground font-mono transition-colors disabled:opacity-30"
          aria-label={t('olapStudioExt.copySql')}
        >
          {copied ? (
            <Check className="h-3 w-3 text-green-400" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
          {copied ? t('olapStudioExt.copied') : t('olapStudioExt.copy')}
        </button>
      </div>

      {/* SQL 본문 */}
      <div className="flex-1 overflow-auto p-3">
        {isLoading ? (
          <div className="text-[10px] text-muted-foreground font-mono animate-pulse">
            SQL 생성 중...
          </div>
        ) : sql ? (
          <pre className="text-[11px] text-muted-foreground font-mono whitespace-pre-wrap leading-relaxed">
            {sql}
          </pre>
        ) : (
          <div className="text-[10px] text-muted-foreground font-mono">
            피벗을 설정하고 미리보기를 클릭하세요
          </div>
        )}
      </div>
    </div>
  );
}
