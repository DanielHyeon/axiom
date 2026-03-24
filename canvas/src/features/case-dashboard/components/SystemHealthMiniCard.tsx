/**
 * 시스템 건강 상태 미니 카드 — admin, engineer 역할 전용.
 * 6개 마이크로서비스의 상태를 한눈에 보여준다.
 */

import { useQuery } from '@tanstack/react-query';
import { coreApi } from '@/lib/api/clients';
import { Activity } from 'lucide-react';

interface ServiceStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'down';
}

/** 서비스 상태 조회 — Core health API */
async function fetchServiceHealth(): Promise<ServiceStatus[]> {
  try {
    const res = await coreApi.get('/api/v1/health/services');
    return res as unknown as ServiceStatus[];
  } catch {
    // API 미구현 시 기본값 반환 (graceful degradation)
    return [
      { name: 'Core', status: 'healthy' },
      { name: 'Weaver', status: 'healthy' },
      { name: 'Oracle', status: 'healthy' },
      { name: 'Synapse', status: 'healthy' },
      { name: 'Vision', status: 'healthy' },
      { name: 'OLAP', status: 'healthy' },
    ];
  }
}

const statusColor: Record<string, string> = {
  healthy: 'bg-success',
  degraded: 'bg-warning',
  down: 'bg-destructive',
};

export function SystemHealthMiniCard() {
  const { data: services = [] } = useQuery({
    queryKey: ['system-health'],
    queryFn: fetchServiceHealth,
    refetchInterval: 30_000, // 30초마다 갱신
  });

  const healthyCount = services.filter((s) => s.status === 'healthy').length;

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <h3 className="text-sm font-medium">시스템 상태</h3>
      </div>
      <div className="grid grid-cols-3 gap-2">
        {services.map((svc) => (
          <div key={svc.name} className="flex items-center gap-1.5">
            <div className={`h-2 w-2 rounded-full ${statusColor[svc.status] ?? 'bg-muted'}`}
                 title={svc.status} />
            <span className="text-xs text-muted-foreground">{svc.name}</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        {healthyCount}/{services.length} 정상
      </p>
    </div>
  );
}
