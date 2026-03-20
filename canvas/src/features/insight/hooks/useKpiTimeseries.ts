// features/insight/hooks/useKpiTimeseries.ts
// Fetches KPI query-activity timeseries from GET /api/insight/kpi/activity (P2-A Phase 1).
// series_type is always "activity" (query count per day/week) — not KPI value timeseries.

import { useState, useEffect } from 'react';
import { fetchKpiActivity } from '../api/insightApi';
import type { ActivityPoint } from '../api/insightApi';
import type { TimeRange } from '../types/insight';

interface UseKpiTimeseriesParams {
  kpiFingerprint: string | null;
  driverKey?: string;
  timeRange: TimeRange;
  granularity?: 'day' | 'week';
}

interface UseKpiTimeseriesReturn {
  data: ActivityPoint[];
  loading: boolean;
}

export function useKpiTimeseries({
  kpiFingerprint,
  driverKey,
  timeRange,
  granularity = 'day',
}: UseKpiTimeseriesParams): UseKpiTimeseriesReturn {
  const [data, setData] = useState<ActivityPoint[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!kpiFingerprint) {
      setData([]);
      return;
    }
    setLoading(true);
    fetchKpiActivity({ kpiFingerprint, driverKey, timeRange, granularity })
      .then((res) => setData(res.series))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [kpiFingerprint, driverKey, timeRange, granularity]);

  return { data, loading };
}
