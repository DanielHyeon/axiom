/**
 * 스키마 캔버스 네비게이션 훅.
 * 가용성 확인, 초기 모드 판정(S1-S4 상태 전이),
 * 관련 테이블 로딩, 데이터소스 변경 시 스코프 리셋을 관리한다.
 */

import { useQuery } from '@tanstack/react-query';
import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getSchemaAvailability,
  getRelatedTables,
} from '@/shared/api/schemaNavigationApi';
import type {
  SchemaAvailability,
  RelatedTableItem,
  InitialModeStatus,
} from '@/shared/types/schemaNavigation';
import type { SchemaMode } from '@/shared/utils/nodeKey';
import { buildNodeKey } from '@/shared/utils/nodeKey';

// localStorage 키 접두사
const LS_MODE_PREFIX = 'axiom-schema-mode:';

/** useSchemaNavigation 훅의 반환값 */
interface UseSchemaNavigationReturn {
  /** 현재 스키마 모드 */
  mode: SchemaMode;
  /** 모드 변경 */
  setMode: (mode: SchemaMode) => void;
  /** 가용성 데이터 */
  availability: SchemaAvailability | null;
  /** 초기 모드 판정 상태 */
  modeStatus: InitialModeStatus;
  /** 관련 테이블 로드 (테이블 더블클릭 시 호출) */
  loadRelatedTables: (params: {
    tableName: string;
    schemaName?: string;
    datasourceName?: string;
    alreadyLoadedNodeKeys: string[];
  }) => Promise<RelatedTableItem[]>;
  /** 관련 테이블 로딩 중 */
  loadingRelated: boolean;
  /** 에러 */
  error: string | null;
}

export function useSchemaNavigation(
  datasourceId: string | null,
): UseSchemaNavigationReturn {
  // --- 상태 ---
  const [mode, setModeInternal] = useState<SchemaMode>('text2sql');
  const [modeStatus, setModeStatus] = useState<InitialModeStatus>('idle');
  const [loadingRelated, setLoadingRelated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 이전 datasourceId를 추적하여 변경 감지에 사용
  const prevDatasourceRef = useRef<string | null>(datasourceId);

  // --- 데이터소스 변경 시 스코프 리셋 ---
  useEffect(() => {
    if (prevDatasourceRef.current !== datasourceId) {
      prevDatasourceRef.current = datasourceId;
      // 모드 상태를 초기화하여 가용성을 다시 로드하도록 한다
      setModeStatus('idle');
      setModeInternal('text2sql');
      setError(null);
    }
  }, [datasourceId]);

  // --- 가용성 쿼리 (TanStack Query) ---
  const {
    data: availabilityData,
    error: queryError,
  } = useQuery({
    queryKey: ['schema-nav', 'availability', datasourceId],
    queryFn: () => getSchemaAvailability(datasourceId || undefined),
    enabled: !!datasourceId && modeStatus !== 'resolved',
    staleTime: 5 * 60 * 1000, // 5분 캐시
  });

  // --- 초기 모드 판정 (S1-S4 정책) ---
  useEffect(() => {
    // 가용성 데이터가 도착하고 아직 판정이 완료되지 않은 경우만 실행
    if (!availabilityData || modeStatus === 'resolved') return;

    try {
      const roboCount = availabilityData.robo.table_count;
      const text2sqlCount = availabilityData.text2sql.table_count;

      let resolvedMode: SchemaMode;

      if (roboCount === 0 && text2sqlCount > 0) {
        // S1: robo 없음, text2sql만 존재
        resolvedMode = 'text2sql';
      } else if (roboCount > 0 && text2sqlCount === 0) {
        // S2: text2sql 없음, robo만 존재
        resolvedMode = 'robo';
      } else if (roboCount > 0 && text2sqlCount > 0) {
        // S3: 둘 다 존재 -- localStorage에서 마지막 선택값 복원
        const stored = localStorage.getItem(`${LS_MODE_PREFIX}${datasourceId}`);
        resolvedMode = stored === 'robo' ? 'robo' : 'text2sql';
      } else {
        // S4: 둘 다 0 -- 기본값 유지, 빈 상태 표시
        resolvedMode = 'text2sql';
      }

      setModeInternal(resolvedMode);
      setModeStatus('resolved');
      setError(null);
    } catch (e) {
      setModeStatus('failed');
      setError(e instanceof Error ? e.message : '모드 판정 중 오류 발생');
    }
  }, [availabilityData, modeStatus, datasourceId]);

  // 쿼리 에러 처리
  useEffect(() => {
    if (queryError) {
      setModeStatus('failed');
      setError(
        queryError instanceof Error
          ? queryError.message
          : '스키마 가용성 조회 실패',
      );
    }
  }, [queryError]);

  // modeStatus가 idle에서 loading으로 전환 (쿼리가 활성화될 때)
  useEffect(() => {
    if (datasourceId && modeStatus === 'idle') {
      setModeStatus('loading');
    }
  }, [datasourceId, modeStatus]);

  // --- 모드 변경 (사용자 수동 전환) ---
  const setMode = useCallback(
    (newMode: SchemaMode) => {
      setModeInternal(newMode);
      // localStorage에 선택값 저장
      if (datasourceId) {
        localStorage.setItem(`${LS_MODE_PREFIX}${datasourceId}`, newMode);
      }
    },
    [datasourceId],
  );

  // --- 관련 테이블 로드 ---
  const loadRelatedTables = useCallback(
    async (params: {
      tableName: string;
      schemaName?: string;
      datasourceName?: string;
      alreadyLoadedNodeKeys: string[];
    }): Promise<RelatedTableItem[]> => {
      setLoadingRelated(true);
      setError(null);

      try {
        // 현재 모드에 따라 API 모드 결정
        const apiMode = mode === 'robo' ? 'ROBO' as const : 'TEXT2SQL' as const;

        // nodeKey 생성
        const nodeKey = buildNodeKey(
          mode,
          params.datasourceName || datasourceId || '',
          params.schemaName || 'public',
          params.tableName,
        );

        const result = await getRelatedTables({
          mode: apiMode,
          tableName: params.tableName,
          schemaName: params.schemaName || 'public',
          datasourceName: params.datasourceName || datasourceId || undefined,
          nodeKey,
          alreadyLoadedTableIds: params.alreadyLoadedNodeKeys,
        });

        return result.relatedTables;
      } catch (e) {
        const message =
          e instanceof Error ? e.message : '관련 테이블 조회 실패';
        setError(message);
        return [];
      } finally {
        setLoadingRelated(false);
      }
    },
    [mode, datasourceId],
  );

  return {
    mode,
    setMode,
    availability: availabilityData ?? null,
    modeStatus,
    loadRelatedTables,
    loadingRelated,
    error,
  };
}
