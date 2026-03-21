/**
 * useSemanticSearch 훅 테스트.
 *
 * 시맨틱 벡터 검색 로직을 검증한다.
 * - 초기 상태
 * - 최소 쿼리 길이 검증
 * - API 호출 및 결과 매핑
 * - 에러 처리
 * - 결과 초기화
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSemanticSearch } from './useSemanticSearch';

// synapseApi 모킹 — 벡터 검색 POST 요청을 가로챈다
const mockPost = vi.fn();
vi.mock('@/lib/api/clients', () => ({
  synapseApi: {
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

describe('useSemanticSearch', () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  // ─── 초기 상태 ──────────────────────────────────────────

  it('초기 상태: 빈 결과 + isSearching=false', () => {
    const { result } = renderHook(() => useSemanticSearch());

    expect(result.current.results).toEqual([]);
    expect(result.current.isSearching).toBe(false);
  });

  // ─── 최소 쿼리 길이 검증 ─────────────────────────────────

  it('빈 쿼리: API를 호출하지 않고 빈 결과 반환', async () => {
    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('');
    });

    expect(mockPost).not.toHaveBeenCalled();
    expect(result.current.results).toEqual([]);
  });

  it('1자 쿼리: API를 호출하지 않고 빈 결과 반환', async () => {
    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('a');
    });

    expect(mockPost).not.toHaveBeenCalled();
    expect(result.current.results).toEqual([]);
  });

  it('공백만 있는 쿼리: API를 호출하지 않는다', async () => {
    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('   ');
    });

    expect(mockPost).not.toHaveBeenCalled();
    expect(result.current.results).toEqual([]);
  });

  // ─── 정상 검색 ──────────────────────────────────────────

  it('2자 이상 쿼리: API를 호출하고 결과를 매핑한다', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        results: [
          {
            node_type: 'Table',
            name: 'orders',
            table_name: 'orders',
            schema_name: 'public',
            description: '주문 테이블',
            similarity: 0.95,
          },
          {
            node_type: 'Column',
            name: 'order_date',
            table_name: 'orders',
            schema_name: 'sales',
            description: null,
            similarity: 0.88,
          },
        ],
      },
    });

    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('주문');
    });

    // API 호출 검증
    expect(mockPost).toHaveBeenCalledWith(
      '/api/v3/synapse/graph/vector-search',
      { query: '주문', node_types: ['Table', 'Column'], limit: 10 },
    );

    // 결과 매핑 검증 — Table 타입
    expect(result.current.results).toHaveLength(2);
    expect(result.current.results[0]).toEqual({
      type: 'table',
      tableName: 'orders',
      columnName: undefined,
      schema: 'public',
      matchedText: 'orders \u2014 주문 테이블',
    });

    // 결과 매핑 검증 — Column 타입 (description 없음)
    expect(result.current.results[1]).toEqual({
      type: 'column',
      tableName: 'orders',
      columnName: 'order_date',
      schema: 'sales',
      matchedText: 'order_date',
    });

    expect(result.current.isSearching).toBe(false);
  });

  it('Table 노드에서 table_name이 없으면 name을 tableName으로 사용한다', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        results: [
          {
            node_type: 'Table',
            name: 'products',
            // table_name 미제공
            schema_name: 'inventory',
            similarity: 0.90,
          },
        ],
      },
    });

    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('product');
    });

    expect(result.current.results[0].tableName).toBe('products');
    expect(result.current.results[0].schema).toBe('inventory');
  });

  it('schema_name이 없으면 기본값 public을 사용한다', async () => {
    mockPost.mockResolvedValueOnce({
      data: {
        results: [
          {
            node_type: 'Table',
            name: 'users',
            table_name: 'users',
            // schema_name 미제공
            similarity: 0.85,
          },
        ],
      },
    });

    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('users');
    });

    expect(result.current.results[0].schema).toBe('public');
  });

  // ─── 에러 처리 ──────────────────────────────────────────

  it('API 오류 시 결과를 비우고 isSearching=false로 복원한다', async () => {
    mockPost.mockRejectedValueOnce(new Error('Network Error'));

    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('테스트');
    });

    expect(result.current.results).toEqual([]);
    expect(result.current.isSearching).toBe(false);
  });

  it('API 응답에 results 필드가 없으면 빈 배열로 처리한다', async () => {
    mockPost.mockResolvedValueOnce({ data: {} });

    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('검색어');
    });

    expect(result.current.results).toEqual([]);
  });

  // ─── 결과 초기화 ─────────────────────────────────────────

  it('clearResults: 결과를 빈 배열로 초기화한다', async () => {
    // 먼저 검색으로 결과를 채운다
    mockPost.mockResolvedValueOnce({
      data: {
        results: [
          { node_type: 'Table', name: 'test', similarity: 0.9 },
        ],
      },
    });

    const { result } = renderHook(() => useSemanticSearch());

    await act(async () => {
      await result.current.search('test');
    });
    expect(result.current.results).toHaveLength(1);

    // 초기화
    act(() => {
      result.current.clearResults();
    });
    expect(result.current.results).toEqual([]);
  });

  // ─── isSearching 상태 전이 ───────────────────────────────

  it('검색 중 isSearching=true, 완료 후 false', async () => {
    // 지연된 응답으로 isSearching 상태 전이 확인
    let resolvePromise: (value: unknown) => void;
    const delayedResponse = new Promise((resolve) => {
      resolvePromise = resolve;
    });
    mockPost.mockReturnValueOnce(delayedResponse);

    const { result } = renderHook(() => useSemanticSearch());

    // 검색 시작 (완료 대기하지 않음)
    let searchPromise: Promise<void>;
    act(() => {
      searchPromise = result.current.search('검색');
    });

    // 검색 중 상태 확인
    expect(result.current.isSearching).toBe(true);

    // 응답 도착
    await act(async () => {
      resolvePromise!({ data: { results: [] } });
      await searchPromise;
    });

    expect(result.current.isSearching).toBe(false);
  });
});
