// features/insight/hooks/useDriverDetail.ts
// Fetches driver score + evidence from GET /api/insight/drivers/detail.
// Falls back gracefully on 404 — caller reads graph-node data from store.

import { useState, useEffect } from 'react';
import { toast } from 'sonner';
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
      .catch((err: unknown) => {
        // 404는 정상 — API 미구현 상태에서 store 데이터로 폴백
        const is404 = err instanceof Error && 'status' in err && (err as { status: number }).status === 404;
        if (!is404) {
          const msg = err instanceof Error ? err.message : '알 수 없는 오류';
          toast.error('드라이버 상세 로딩 실패', { description: msg });
        }
        setDetail(null);
      })
      .finally(() => setLoading(false));
  }, [nodeId, timeRange]);

  return { detail, loading, close: () => selectDriver(null) };
}
