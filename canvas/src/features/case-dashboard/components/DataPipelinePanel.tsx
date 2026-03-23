/**
 * 데이터 파이프라인 상태 패널 — engineer 역할 전용.
 * 데이터소스 연결 상태와 최근 동기화 현황을 보여준다.
 */

import { useQuery } from '@tanstack/react-query';
import { weaverApi } from '@/lib/api/clients';
import { Database, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

interface DatasourceStatus {
  name: string;
  engine: string;
  status: 'connected' | 'syncing' | 'error' | 'idle';
  lastSync?: string;
}

/** 데이터소스 상태 조회 */
async function fetchDatasourceStatus(): Promise<DatasourceStatus[]> {
  try {
    const res = await weaverApi.get('/api/datasources');
    const list = res as unknown as Array<Record<string, unknown>>;
    return list.map((ds) => ({
      name: String(ds.name ?? ''),
      engine: String(ds.engine ?? ''),
      status: (ds.status as DatasourceStatus['status']) ?? 'idle',
      lastSync: ds.last_sync ? String(ds.last_sync) : undefined,
    }));
  } catch {
    return [];
  }
}

const statusBadge: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
  connected: { variant: 'default', label: '연결됨' },
  syncing: { variant: 'secondary', label: '동기화중' },
  error: { variant: 'destructive', label: '오류' },
  idle: { variant: 'outline', label: '대기' },
};

export function DataPipelinePanel() {
  const { data: sources = [] } = useQuery({
    queryKey: ['datasource-status'],
    queryFn: fetchDatasourceStatus,
    refetchInterval: 60_000,
  });

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Database className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <h3 className="text-sm font-medium">데이터 파이프라인</h3>
      </div>

      {sources.length === 0 ? (
        <p className="text-xs text-muted-foreground">연결된 데이터소스가 없습니다</p>
      ) : (
        <div className="space-y-2">
          {sources.slice(0, 5).map((ds) => {
            const badge = statusBadge[ds.status] ?? statusBadge.idle;
            return (
              <div key={ds.name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2 min-w-0">
                  {ds.status === 'syncing' && <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />}
                  <span className="truncate">{ds.name}</span>
                  <span className="text-xs text-muted-foreground">({ds.engine})</span>
                </div>
                <Badge variant={badge.variant} className="text-xs shrink-0">{badge.label}</Badge>
              </div>
            );
          })}
          {sources.length > 5 && (
            <p className="text-xs text-muted-foreground">외 {sources.length - 5}개</p>
          )}
        </div>
      )}
    </div>
  );
}
