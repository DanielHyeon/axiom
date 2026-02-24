import { useState } from 'react';
import type { ExecutionMetadata } from '@/features/nl2sql/types/nl2sql';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Clock,
  Table2,
  Search,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Zap,
  Hash,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetadataPanelProps {
  metadata: ExecutionMetadata | null | undefined;
}

const GUARD_VARIANT: Record<string, { className: string; label: string }> = {
  PASS: { className: 'border-green-700 text-green-400', label: 'PASS' },
  FIX: { className: 'border-amber-700 text-amber-400', label: 'FIX' },
  REJECT: { className: 'border-red-700 text-red-400', label: 'REJECT' },
};

export function MetadataPanel({ metadata }: MetadataPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [copiedQueryId, setCopiedQueryId] = useState(false);

  if (!metadata) return null;

  const guardInfo = GUARD_VARIANT[metadata.guard_status ?? ''] ?? {
    className: 'border-neutral-700 text-neutral-400',
    label: metadata.guard_status ?? 'N/A',
  };

  const handleCopyQueryId = () => {
    if (metadata.query_id) {
      navigator.clipboard.writeText(metadata.query_id);
      setCopiedQueryId(true);
      setTimeout(() => setCopiedQueryId(false), 2000);
    }
  };

  const summaryItems: { icon: React.ReactNode; text: string }[] = [];

  if (metadata.execution_time_ms != null) {
    summaryItems.push({
      icon: <Clock className="h-3 w-3" />,
      text: `${metadata.execution_time_ms}ms`,
    });
  }
  if (metadata.tables_used && metadata.tables_used.length > 0) {
    summaryItems.push({
      icon: <Table2 className="h-3 w-3" />,
      text: `${metadata.tables_used.length} tables`,
    });
  }
  if (metadata.schema_source) {
    summaryItems.push({
      icon: <Search className="h-3 w-3" />,
      text: metadata.schema_source,
    });
  }
  if (metadata.guard_status) {
    summaryItems.push({
      icon: <ShieldCheck className="h-3 w-3" />,
      text: metadata.guard_status,
    });
  }
  if (metadata.cache_hit != null) {
    summaryItems.push({
      icon: <Zap className="h-3 w-3" />,
      text: metadata.cache_hit ? 'Cached' : 'Fresh',
    });
  }

  if (summaryItems.length === 0) return null;

  return (
    <div className="border-t border-neutral-800">
      {/* Collapsed summary row */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-3 py-2 hover:bg-neutral-800/30 transition-colors"
      >
        <div className="flex flex-wrap items-center gap-2">
          {summaryItems.map((item, i) => (
            <Badge
              key={i}
              variant="outline"
              className="gap-1 text-neutral-400 border-neutral-700 font-normal"
            >
              {item.icon}
              {item.text}
            </Badge>
          ))}
        </div>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-neutral-500 shrink-0" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-neutral-500 shrink-0" />
        )}
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3 text-sm">
          {metadata.execution_time_ms != null && (
            <div className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-neutral-500" />
              <span className="text-neutral-400">Execution Time:</span>
              <span className="text-neutral-200 font-mono">
                {metadata.execution_time_ms >= 1000
                  ? `${(metadata.execution_time_ms / 1000).toFixed(2)}s`
                  : `${metadata.execution_time_ms}ms`}
              </span>
            </div>
          )}

          {metadata.guard_status && (
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-neutral-500" />
              <span className="text-neutral-400">Guard Status:</span>
              <Badge variant="outline" className={cn('font-mono', guardInfo.className)}>
                {guardInfo.label}
              </Badge>
            </div>
          )}

          {metadata.guard_fixes && metadata.guard_fixes.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-1">
                <ShieldCheck className="h-3.5 w-3.5 text-amber-500" />
                <span className="text-neutral-400">Guard Fixes:</span>
              </div>
              <ul className="ml-6 space-y-0.5">
                {metadata.guard_fixes.map((fix, i) => (
                  <li key={i} className="text-xs text-amber-300/80">
                    - {fix}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {metadata.tables_used && metadata.tables_used.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Table2 className="h-3.5 w-3.5 text-neutral-500" />
                <span className="text-neutral-400">Tables Used:</span>
              </div>
              <div className="ml-6 flex flex-wrap gap-1">
                {metadata.tables_used.map((table) => (
                  <Badge key={table} variant="secondary" className="text-xs font-mono">
                    {table}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {metadata.schema_source && (
            <div className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5 text-neutral-500" />
              <span className="text-neutral-400">Schema Source:</span>
              <span className="text-neutral-200">{metadata.schema_source}</span>
            </div>
          )}

          {metadata.cache_hit != null && (
            <div className="flex items-center gap-2">
              <Zap className="h-3.5 w-3.5 text-neutral-500" />
              <span className="text-neutral-400">Cache:</span>
              <Badge
                variant="outline"
                className={cn(
                  'font-normal',
                  metadata.cache_hit
                    ? 'border-green-700 text-green-400'
                    : 'border-neutral-700 text-neutral-400'
                )}
              >
                {metadata.cache_hit ? 'HIT' : 'MISS'}
              </Badge>
            </div>
          )}

          {metadata.query_id && (
            <div className="flex items-center gap-2">
              <Hash className="h-3.5 w-3.5 text-neutral-500" />
              <span className="text-neutral-400">Query ID:</span>
              <code className="text-xs text-neutral-300 bg-neutral-800 px-1.5 py-0.5 rounded font-mono">
                {metadata.query_id}
              </code>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5"
                onClick={(e) => {
                  e.stopPropagation();
                  handleCopyQueryId();
                }}
              >
                {copiedQueryId ? (
                  <Check className="h-3 w-3 text-green-500" />
                ) : (
                  <Copy className="h-3 w-3 text-neutral-400" />
                )}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
