import React, { useCallback, useEffect, useState } from 'react';
import { checkServiceHealth, type ServiceStatus } from '@/lib/api/health';
import { getCoreReadiness, type CoreReadinessResponse } from '@/lib/api/settingsApi';

/** 설정 > 시스템. Core health/ready 및 서비스별 헬스 연동 (읽기 전용). */
export const SettingsSystemPage: React.FC = () => {
  const [serviceStatuses, setServiceStatuses] = useState<ServiceStatus[]>([]);
  const [coreReadiness, setCoreReadiness] = useState<CoreReadinessResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [statuses, readiness] = await Promise.all([
        checkServiceHealth(),
        getCoreReadiness().catch(() => null),
      ]);
      setServiceStatuses(statuses);
      setCoreReadiness(readiness);
    } catch (e) {
      setError(e instanceof Error ? e.message : '시스템 상태를 불러오지 못했습니다.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-foreground">시스템</h2>
        <p className="text-sm text-neutral-400">로딩 중…</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-foreground">시스템</h2>
      {error && (
        <p className="text-sm text-red-400 bg-red-950/30 border border-red-800 rounded px-3 py-2">
          {error}
        </p>
      )}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-neutral-300">서비스 상태</h3>
        <ul className="border border-neutral-700 rounded divide-y divide-neutral-700">
          {serviceStatuses.map((s) => (
            <li key={s.name} className="px-4 py-2 flex items-center justify-between">
              <span className="text-neutral-100">{s.name}</span>
              <span
                className={
                  s.status === 'up'
                    ? 'text-emerald-400 font-medium'
                    : 'text-red-400 font-medium'
                }
              >
                {s.status === 'up' ? '정상' : '이상'}
              </span>
            </li>
          ))}
        </ul>
      </div>
      {coreReadiness && (
        <div className="space-y-3">
          <h3 className="text-sm font-medium text-neutral-300">Core 상세 (DB / Redis)</h3>
          <ul className="border border-neutral-700 rounded divide-y divide-neutral-700">
            {coreReadiness.checks &&
              Object.entries(coreReadiness.checks).map(([key, value]) => (
                <li key={key} className="px-4 py-2 flex items-center justify-between">
                  <span className="text-neutral-100">{key}</span>
                  <span
                    className={
                      value === 'healthy'
                        ? 'text-emerald-400 font-medium'
                        : 'text-red-400 font-medium'
                    }
                  >
                    {value === 'healthy' ? '정상' : value}
                  </span>
                </li>
              ))}
          </ul>
        </div>
      )}
      <button
        type="button"
        onClick={() => load()}
        className="rounded border border-neutral-600 text-neutral-200 px-4 py-2 text-sm hover:bg-neutral-800"
      >
        새로고침
      </button>
    </div>
  );
};
