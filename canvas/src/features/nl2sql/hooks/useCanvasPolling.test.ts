/**
 * useCanvasPolling 훅 테스트.
 *
 * 폴링 기반 캔버스 변경 감지 로직을 검증한다.
 * - 활성/비활성 상태에 따른 폴링 제어
 * - interval에 따른 주기적 API 호출
 * - 변경 감지 시 onUpdate 콜백 호출
 * - 클린업 시 타이머 정리
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCanvasPolling } from './useCanvasPolling';

// synapseApi를 모킹 — 실제 네트워크 요청을 차단한다
const mockGet = vi.fn();
vi.mock('@/lib/api/clients', () => ({
  synapseApi: {
    get: (...args: unknown[]) => mockGet(...args),
  },
}));

describe('useCanvasPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGet.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  // ─── 활성/비활성 제어 ─────────────────────────────────────

  it('enabled=false일 때 API를 호출하지 않는다', () => {
    const onUpdate = vi.fn();
    renderHook(() => useCanvasPolling({ enabled: false, onUpdate }));

    // 10초 지나도 API 호출 없음
    vi.advanceTimersByTime(10000);
    expect(mockGet).not.toHaveBeenCalled();
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('enabled=true일 때 즉시 한 번 체크한다', () => {
    mockGet.mockResolvedValue({ data: { lastModified: null } });
    const onUpdate = vi.fn();

    renderHook(() => useCanvasPolling({ enabled: true, interval: 5000, onUpdate }));

    // 마운트 직후 즉시 호출
    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(mockGet).toHaveBeenCalledWith('/api/v3/synapse/schema-edit/last-modified');
  });

  it('enabled=true일 때 interval마다 반복 체크한다', async () => {
    mockGet.mockResolvedValue({ data: { lastModified: null } });
    const onUpdate = vi.fn();

    renderHook(() => useCanvasPolling({ enabled: true, interval: 1000, onUpdate }));

    // 최초 1회 (즉시)
    expect(mockGet).toHaveBeenCalledTimes(1);

    // 1초 후 추가 호출
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(mockGet).toHaveBeenCalledTimes(2);

    // 2초 후 또 추가 호출
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(mockGet).toHaveBeenCalledTimes(3);
  });

  it('enabled가 false로 바뀌면 폴링을 중단한다', async () => {
    mockGet.mockResolvedValue({ data: { lastModified: null } });
    const onUpdate = vi.fn();

    const { rerender } = renderHook(
      ({ enabled }) => useCanvasPolling({ enabled, interval: 1000, onUpdate }),
      { initialProps: { enabled: true } },
    );

    // 최초 호출
    expect(mockGet).toHaveBeenCalledTimes(1);

    // 비활성화
    rerender({ enabled: false });

    // 이후 시간이 지나도 추가 호출 없음
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  // ─── 변경 감지 콜백 ──────────────────────────────────────

  it('lastModified가 변경되면 onUpdate를 호출한다', async () => {
    // 첫 호출: 기준값 설정
    mockGet.mockResolvedValueOnce({ data: { lastModified: '2026-03-22T00:00:00Z' } });
    // 두 번째 호출: 변경 감지
    mockGet.mockResolvedValueOnce({ data: { lastModified: '2026-03-22T01:00:00Z' } });

    const onUpdate = vi.fn();
    renderHook(() => useCanvasPolling({ enabled: true, interval: 1000, onUpdate }));

    // 첫 번째 호출 완료 대기 — 기준값 저장
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(onUpdate).not.toHaveBeenCalled();

    // 두 번째 호출 — 변경 감지
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(onUpdate).toHaveBeenCalledTimes(1);
  });

  it('lastModified가 동일하면 onUpdate를 호출하지 않는다', async () => {
    const timestamp = '2026-03-22T00:00:00Z';
    mockGet.mockResolvedValue({ data: { lastModified: timestamp } });

    const onUpdate = vi.fn();
    renderHook(() => useCanvasPolling({ enabled: true, interval: 1000, onUpdate }));

    // 기준값 설정
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    // 동일한 값 반복 — onUpdate 호출 없어야 함
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('API 오류 시 조용히 실패하고 onUpdate를 호출하지 않는다', async () => {
    mockGet.mockRejectedValue(new Error('Network Error'));

    const onUpdate = vi.fn();
    renderHook(() => useCanvasPolling({ enabled: true, interval: 1000, onUpdate }));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    // 에러 발생해도 onUpdate 호출 없음
    expect(onUpdate).not.toHaveBeenCalled();
  });

  // ─── 기본값 및 클린업 ────────────────────────────────────

  it('interval 기본값은 5000ms이다', async () => {
    mockGet.mockResolvedValue({ data: { lastModified: null } });
    const onUpdate = vi.fn();

    renderHook(() => useCanvasPolling({ enabled: true, onUpdate }));

    // 최초 즉시 호출
    expect(mockGet).toHaveBeenCalledTimes(1);

    // 4초 후 — 아직 두 번째 호출 없음
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(mockGet).toHaveBeenCalledTimes(1);

    // 5초 후 — 두 번째 호출 발생
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    expect(mockGet).toHaveBeenCalledTimes(2);
  });

  it('unmount 시 타이머를 정리한다', async () => {
    mockGet.mockResolvedValue({ data: { lastModified: null } });
    const onUpdate = vi.fn();

    const { unmount } = renderHook(() =>
      useCanvasPolling({ enabled: true, interval: 1000, onUpdate }),
    );

    expect(mockGet).toHaveBeenCalledTimes(1);

    // unmount 후 시간이 지나도 추가 호출 없음
    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(mockGet).toHaveBeenCalledTimes(1);
  });
});
