/**
 * Watch SSE 스트림 테스트 — EventSource 기반 실시간 알림 플로우 검증.
 *
 * 고위험 플로우:
 * - 연결 수립 및 URL 생성 (토큰 포함)
 * - 이벤트 타입별 핸들러 등록 (alert, alert_update, heartbeat)
 * - JSON 파싱 에러 시 크래시 방지
 * - 정리(cleanup) 함수 호출 시 리스너 해제 + close
 * - disconnectWatchStream으로 수동 연결 해제
 * - 중복 구독 시 이전 연결 자동 해제
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ── EventSource 모킹 ──

type EventListenerFn = (event: Event) => void;

class MockEventSource {
  url: string;
  listeners: Record<string, EventListenerFn[]> = {};
  onerror: ((e: Event) => void) | null = null;
  closed = false;

  static instances: MockEventSource[] = [];

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: EventListenerFn) {
    if (!this.listeners[type]) {
      this.listeners[type] = [];
    }
    this.listeners[type].push(handler);
  }

  removeEventListener(type: string, handler: EventListenerFn) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((h) => h !== handler);
    }
  }

  close() {
    this.closed = true;
  }

  // 테스트 헬퍼: 이벤트 디스패치
  _dispatch(type: string, data: string) {
    const event = { data } as MessageEvent;
    (this.listeners[type] || []).forEach((h) => h(event));
  }

  _dispatchError() {
    const event = new Event('error');
    if (this.onerror) this.onerror(event);
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal('EventSource', MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

async function getModule() {
  vi.resetModules();
  return import('./watchStream');
}

// ═══════════════════════════════════════════════════════════════
// 1. 연결 수립
// ═══════════════════════════════════════════════════════════════

describe('subscribeWatchStream — 연결 수립', () => {
  it('올바른 URL로 EventSource를 생성한다 (토큰 인코딩 포함)', async () => {
    const { subscribeWatchStream } = await getModule();

    subscribeWatchStream('http://core:9002', 'my-jwt-token', {
      onAlert: vi.fn(),
    });

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toBe(
      'http://core:9002/api/v1/watches/stream?token=my-jwt-token',
    );
  });

  it('baseUrl 뒤의 슬래시를 제거한다', async () => {
    const { subscribeWatchStream } = await getModule();

    subscribeWatchStream('http://core:9002/', 'token-123', {
      onAlert: vi.fn(),
    });

    expect(MockEventSource.instances[0].url).toContain('http://core:9002/api/v1/watches/stream');
    expect(MockEventSource.instances[0].url).not.toContain('//api');
  });

  it('토큰에 특수문자가 있으면 URL 인코딩된다', async () => {
    const { subscribeWatchStream } = await getModule();

    subscribeWatchStream('http://core:9002', 'token/with+special=chars', {
      onAlert: vi.fn(),
    });

    expect(MockEventSource.instances[0].url).toContain(
      'token=' + encodeURIComponent('token/with+special=chars'),
    );
  });

  it('구독 시 3종 이벤트 리스너가 등록된다 (alert, alert_update, heartbeat)', async () => {
    const { subscribeWatchStream } = await getModule();

    subscribeWatchStream('http://core:9002', 'token', {
      onAlert: vi.fn(),
      onAlertUpdate: vi.fn(),
      onHeartbeat: vi.fn(),
    });

    const es = MockEventSource.instances[0];
    expect(es.listeners['alert']).toHaveLength(1);
    expect(es.listeners['alert_update']).toHaveLength(1);
    expect(es.listeners['heartbeat']).toHaveLength(1);
  });
});

// ═══════════════════════════════════════════════════════════════
// 2. 이벤트 핸들링
// ═══════════════════════════════════════════════════════════════

describe('subscribeWatchStream — 이벤트 핸들링', () => {
  it('alert 이벤트 수신 시 onAlert 콜백이 파싱된 데이터로 호출된다', async () => {
    const { subscribeWatchStream } = await getModule();
    const onAlert = vi.fn();

    subscribeWatchStream('http://core:9002', 'token', { onAlert });

    const es = MockEventSource.instances[0];
    es._dispatch('alert', JSON.stringify({ rule_id: 'r-1', severity: 'high' }));

    expect(onAlert).toHaveBeenCalledWith({ rule_id: 'r-1', severity: 'high' });
  });

  it('alert_update 이벤트 수신 시 onAlertUpdate 콜백이 호출된다', async () => {
    const { subscribeWatchStream } = await getModule();
    const onAlertUpdate = vi.fn();

    subscribeWatchStream('http://core:9002', 'token', {
      onAlert: vi.fn(),
      onAlertUpdate,
    });

    const es = MockEventSource.instances[0];
    es._dispatch('alert_update', JSON.stringify({ alert_id: 'a-1', status: 'acknowledged' }));

    expect(onAlertUpdate).toHaveBeenCalledWith({ alert_id: 'a-1', status: 'acknowledged' });
  });

  it('heartbeat 이벤트 수신 시 onHeartbeat 콜백이 호출된다', async () => {
    const { subscribeWatchStream } = await getModule();
    const onHeartbeat = vi.fn();

    subscribeWatchStream('http://core:9002', 'token', {
      onAlert: vi.fn(),
      onHeartbeat,
    });

    const es = MockEventSource.instances[0];
    es._dispatch('heartbeat', JSON.stringify({ timestamp: '2026-03-24T12:00:00Z' }));

    expect(onHeartbeat).toHaveBeenCalledWith({ timestamp: '2026-03-24T12:00:00Z' });
  });

  it('유효하지 않은 JSON이 오면 콜백을 호출하지 않고 에러를 삼킨다', async () => {
    const { subscribeWatchStream } = await getModule();
    const onAlert = vi.fn();
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    subscribeWatchStream('http://core:9002', 'token', { onAlert });

    const es = MockEventSource.instances[0];
    es._dispatch('alert', '{{invalid json}}');

    expect(onAlert).not.toHaveBeenCalled();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it('error 이벤트 발생 시 onError 콜백이 호출된다', async () => {
    const { subscribeWatchStream } = await getModule();
    const onError = vi.fn();

    subscribeWatchStream('http://core:9002', 'token', {
      onAlert: vi.fn(),
      onError,
    });

    const es = MockEventSource.instances[0];
    es._dispatchError();

    expect(onError).toHaveBeenCalledTimes(1);
  });

  it('선택적 콜백(onAlertUpdate, onHeartbeat)이 없어도 에러 없이 동작한다', async () => {
    const { subscribeWatchStream } = await getModule();

    subscribeWatchStream('http://core:9002', 'token', {
      onAlert: vi.fn(),
      // onAlertUpdate, onHeartbeat 미제공
    });

    const es = MockEventSource.instances[0];
    // 에러 없이 이벤트 처리되어야 함
    expect(() => {
      es._dispatch('alert_update', JSON.stringify({ alert_id: 'a-1', status: 'ok' }));
      es._dispatch('heartbeat', JSON.stringify({ timestamp: 'now' }));
    }).not.toThrow();
  });
});

// ═══════════════════════════════════════════════════════════════
// 3. 정리(cleanup) + 연결 해제
// ═══════════════════════════════════════════════════════════════

describe('subscribeWatchStream — 정리(cleanup)', () => {
  it('반환된 cleanup 함수 호출 시 EventSource가 close된다', async () => {
    const { subscribeWatchStream } = await getModule();

    const cleanup = subscribeWatchStream('http://core:9002', 'token', {
      onAlert: vi.fn(),
    });

    const es = MockEventSource.instances[0];
    expect(es.closed).toBe(false);

    cleanup();

    expect(es.closed).toBe(true);
  });

  it('cleanup 후 이벤트 리스너가 제거된다', async () => {
    const { subscribeWatchStream } = await getModule();

    const cleanup = subscribeWatchStream('http://core:9002', 'token', {
      onAlert: vi.fn(),
      onAlertUpdate: vi.fn(),
      onHeartbeat: vi.fn(),
    });

    const es = MockEventSource.instances[0];
    expect(es.listeners['alert']).toHaveLength(1);

    cleanup();

    expect(es.listeners['alert']).toHaveLength(0);
    expect(es.listeners['alert_update']).toHaveLength(0);
    expect(es.listeners['heartbeat']).toHaveLength(0);
    expect(es.onerror).toBeNull();
  });
});

describe('disconnectWatchStream — 수동 연결 해제', () => {
  it('활성 연결이 있으면 close된다', async () => {
    const { subscribeWatchStream, disconnectWatchStream } = await getModule();

    subscribeWatchStream('http://core:9002', 'token', { onAlert: vi.fn() });
    const es = MockEventSource.instances[0];

    disconnectWatchStream();

    expect(es.closed).toBe(true);
  });

  it('활성 연결이 없으면 에러 없이 무시된다', async () => {
    const { disconnectWatchStream } = await getModule();

    expect(() => disconnectWatchStream()).not.toThrow();
  });
});

describe('subscribeWatchStream — 중복 구독 방어', () => {
  it('새 구독 시 이전 EventSource가 자동으로 close된다', async () => {
    const { subscribeWatchStream } = await getModule();

    subscribeWatchStream('http://core:9002', 'token-1', { onAlert: vi.fn() });
    const firstEs = MockEventSource.instances[0];

    // 두 번째 구독 — 첫 번째가 자동 해제되어야 함
    subscribeWatchStream('http://core:9002', 'token-2', { onAlert: vi.fn() });
    const secondEs = MockEventSource.instances[1];

    expect(firstEs.closed).toBe(true);
    expect(secondEs.closed).toBe(false);
  });
});
