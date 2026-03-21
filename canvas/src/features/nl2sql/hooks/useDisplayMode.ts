/**
 * 논리명/물리명 표시 모드 토글 훅.
 *
 * ERD 캔버스에서 테이블·컬럼 표시를 전환한다:
 *  - physical: 원래 DB 이름 (name) — 기본값
 *  - logical: 비즈니스 설명 (description) — 없으면 name 폴백
 */
import { useState, useCallback } from 'react';

/** 표시 모드 */
export type DisplayMode = 'physical' | 'logical';

export function useDisplayMode(initial: DisplayMode = 'physical') {
  const [displayMode, setDisplayMode] = useState<DisplayMode>(initial);

  /** 모드 전환 */
  const toggleDisplayMode = useCallback(() => {
    setDisplayMode((prev) => (prev === 'physical' ? 'logical' : 'physical'));
  }, []);

  /**
   * 표시할 이름을 결정한다.
   * logical 모드에서 description이 있으면 description을, 없으면 name을 반환한다.
   */
  const getDisplayName = useCallback(
    (name: string, description?: string | null): string => {
      if (displayMode === 'logical' && description) {
        return description;
      }
      return name;
    },
    [displayMode],
  );

  return { displayMode, toggleDisplayMode, getDisplayName };
}
