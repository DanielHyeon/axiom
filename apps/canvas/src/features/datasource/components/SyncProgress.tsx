import React, { useState, useEffect, useCallback } from 'react';
import { triggerSync, listJobs, type JobItem } from '../api/weaverDatasourceApi';
import { RefreshCw, Loader2 } from 'lucide-react';

interface SyncProgressProps {
  selectedDsName: string | null;
}

const SYNC_JOB_TYPE = 'schema_sync';

export function SyncProgress({ selectedDsName }: SyncProgressProps) {
  const [lastSync, setLastSync] = useState<{ job_id: string; ds: string } | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);

  const loadJobs = useCallback(async () => {
    setJobsLoading(true);
    try {
      const res = await listJobs();
      const syncJobs = (res.jobs ?? []).filter((j) => j.type === SYNC_JOB_TYPE);
      setJobs(syncJobs);
    } catch {
      setJobs([]);
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    const interval = setInterval(loadJobs, 8000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  const handleSync = async () => {
    if (!selectedDsName || syncing) return;
    setSyncing(true);
    setLastSync(null);
    try {
      const res = await triggerSync(selectedDsName);
      setLastSync({ job_id: res.job_id, ds: res.datasource_id });
      await loadJobs();
    } catch (e) {
      console.error('Sync failed', e);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="border border-neutral-200 rounded-lg bg-white overflow-hidden">
      <div className="p-3 border-b border-neutral-200 bg-neutral-50 font-medium text-sm">스키마 동기화</div>
      <div className="p-3 space-y-2">
        <button
          type="button"
          onClick={handleSync}
          disabled={!selectedDsName || syncing}
          className="flex items-center gap-2 text-sm px-3 py-1.5 rounded border border-neutral-300 hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {syncing ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {syncing ? '동기화 중...' : '동기화 시작'}
        </button>
        {lastSync && (
          <p className="text-xs text-neutral-600">
            시작됨: {lastSync.ds} (job: {lastSync.job_id})
          </p>
        )}
        {jobs.length > 0 && (
          <div className="mt-2">
            <p className="text-xs font-medium text-neutral-500 mb-1">최근 동기화 작업</p>
            <ul className="text-xs text-neutral-600 space-y-0.5 max-h-24 overflow-y-auto">
              {jobs.slice(0, 5).map((j) => (
                <li key={j.id}>
                  {j.datasource_id ?? j.id} — {j.status ?? '?'} {j.created_at ? new Date(j.created_at).toLocaleTimeString() : ''}
                </li>
              ))}
            </ul>
          </div>
        )}
        {jobsLoading && jobs.length === 0 && <p className="text-xs text-neutral-400">작업 목록 로딩 중...</p>}
      </div>
    </div>
  );
}
