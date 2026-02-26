// features/insight/hooks/useDriverDetail.ts
// Hook stub — Phase 2 uses graph-derived node data directly (no separate API yet).
// When GET /api/insight/nodes/{id} is implemented on Weaver, replace the body here.

import { useInsightStore } from '../store/useInsightStore';

interface UseDriverDetailOptions {
  nodeId: string | null;
}

/**
 * Returns close handler for the NodeDetailPanel.
 * All data (graphNode, evidence) is read directly from the store by InsightPage.
 */
export function useDriverDetail({ nodeId: _nodeId }: UseDriverDetailOptions) {
  const { selectDriver } = useInsightStore();

  return {
    close: () => selectDriver(null),
  };
}
