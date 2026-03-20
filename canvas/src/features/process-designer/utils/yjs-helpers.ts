// features/process-designer/utils/yjs-helpers.ts
// Yjs CRDT 변환 헬퍼 — K-AIR store.ts의 toYMap/toYArray를 TypeScript로 이식.

import * as Y from 'yjs';

/**
 * JS 객체를 Y.Map으로 깊은 변환.
 * 중첩 객체/배열도 재귀적으로 Yjs 타입으로 변환한다.
 */
export function toYMap(obj: Record<string, unknown>): Y.Map<unknown> {
  const map = new Y.Map<unknown>();
  for (const key in obj) {
    const value = obj[key];
    if (Array.isArray(value)) {
      map.set(key, toYArray(value));
    } else if (typeof value === 'object' && value !== null) {
      map.set(key, toYMap(value as Record<string, unknown>));
    } else {
      map.set(key, value);
    }
  }
  return map;
}

/**
 * JS 배열을 Y.Array로 깊은 변환.
 */
export function toYArray(arr: unknown[]): Y.Array<unknown> {
  const yArr = new Y.Array<unknown>();
  for (const value of arr) {
    if (Array.isArray(value)) {
      yArr.push([toYArray(value)]);
    } else if (typeof value === 'object' && value !== null) {
      yArr.push([toYMap(value as Record<string, unknown>)]);
    } else {
      yArr.push([value]);
    }
  }
  return yArr;
}

/**
 * Y.Map의 특정 키만 diff 적용 (전체 교체 대신 변경된 키만 업데이트).
 */
export function updateYMap(yMap: Y.Map<unknown>, updates: Record<string, unknown>): void {
  for (const key in updates) {
    const value = updates[key];
    if (value === undefined) continue;

    if (Array.isArray(value)) {
      yMap.set(key, toYArray(value));
    } else if (typeof value === 'object' && value !== null) {
      // 중첩 객체: 기존 Y.Map이 있으면 재귀 diff, 없으면 새로 생성
      const existing = yMap.get(key);
      if (existing instanceof Y.Map) {
        updateYMap(existing, value as Record<string, unknown>);
      } else {
        yMap.set(key, toYMap(value as Record<string, unknown>));
      }
    } else {
      yMap.set(key, value);
    }
  }
}
