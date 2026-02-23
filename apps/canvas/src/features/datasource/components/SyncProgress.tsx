import React, { useState } from 'react';
import { extractMetadataStream } from '../api/weaverDatasourceApi';
import { RefreshCw, Loader2 } from 'lucide-react';

interface SyncProgressProps {
  selectedDsName: string | null;
  onComplete?: () => void;
}

export function SyncProgress({ selectedDsName, onComplete }: SyncProgressProps) {
  const [syncing, setSyncing] = useState(false);
  const [progress, setProgress] = useState<{ phase?: string; percent?: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSync = async () => {
    if (!selectedDsName || syncing) return;
    setSyncing(true);
    setProgress(null);
    setError(null);
    try {
      await extractMetadataStream(
        selectedDsName,
        {},
        {
          onProgress: (data) => setProgress({ phase: data.phase, percent: data.percent }),
          onComplete: () => {
            setSyncing(false);
            setProgress(null);
            onComplete?.();
          },
          onNeo4jSaved: () => {
            setSyncing(false);
            setProgress(null);
            onComplete?.();
          },
          onError: (data) => setError(data.message ?? '오류 발생'),
        }
      );
      setSyncing(false);
      setProgress(null);
      onComplete?.();
    } catch (e) {
      setSyncing(false);
      setProgress(null);
      setError(e instanceof Error ? e.message : '동기화 실패');
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
          {syncing ? (progress?.percent != null ? `동기화 중 ${progress.percent}%` : '동기화 중...') : '동기화 시작'}
        </button>
        {progress?.phase && (
          <p className="text-xs text-neutral-600">
            {progress.phase}
            {progress.percent != null ? ` — ${progress.percent}%` : ''}
          </p>
        )}
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    </div>
  );
}
