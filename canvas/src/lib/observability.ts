/**
 * 프론트엔드 운영 관측성 — 에러 추적 + Web Vitals.
 * Phase 2: 최소 에러 수집 + 성능 메트릭.
 *
 * Sentry 등 외부 서비스 연동 전 단계로,
 * console 기반 구조화 로깅 + TanStack Query 글로벌 에러 핸들러를 설정한다.
 *
 * 사용법: main.tsx에서 `initObservability()` 호출.
 */

/** 구조화된 에러 로그 — 운영 환경에서 수집 가능한 형태 */
interface ErrorLog {
  type: 'unhandled_error' | 'unhandled_rejection' | 'query_error' | 'mutation_error' | 'ws_error';
  message: string;
  stack?: string;
  url: string;
  timestamp: string;
  extra?: Record<string, unknown>;
}

function logError(entry: ErrorLog): void {
  // 개발: 콘솔 출력
  // 운영: 여기를 Sentry/LogRocket/커스텀 엔드포인트로 교체
  if (import.meta.env.DEV) {
    console.error('[FE-ERROR]', entry);
  } else {
    // 운영 환경: beacon API로 에러 전송 (페이지 언로드 시에도 전송 보장)
    try {
      navigator.sendBeacon(
        '/api/v1/telemetry/fe-errors',
        JSON.stringify(entry),
      );
    } catch {
      console.error('[FE-ERROR]', entry);
    }
  }
}

/** 글로벌 에러 핸들러 등록 */
export function initObservability(): void {
  // 1. 미처리 에러
  window.addEventListener('error', (event) => {
    logError({
      type: 'unhandled_error',
      message: event.message,
      stack: event.error?.stack,
      url: window.location.href,
      timestamp: new Date().toISOString(),
    });
  });

  // 2. 미처리 Promise rejection
  window.addEventListener('unhandledrejection', (event) => {
    logError({
      type: 'unhandled_rejection',
      message: String(event.reason),
      stack: event.reason?.stack,
      url: window.location.href,
      timestamp: new Date().toISOString(),
    });
  });

  // 3. Web Vitals 수집 (web-vitals 패키지 설치 시)
  initWebVitals();
}

/** TanStack Query 글로벌 에러 핸들러 — queryClient 설정에 사용 */
export function onQueryError(error: unknown): void {
  logError({
    type: 'query_error',
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : undefined,
    url: window.location.href,
    timestamp: new Date().toISOString(),
  });
}

export function onMutationError(error: unknown): void {
  logError({
    type: 'mutation_error',
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack : undefined,
    url: window.location.href,
    timestamp: new Date().toISOString(),
  });
}

/** Web Vitals 메트릭 수집 */
async function initWebVitals(): Promise<void> {
  try {
    const { onCLS, onFID, onLCP } = await import('web-vitals');
    const report = (metric: { name: string; value: number }) => {
      if (import.meta.env.DEV) {
        console.log(`[Web-Vital] ${metric.name}: ${metric.value.toFixed(2)}`);
      }
    };
    onCLS(report);
    onFID(report);
    onLCP(report);
  } catch {
    // web-vitals 미설치 — 무시
  }
}
