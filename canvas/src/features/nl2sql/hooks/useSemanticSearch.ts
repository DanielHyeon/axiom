/**
 * 시맨틱 벡터 검색 훅.
 *
 * Synapse의 벡터 검색 API를 활용하여
 * 자연어로 테이블/컬럼을 검색한다.
 */
import { useState, useCallback } from 'react';
import { synapseApi } from '@/lib/api/clients';
import type { SchemaSearchResult } from '../types/schema';

interface VectorSearchHit {
  node_type: string;
  name: string;
  table_name?: string;
  schema_name?: string;
  description?: string;
  similarity: number;
}

export function useSemanticSearch() {
  const [results, setResults] = useState<SchemaSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  /** 벡터 검색 실행 */
  const search = useCallback(async (query: string) => {
    if (!query.trim() || query.length < 2) {
      setResults([]);
      return;
    }

    setIsSearching(true);
    try {
      const res = await synapseApi.post('/api/v3/synapse/graph/vector-search', {
        query,
        node_types: ['Table', 'Column'],
        limit: 10,
      });
      const hits: VectorSearchHit[] = (res as any)?.data?.results ?? [];

      // VectorSearchHit → SchemaSearchResult 변환
      const mapped: SchemaSearchResult[] = hits.map((hit) => ({
        type: hit.node_type === 'Table' ? 'table' as const : 'column' as const,
        tableName: hit.table_name || hit.name,
        columnName: hit.node_type === 'Column' ? hit.name : undefined,
        schema: hit.schema_name || 'public',
        matchedText: hit.description
          ? `${hit.name} — ${hit.description}`
          : hit.name,
      }));

      setResults(mapped);
    } catch (err) {
      console.warn('[useSemanticSearch] 벡터 검색 실패:', err);
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  }, []);

  /** 결과 초기화 */
  const clearResults = useCallback(() => {
    setResults([]);
  }, []);

  return { results, isSearching, search, clearResults };
}
