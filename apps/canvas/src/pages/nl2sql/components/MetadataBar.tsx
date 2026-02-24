import type { ExecutionMetadata } from '@/features/nl2sql/types/nl2sql';
import { Badge } from '@/components/ui/badge';
import { Clock, Table2, Search, ShieldCheck } from 'lucide-react';

interface MetadataBarProps {
  metadata: ExecutionMetadata | null | undefined;
}

export function MetadataBar({ metadata }: MetadataBarProps) {
  if (!metadata) return null;

  const items: { icon: React.ReactNode; text: string }[] = [];

  if (metadata.execution_time_ms != null) {
    items.push({
      icon: <Clock className="h-3 w-3" />,
      text: `${metadata.execution_time_ms}ms`,
    });
  }

  if (metadata.tables_used && metadata.tables_used.length > 0) {
    items.push({
      icon: <Table2 className="h-3 w-3" />,
      text: `${metadata.tables_used.length} tables`,
    });
  }

  if (metadata.schema_source) {
    items.push({
      icon: <Search className="h-3 w-3" />,
      text: metadata.schema_source,
    });
  }

  if (metadata.guard_status) {
    items.push({
      icon: <ShieldCheck className="h-3 w-3" />,
      text: metadata.guard_status,
    });
  }

  if (items.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 py-2">
      {items.map((item, i) => (
        <Badge key={i} variant="outline" className="gap-1 text-neutral-400 border-neutral-700 font-normal">
          {item.icon}
          {item.text}
        </Badge>
      ))}
    </div>
  );
}
