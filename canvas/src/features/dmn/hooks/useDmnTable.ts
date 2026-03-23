/**
 * DMN 결정 테이블 훅 — CRUD + 테스트 실행.
 * KG-1: TanStack Query 기반.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import {
  fetchDecisionTables,
  fetchDecisionTable,
  createDecisionTable,
  updateDecisionTable,
  deleteDecisionTable,
  executeTest,
} from '../api/dmnApi';
import type { DecisionTable, DmnTestRequest } from '../types/dmn';

const keys = {
  list: ['dmn-tables'] as const,
  detail: (id: string) => ['dmn-tables', id] as const,
};

/** 결정 테이블 목록 */
export function useDmnTables() {
  return useQuery({
    queryKey: keys.list,
    queryFn: fetchDecisionTables,
  });
}

/** 결정 테이블 상세 */
export function useDmnTable(id: string) {
  return useQuery({
    queryKey: keys.detail(id),
    queryFn: () => fetchDecisionTable(id),
    enabled: !!id,
  });
}

/** 결정 테이블 생성 */
export function useCreateDmnTable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createDecisionTable,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.list });
      toast.success('결정 테이블이 생성되었습니다');
    },
    onError: () => toast.error('결정 테이블 생성에 실패했습니다'),
  });
}

/** 결정 테이블 수정 */
export function useUpdateDmnTable(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Pick<DecisionTable, 'name' | 'hitPolicy' | 'columns' | 'rules' | 'description'>>) =>
      updateDecisionTable(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.detail(id) });
      qc.invalidateQueries({ queryKey: keys.list });
      toast.success('결정 테이블이 수정되었습니다');
    },
    onError: () => toast.error('수정에 실패했습니다'),
  });
}

/** 결정 테이블 삭제 */
export function useDeleteDmnTable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDecisionTable,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.list });
      toast.success('결정 테이블이 삭제되었습니다');
    },
    onError: () => toast.error('삭제에 실패했습니다'),
  });
}

/** 테스트 실행 */
export function useExecuteDmnTest(tableId: string) {
  return useMutation({
    mutationFn: (payload: DmnTestRequest) => executeTest(tableId, payload),
    onError: () => toast.error('테스트 실행에 실패했습니다'),
  });
}
