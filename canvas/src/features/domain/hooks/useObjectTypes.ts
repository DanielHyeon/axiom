/**
 * ObjectType CRUD TanStack Query 훅
 *
 * queryKey: ['domain', 'objectTypes'] — 목록
 * queryKey: ['domain', 'objectTypes', id] — 단건
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listObjectTypes,
  getObjectType,
  createObjectType,
  updateObjectType,
  deleteObjectType,
  generateFromTable,
  executeBehavior,
} from '../api/domainApi';
import type {
  CreateObjectTypePayload,
  UpdateObjectTypePayload,
  GenerateFromTablePayload,
  ExecuteBehaviorPayload,
} from '../types/domain';

// ── Query Keys ──
const KEYS = {
  all: ['domain', 'objectTypes'] as const,
  detail: (id: string) => ['domain', 'objectTypes', id] as const,
};

// ──────────────────────────────────────
// 목록 조회
// ──────────────────────────────────────

export function useObjectTypeList() {
  return useQuery({
    queryKey: KEYS.all,
    queryFn: () => listObjectTypes(),
    staleTime: 30_000, // 30초 캐시
  });
}

// ──────────────────────────────────────
// 단건 조회
// ──────────────────────────────────────

export function useObjectTypeDetail(id: string | null) {
  return useQuery({
    queryKey: KEYS.detail(id ?? ''),
    queryFn: () => getObjectType(id!),
    enabled: !!id,
  });
}

// ──────────────────────────────────────
// 생성
// ──────────────────────────────────────

export function useCreateObjectType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateObjectTypePayload) => createObjectType(payload),
    onSuccess: () => {
      // 목록 캐시 무효화
      qc.invalidateQueries({ queryKey: KEYS.all });
    },
  });
}

// ──────────────────────────────────────
// 수정
// ──────────────────────────────────────

export function useUpdateObjectType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UpdateObjectTypePayload }) =>
      updateObjectType(id, payload),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: KEYS.all });
      qc.invalidateQueries({ queryKey: KEYS.detail(variables.id) });
    },
  });
}

// ──────────────────────────────────────
// 삭제
// ──────────────────────────────────────

export function useDeleteObjectType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteObjectType(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.all });
    },
  });
}

// ──────────────────────────────────────
// 테이블 기반 자동 생성
// ──────────────────────────────────────

export function useGenerateFromTable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: GenerateFromTablePayload) => generateFromTable(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEYS.all });
    },
  });
}

// ──────────────────────────────────────
// Behavior 실행
// ──────────────────────────────────────

export function useExecuteBehavior() {
  return useMutation({
    mutationFn: ({
      objectTypeId,
      behaviorId,
      payload,
    }: {
      objectTypeId: string;
      behaviorId: string;
      payload?: ExecuteBehaviorPayload;
    }) => executeBehavior(objectTypeId, behaviorId, payload),
  });
}
