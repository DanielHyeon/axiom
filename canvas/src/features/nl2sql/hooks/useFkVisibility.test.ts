/**
 * useFkVisibility 훅 테스트.
 *
 * FK 소스별 가시성 토글 로직을 검증한다.
 */
import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useFkVisibility } from './useFkVisibility';

describe('useFkVisibility', () => {
  it('초기 상태: 모든 소스가 보임', () => {
    const { result } = renderHook(() => useFkVisibility());
    expect(result.current.visibility).toEqual({ ddl: true, user: true, fabric: true });
  });

  it('toggle: ddl을 끄면 ddl만 false', () => {
    const { result } = renderHook(() => useFkVisibility());
    act(() => result.current.toggle('ddl'));
    expect(result.current.visibility.ddl).toBe(false);
    expect(result.current.visibility.user).toBe(true);
    expect(result.current.visibility.fabric).toBe(true);
  });

  it('toggle: 같은 소스를 두 번 토글하면 원래 상태로', () => {
    const { result } = renderHook(() => useFkVisibility());
    act(() => result.current.toggle('fabric'));
    act(() => result.current.toggle('fabric'));
    expect(result.current.visibility.fabric).toBe(true);
  });

  it('toggle: 여러 소스를 독립적으로 토글', () => {
    const { result } = renderHook(() => useFkVisibility());
    act(() => result.current.toggle('ddl'));
    act(() => result.current.toggle('user'));
    expect(result.current.visibility).toEqual({ ddl: false, user: false, fabric: true });
  });

  it('toggle: 모든 소스를 끄면 전부 false', () => {
    const { result } = renderHook(() => useFkVisibility());
    act(() => result.current.toggle('ddl'));
    act(() => result.current.toggle('user'));
    act(() => result.current.toggle('fabric'));
    expect(result.current.visibility).toEqual({ ddl: false, user: false, fabric: false });
  });

  it('isVisible: 소스가 켜져 있으면 true', () => {
    const { result } = renderHook(() => useFkVisibility());
    expect(result.current.isVisible('ddl')).toBe(true);
    expect(result.current.isVisible('user')).toBe(true);
  });

  it('isVisible: 소스가 꺼져 있으면 false', () => {
    const { result } = renderHook(() => useFkVisibility());
    act(() => result.current.toggle('user'));
    expect(result.current.isVisible('user')).toBe(false);
  });

  it('isVisible: undefined 소스는 ddl 기본값 사용', () => {
    const { result } = renderHook(() => useFkVisibility());
    expect(result.current.isVisible(undefined)).toBe(true);
    act(() => result.current.toggle('ddl'));
    expect(result.current.isVisible(undefined)).toBe(false);
  });

  it('isVisible: fabric 소스 토글 후 정확히 반영', () => {
    const { result } = renderHook(() => useFkVisibility());
    expect(result.current.isVisible('fabric')).toBe(true);
    act(() => result.current.toggle('fabric'));
    expect(result.current.isVisible('fabric')).toBe(false);
    act(() => result.current.toggle('fabric'));
    expect(result.current.isVisible('fabric')).toBe(true);
  });
});
