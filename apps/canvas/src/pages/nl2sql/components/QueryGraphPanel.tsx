// pages/nl2sql/components/QueryGraphPanel.tsx
// NL2SQL Graph tab content — wraps QuerySubgraphViewer

import { QuerySubgraphViewer } from '@/features/insight/components/QuerySubgraphViewer';

interface QueryGraphPanelProps {
  sql?: string;
}

export function QueryGraphPanel({ sql }: QueryGraphPanelProps) {
  return (
    <div className="p-3">
      <QuerySubgraphViewer sql={sql} />
    </div>
  );
}
