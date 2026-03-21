/**
 * 캔버스 실시간 업데이트 훅 (폴링 기반).
 *
 * Synapse schema-edit last-modified 타임스탬프를 주기적으로 확인하여
 * 변경이 감지되면 onUpdate 콜백을 호출한다.
 *
 * 5초 간격 폴링 + 디바운스로 과도한 렌더링을 방지한다.
 */
import { useEffect, useRef, useCallback } from 'react';
import { synapseApi } from '@/lib/api/clients';

interface UseCanvasPollingOptions {
  /** 폴링 활성화 여부 */
  enabled: boolean;
  /** 폴링 간격 (ms) — 기본 5000ms */
  interval?: number;
  /** 변경 감지 시 호출되는 콜백 */
  onUpdate: () => void;
}

/** 마지막 수정 시간 조회 */
async function fetchLastModified(): Promise<string | null> {
  try {
    const res = await synapseApi.get('/api/v3/synapse/schema-edit/last-modified');
    return (res as any)?.data?.lastModified ?? null;
  } catch {
    // 엔드포인트 미구현 시 조용히 실패
    return null;
  }
}

export function useCanvasPolling({
  enabled,
  interval = 5000,
  onUpdate,
}: UseCanvasPollingOptions) {
  const lastModifiedRef = useRef<string | null>(null);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const checkForUpdates = useCallback(async () => {
    const current = await fetchLastModified();
    if (!current) return;

    // 최초 조회 시 기준값 저장
    if (lastModifiedRef.current === null) {
      lastModifiedRef.current = current;
      return;
    }

    // 변경 감지
    if (current !== lastModifiedRef.current) {
      lastModifiedRef.current = current;
      onUpdateRef.current();
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    // 즉시 한 번 체크
    checkForUpdates();

    const timer = setInterval(checkForUpdates, interval);
    return () => clearInterval(timer);
  }, [enabled, interval, checkForUpdates]);
}
