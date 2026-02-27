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
  PASS: { className: 'border-green-300 text-green-600', label: 'PASS' },
  FIX: { className: 'border-amber-300 text-amber-600', label: 'FIX' },
  REJECT: { className: 'border-red-300 text-red-600', label: 'REJECT' },
};

export function MetadataPanel({ metadata }: MetadataPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [copiedQueryId, setCopiedQueryId] = useState(false);

  if (!metadata) return null;

  const guardInfo = GUARD_VARIANT[metadata.guard_status ?? ''] ?? {
    className: 'border-[#E5E5E5] text-[#999]',
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
    <div className="border-t border-[#E5E5E5]">
      {/* Collapsed summary row */}
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center justify-between px-3 py-2 hover:bg-[#F5F5F5] transition-colors"
      >
        <div className="flex flex-wrap items-center gap-2">
          {summaryItems.map((item, i) => (
            <Badge
              key={i}
              variant="outline"
              className="gap-1 text-[#999] border-[#E5E5E5] font-normal font-[IBM_Plex_Mono]"
            >
              {item.icon}
              {item.text}
            </Badge>
          ))}
        </div>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-[#999] shrink-0" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-[#999] shrink-0" />
        )}
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-3 pb-3 space-y-3 text-sm">
          {metadata.execution_time_ms != null && (
            <div className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-[#999]" />
              <span className="text-[#999] font-[IBM_Plex_Mono]">Execution Time:</span>
              <span className="text-black font-[IBM_Plex_Mono]">
                {metadata.execution_time_ms >= 1000
                  ? `${(metadata.execution_time_ms / 1000).toFixed(2)}s`
                  : `${metadata.execution_time_ms}ms`}
              </span>
            </div>
          )}

          {metadata.guard_status && (
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-[#999]" />
              <span className="text-[#999] font-[IBM_Plex_Mono]">Guard Status:</span>
              <Badge variant="outline" className={cn('font-[IBM_Plex_Mono]', guardInfo.className)}>
                {guardInfo.label}
              </Badge>
            </div>
          )}

          {metadata.guard_fixes && metadata.guard_fixes.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-1">
                <ShieldCheck className="h-3.5 w-3.5 text-amber-500" />
                <span className="text-[#999] font-[IBM_Plex_Mono]">Guard Fixes:</span>
              </div>
              <ul className="ml-6 space-y-0.5">
                {metadata.guard_fixes.map((fix, i) => (
                  <li key={i} className="text-xs text-amber-600 font-[IBM_Plex_Mono]">
                    - {fix}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {metadata.tables_used && metadata.tables_used.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Table2 className="h-3.5 w-3.5 text-[#999]" />
                <span className="text-[#999] font-[IBM_Plex_Mono]">Tables Used:</span>
              </div>
              <div className="ml-6 flex flex-wrap gap-1">
                {metadata.tables_used.map((table) => (
                  <Badge key={table} variant="secondary" className="text-xs font-[IBM_Plex_Mono]">
                    {table}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {metadata.schema_source && (
            <div className="flex items-center gap-2">
              <Search className="h-3.5 w-3.5 text-[#999]" />
              <span className="text-[#999] font-[IBM_Plex_Mono]">Schema Source:</span>
              <span className="text-black font-[IBM_Plex_Mono]">{metadata.schema_source}</span>
            </div>
          )}

          {metadata.cache_hit != null && (
            <div className="flex items-center gap-2">
              <Zap className="h-3.5 w-3.5 text-[#999]" />
              <span className="text-[#999] font-[IBM_Plex_Mono]">Cache:</span>
              <Badge
                variant="outline"
                className={cn(
                  'font-normal font-[IBM_Plex_Mono]',
                  metadata.cache_hit
                    ? 'border-green-300 text-green-600'
                    : 'border-[#E5E5E5] text-[#999]'
                )}
              >
                {metadata.cache_hit ? 'HIT' : 'MISS'}
              </Badge>
            </div>
          )}

          {metadata.query_id && (
            <div className="flex items-center gap-2">
              <Hash className="h-3.5 w-3.5 text-[#999]" />
              <span className="text-[#999] font-[IBM_Plex_Mono]">Query ID:</span>
              <code className="text-xs text-[#5E5E5E] bg-[#F5F5F5] px-1.5 py-0.5 rounded font-[IBM_Plex_Mono]">
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
                  <Copy className="h-3 w-3 text-[#999]" />
                )}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
