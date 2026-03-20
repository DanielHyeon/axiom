/**
 * Watch 알림 스트림 (SSE). EventSource 기반 단일 연결.
 * Core GET /api/v1/watches/stream 이벤트: alert, alert_update, heartbeat.
 * @see docs/04_frontend/event-streams.md
 */
export interface WatchStreamCallbacks {
  onAlert: (data: Record<string, unknown>) => void;
  onAlertUpdate?: (data: { alert_id: string; status: string }) => void;
  onHeartbeat?: (data: { timestamp: string }) => void;
  onError?: (error: Event) => void;
}

let watchEventSource: EventSource | null = null;

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/$/, '');
}

/**
 * Watch SSE 스트림 구독 (단일 연결). 해제 시 반환된 함수 호출.
 */
export function subscribeWatchStream(
  baseUrl: string,
  token: string,
  callbacks: WatchStreamCallbacks
): () => void {
  disconnectWatchStream();
  const url = `${normalizeBaseUrl(baseUrl)}/api/v1/watches/stream?token=${encodeURIComponent(token)}`;
  const eventSource = new EventSource(url);
  watchEventSource = eventSource;

  function getData(ev: Event): string {
    return (ev as MessageEvent).data ?? '';
  }

  function handlerAlert(ev: Event) {
    try {
      const data = JSON.parse(getData(ev)) as Record<string, unknown>;
      callbacks.onAlert(data);
    } catch (err) {
      console.error('Watch stream parse alert', err);
    }
  }

  function handlerAlertUpdate(ev: Event) {
    try {
      const data = JSON.parse(getData(ev)) as { alert_id: string; status: string };
      callbacks.onAlertUpdate?.(data);
    } catch (err) {
      console.error('Watch stream parse alert_update', err);
    }
  }

  function handlerHeartbeat(ev: Event) {
    try {
      const data = JSON.parse(getData(ev)) as { timestamp: string };
      callbacks.onHeartbeat?.(data);
    } catch {
      // ignore
    }
  }

  eventSource.addEventListener('alert', handlerAlert);
  eventSource.addEventListener('alert_update', handlerAlertUpdate);
  eventSource.addEventListener('heartbeat', handlerHeartbeat);
  eventSource.onerror = (e) => {
    callbacks.onError?.(e);
  };

  return () => {
    eventSource.removeEventListener('alert', handlerAlert);
    eventSource.removeEventListener('alert_update', handlerAlertUpdate);
    eventSource.removeEventListener('heartbeat', handlerHeartbeat);
    eventSource.onerror = null;
    eventSource.close();
    if (watchEventSource === eventSource) {
      watchEventSource = null;
    }
  };
}

/** Watch 스트림 연결 해제 (수동 정리용). */
export function disconnectWatchStream(): void {
  if (watchEventSource) {
    watchEventSource.close();
    watchEventSource = null;
  }
}
