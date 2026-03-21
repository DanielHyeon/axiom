/**
 * 스키마 편집 훅 — TanStack Query 기반 CRUD.
 *
 * 테이블/컬럼 설명 수정, 관계 추가/삭제, 임베딩 재생성을 관리한다.
 * 모든 mutation 성공 시 관련 쿼리 캐시를 자동 무효화한다.
 * 실패 시 콘솔에 에러를 기록한다 (M5 수정).
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as schemaEditApi from '@/shared/api/schemaEditApi';

export function useSchemaEdit() {
  const qc = useQueryClient();

  // 관계 목록 조회
  const relationships = useQuery({
    queryKey: ['schema-edit', 'relationships'],
    queryFn: schemaEditApi.listRelationships,
    staleTime: 2 * 60 * 1000,
  });

  // 테이블 설명 수정
  const updateTableDesc = useMutation({
    mutationFn: (p: { tableName: string; description: string }) =>
      schemaEditApi.updateTableDescription(p.tableName, p.description),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schema-edit'] });
      qc.invalidateQueries({ queryKey: ['nl2sql', 'schemaTree'] });
    },
    onError: (error: Error) => {
      console.error('[useSchemaEdit] 테이블 설명 수정 실패:', error.message);
    },
  });

  // 컬럼 설명 수정
  const updateColumnDesc = useMutation({
    mutationFn: (p: { tableName: string; columnName: string; description: string }) =>
      schemaEditApi.updateColumnDescription(p.tableName, p.columnName, p.description),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schema-edit'] });
    },
    onError: (error: Error) => {
      console.error('[useSchemaEdit] 컬럼 설명 수정 실패:', error.message);
    },
  });

  // 관계 추가
  const createRel = useMutation({
    mutationFn: schemaEditApi.createRelationship,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schema-edit', 'relationships'] });
      qc.invalidateQueries({ queryKey: ['schema-nav'] });
    },
    onError: (error: Error) => {
      console.error('[useSchemaEdit] 관계 추가 실패:', error.message);
    },
  });

  // 관계 삭제
  const deleteRel = useMutation({
    mutationFn: schemaEditApi.deleteRelationship,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schema-edit', 'relationships'] });
      qc.invalidateQueries({ queryKey: ['schema-nav'] });
    },
    onError: (error: Error) => {
      console.error('[useSchemaEdit] 관계 삭제 실패:', error.message);
    },
  });

  // 임베딩 재생성
  const rebuildEmbedding = useMutation({
    mutationFn: schemaEditApi.rebuildTableEmbedding,
    onError: (error: Error) => {
      console.error('[useSchemaEdit] 임베딩 재생성 실패:', error.message);
    },
  });

  return {
    relationships,
    updateTableDesc,
    updateColumnDesc,
    createRel,
    deleteRel,
    rebuildEmbedding,
  };
}
