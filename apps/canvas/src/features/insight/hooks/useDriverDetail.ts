// features/insight/hooks/useDriverDetail.ts
// Fetches driver score + evidence from GET /api/insight/drivers/detail.
// Falls back gracefully on 404 — caller reads graph-node data from store.

import { useState, useEffect } from 'react';
import { useInsightStore } from '../store/useInsightStore';
import { fetchDriverDetail } from '../api/insightApi';
import type { DriverDetailResponse, TimeRange } from '../types/insight';

interface UseDriverDetailOptions {
  nodeId: string | null;
}

interface UseDriverDetailReturn {
  detail: DriverDetailResponse | null;
  loading: boolean;
  close: () => void;
}

export function useDriverDetail({ nodeId }: UseDriverDetailOptions): UseDriverDetailReturn {
  const { selectDriver, timeRange } = useInsightStore();
  const [detail, setDetail] = useState<DriverDetailResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!nodeId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    fetchDriverDetail(nodeId, timeRange as TimeRange)
      .then(setDetail)
      .catch(() => setDetail(null))   // 404 → caller falls back to store graph-node data
      .finally(() => setLoading(false));
  }, [nodeId, timeRange]);

  return { detail, loading, close: () => selectDriver(null) };
}
