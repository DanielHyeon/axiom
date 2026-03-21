/**
 * useDisplayMode 훅 테스트.
 *
 * 논리명/물리명 전환 로직을 검증한다.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDisplayMode } from './useDisplayMode';

describe('useDisplayMode', () => {
  it('기본 모드: physical', () => {
    const { result } = renderHook(() => useDisplayMode());
    expect(result.current.displayMode).toBe('physical');
  });

  it('초기값 지정: logical로 시작', () => {
    const { result } = renderHook(() => useDisplayMode('logical'));
    expect(result.current.displayMode).toBe('logical');
  });

  it('초기값 지정: physical로 시작', () => {
    const { result } = renderHook(() => useDisplayMode('physical'));
    expect(result.current.displayMode).toBe('physical');
  });

  it('toggleDisplayMode: physical ↔ logical 전환', () => {
    const { result } = renderHook(() => useDisplayMode());
    act(() => result.current.toggleDisplayMode());
    expect(result.current.displayMode).toBe('logical');
    act(() => result.current.toggleDisplayMode());
    expect(result.current.displayMode).toBe('physical');
  });

  it('toggleDisplayMode: logical에서 시작해도 정상 전환', () => {
    const { result } = renderHook(() => useDisplayMode('logical'));
    act(() => result.current.toggleDisplayMode());
    expect(result.current.displayMode).toBe('physical');
    act(() => result.current.toggleDisplayMode());
    expect(result.current.displayMode).toBe('logical');
  });

  it('getDisplayName: physical 모드에서는 항상 name 반환', () => {
    const { result } = renderHook(() => useDisplayMode('physical'));
    expect(result.current.getDisplayName('orders', '주문 테이블')).toBe('orders');
    expect(result.current.getDisplayName('orders', null)).toBe('orders');
    expect(result.current.getDisplayName('orders')).toBe('orders');
  });

  it('getDisplayName: logical 모드에서 description이 있으면 description', () => {
    const { result } = renderHook(() => useDisplayMode('logical'));
    expect(result.current.getDisplayName('orders', '주문 테이블')).toBe('주문 테이블');
  });

  it('getDisplayName: logical 모드에서 description이 없으면 name 폴백', () => {
    const { result } = renderHook(() => useDisplayMode('logical'));
    expect(result.current.getDisplayName('orders', null)).toBe('orders');
    expect(result.current.getDisplayName('orders', undefined)).toBe('orders');
    expect(result.current.getDisplayName('orders', '')).toBe('orders');
  });

  it('getDisplayName: 토글 후 모드에 맞는 값 반환', () => {
    const { result } = renderHook(() => useDisplayMode('physical'));
    // physical 모드 — name 반환
    expect(result.current.getDisplayName('users', '사용자')).toBe('users');
    // logical 모드로 전환
    act(() => result.current.toggleDisplayMode());
    expect(result.current.getDisplayName('users', '사용자')).toBe('사용자');
    // 다시 physical 모드
    act(() => result.current.toggleDisplayMode());
    expect(result.current.getDisplayName('users', '사용자')).toBe('users');
  });

  it('getDisplayName: logical 모드에서 긴 description도 정상 반환', () => {
    const { result } = renderHook(() => useDisplayMode('logical'));
    const longDesc = '이것은 매우 긴 비즈니스 설명입니다 — 주문 관련 모든 데이터를 포함합니다';
    expect(result.current.getDisplayName('order_items', longDesc)).toBe(longDesc);
  });
});
