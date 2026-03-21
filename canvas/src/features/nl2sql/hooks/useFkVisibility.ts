/**
 * FK 가시성 상태 관리 훅.
 *
 * 관계선을 소스 타입별(DDL/User/Fabric)로 토글할 수 있다.
 * SchemaCanvas에서 ERD 렌더링 시 이 훅의 isVisible()로 필터링한다.
 */
import { useState, useCallback } from 'react';
import type { FkSource } from '../types/schema';

export type { FkSource };

/** 소스별 가시성 상태 */
export interface FkVisibilityState {
  ddl: boolean;     // DDL 기반 FK (초록 실선)
  user: boolean;    // 사용자 추가 FK (주황 실선)
  fabric: boolean;  // Fabric 추론 FK (파랑 점선)
}

/** 소스별 스타일 설정 */
export const FK_SOURCE_STYLES: Record<FkSource, { color: string; label: string }> = {
  ddl: { color: '#22C55E', label: 'DDL' },
  user: { color: '#F97316', label: 'User' },
  fabric: { color: '#3B82F6', label: 'Fabric' },
};

const DEFAULT_VISIBILITY: FkVisibilityState = { ddl: true, user: true, fabric: true };

export function useFkVisibility() {
  const [visibility, setVisibility] = useState<FkVisibilityState>(DEFAULT_VISIBILITY);

  /** 특정 소스의 가시성을 토글한다 */
  const toggle = useCallback((source: FkSource) => {
    setVisibility((prev) => ({ ...prev, [source]: !prev[source] }));
  }, []);

  /** 해당 소스의 관계가 보이는지 확인한다 */
  const isVisible = useCallback(
    (source: FkSource | undefined) => {
      if (!source) return visibility.ddl; // 소스 미지정 시 DDL로 간주
      return visibility[source];
    },
    [visibility],
  );

  return { visibility, toggle, isVisible };
}
