/**
 * 데이터 품질 메트릭 TanStack Query 훅
 * DQ 규칙, 인시던트, 점수, 추이 데이터를 서버에서 조회하고 캐싱합니다.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';
import {
  getDQRules,
  createDQRule,
  runDQTest,
  getDQScore,
  getDQIncidents,
  updateIncidentStatus,
  getDQTrend,
} from '../api/dataQualityApi';
import { useDQStore } from '../store/useDQStore';
import type {
  DQRule,
  DQStats,
  DQIncident,
  CreateDQRulePayload,
} from '../types/data-quality';

// ─── Query Keys ─────────────────────────────────────

const KEYS = {
  rules: ['dq', 'rules'] as const,
  score: ['dq', 'score'] as const,
  incidents: ['dq', 'incidents'] as const,
  trend: ['dq', 'trend'] as const,
};

// ─── 규칙 목록 + 필터링 ─────────────────────────────

export function useDQRules() {
  const { filters } = useDQStore();

  const query = useQuery({
    queryKey: KEYS.rules,
    queryFn: getDQRules,
    staleTime: 30_000,
  });

  // 클라이언트 필터링 — 서버에서 전체를 받아온 뒤 필터
  const filteredRules = useMemo(() => {
    if (!query.data) return [];
    let rules = [...query.data];

    // 검색어 필터
    if (filters.searchQuery) {
      const q = filters.searchQuery.toLowerCase();
      rules = rules.filter(
        (r) =>
          r.name.toLowerCase().includes(q) ||
          r.tableName.toLowerCase().includes(q) ||
          (r.columnName?.toLowerCase().includes(q) ?? false),
      );
    }

    // 테이블 필터
    if (filters.tableFilter) {
      rules = rules.filter((r) => r.tableName === filters.tableFilter);
    }

    // 유형 필터
    if (filters.typeFilter) {
      rules = rules.filter((r) => r.type === filters.typeFilter);
    }

    // 상태 필터
    if (filters.statusFilter) {
      rules = rules.filter((r) => {
        if (!r.lastResult) return filters.statusFilter === '';
        if (filters.statusFilter === 'success') return r.lastResult.passed;
        if (filters.statusFilter === 'failed') return !r.lastResult.passed;
        return true;
      });
    }

    // 심각도 필터
    if (filters.severityFilter) {
      rules = rules.filter((r) => r.severity === filters.severityFilter);
    }

    return rules;
  }, [query.data, filters]);

  return { ...query, filteredRules };
}

// ─── 통계 계산 (규칙 데이터에서 파생) ───────────────

export function useDQStats(): DQStats | null {
  const { data: rules } = useQuery({
    queryKey: KEYS.rules,
    queryFn: getDQRules,
    staleTime: 30_000,
  });

  return useMemo(() => {
    if (!rules || rules.length === 0) return null;

    const total = rules.length;
    const success = rules.filter((r) => r.lastResult?.passed).length;
    const failed = rules.filter((r) => r.lastResult && !r.lastResult.passed).length;
    const aborted = total - success - failed;

    const tables = new Set(rules.map((r) => r.tableName));
    const failedTables = new Set(
      rules.filter((r) => r.lastResult && !r.lastResult.passed).map((r) => r.tableName),
    );
    const healthyAssets = tables.size - failedTables.size;

    return {
      totalTests: total,
      successCount: success,
      failedCount: failed,
      abortedCount: aborted,
      successRate: total > 0 ? Math.round((success / total) * 100) : 0,
      healthyAssets,
      totalAssets: tables.size,
      healthyRate: tables.size > 0 ? Math.round((healthyAssets / tables.size) * 100) : 0,
      coverageRate: 22.73, // TODO: 실제 커버리지 계산
    };
  }, [rules]);
}

// ─── DQ 점수 ─────────────────────────────────────────

export function useDQScore() {
  return useQuery({
    queryKey: KEYS.score,
    queryFn: getDQScore,
    staleTime: 60_000,
  });
}

// ─── 인시던트 ─────────────────────────────────────────

export function useDQIncidents() {
  return useQuery({
    queryKey: KEYS.incidents,
    queryFn: getDQIncidents,
    staleTime: 30_000,
  });
}

// ─── 추이 차트 ────────────────────────────────────────

export function useDQTrend(days = 14) {
  return useQuery({
    queryKey: [...KEYS.trend, days],
    queryFn: () => getDQTrend(days),
    staleTime: 60_000,
  });
}

// ─── Mutations ────────────────────────────────────────

/** 규칙 생성 뮤테이션 */
export function useCreateDQRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateDQRulePayload) => createDQRule(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.rules });
    },
  });
}

/** 테스트 실행 뮤테이션 */
export function useRunDQTest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ruleId: string) => runDQTest(ruleId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.rules });
      qc.invalidateQueries({ queryKey: KEYS.incidents });
    },
  });
}

/** 인시던트 상태 변경 뮤테이션 */
export function useUpdateIncident() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: DQIncident['status'] }) =>
      updateIncidentStatus(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.incidents });
    },
  });
}
