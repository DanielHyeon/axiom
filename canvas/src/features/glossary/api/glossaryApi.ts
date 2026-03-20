/**
 * 글로서리 API 클라이언트
 * Weaver 서비스의 글로서리 엔드포인트와 통신
 */

import { weaverApi } from '@/lib/api/clients';
import type {
  Glossary,
  GlossaryListResponse,
  GlossaryCreateRequest,
  GlossaryTerm,
  TermListResponse,
  TermCreateRequest,
  CategoryListResponse,
  TermSearchParams,
} from '../types/glossary';

const BASE = '/api/v3/weaver/glossary';

// ---------------------------------------------------------------------------
// 용어집 CRUD
// ---------------------------------------------------------------------------

/** 용어집 목록 조회 */
export async function fetchGlossaries(): Promise<GlossaryListResponse> {
  return weaverApi.get(`${BASE}`);
}

/** 용어집 생성 */
export async function createGlossary(
  data: GlossaryCreateRequest,
): Promise<Glossary> {
  return weaverApi.post(`${BASE}`, data);
}

/** 용어집 수정 */
export async function updateGlossary(
  id: string,
  data: Partial<GlossaryCreateRequest>,
): Promise<Glossary> {
  return weaverApi.put(`${BASE}/${id}`, data);
}

/** 용어집 삭제 */
export async function deleteGlossary(id: string): Promise<void> {
  return weaverApi.delete(`${BASE}/${id}`);
}

// ---------------------------------------------------------------------------
// 용어 CRUD
// ---------------------------------------------------------------------------

/** 용어 목록 조회 (검색/필터 지원) */
export async function fetchTerms(
  params: TermSearchParams,
): Promise<TermListResponse> {
  const queryParams = new URLSearchParams();
  if (params.query) queryParams.set('q', params.query);
  if (params.category) queryParams.set('category', params.category);
  if (params.status) queryParams.set('status', params.status);

  const qs = queryParams.toString();
  const url = `${BASE}/${params.glossaryId}/terms${qs ? `?${qs}` : ''}`;
  return weaverApi.get(url);
}

/** 용어 생성 */
export async function createTerm(
  glossaryId: string,
  data: TermCreateRequest,
): Promise<GlossaryTerm> {
  return weaverApi.post(`${BASE}/${glossaryId}/terms`, data);
}

/** 용어 수정 */
export async function updateTerm(
  glossaryId: string,
  termId: string,
  data: Partial<TermCreateRequest>,
): Promise<GlossaryTerm> {
  return weaverApi.put(`${BASE}/${glossaryId}/terms/${termId}`, data);
}

/** 용어 삭제 */
export async function deleteTerm(
  glossaryId: string,
  termId: string,
): Promise<void> {
  return weaverApi.delete(`${BASE}/${glossaryId}/terms/${termId}`);
}

// ---------------------------------------------------------------------------
// 카테고리
// ---------------------------------------------------------------------------

/** 카테고리 목록 조회 */
export async function fetchCategories(): Promise<CategoryListResponse> {
  return weaverApi.get(`${BASE}/categories`);
}

/** 카테고리 생성 */
export async function createCategory(
  name: string,
  color: string,
): Promise<{ id: string; name: string; color: string }> {
  return weaverApi.post(`${BASE}/categories`, { name, color });
}

/** 카테고리 삭제 */
export async function deleteCategory(id: string): Promise<void> {
  return weaverApi.delete(`${BASE}/categories/${id}`);
}

// ---------------------------------------------------------------------------
// Import / Export
// ---------------------------------------------------------------------------

/** CSV/JSON 내보내기 — Blob 반환 */
export async function exportTerms(
  glossaryId: string,
  format: 'csv' | 'json' = 'json',
): Promise<Blob> {
  const res = await fetch(
    `${(weaverApi as any).defaults?.baseURL ?? ''}${BASE}/${glossaryId}/export?format=${format}`,
    { headers: { Accept: format === 'csv' ? 'text/csv' : 'application/json' } },
  );
  if (!res.ok) throw new Error(`Export failed: ${res.statusText}`);
  return res.blob();
}

/** CSV/JSON 가져오기 */
export async function importTerms(
  glossaryId: string,
  file: File,
): Promise<{ imported: number; skipped: number }> {
  const formData = new FormData();
  formData.append('file', file);
  return weaverApi.post(`${BASE}/${glossaryId}/import`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
}
