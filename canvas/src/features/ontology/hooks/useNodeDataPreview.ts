// features/ontology/hooks/useNodeDataPreview.ts
// Fetches querylog + driver_score coverage for an Ontology node (P2-B Phase 1).
// Parses nodeId in the form "tbl:schema.table" or "col:schema.table.column"
// and calls GET /api/insight/schema-coverage.

import { useState, useEffect } from 'react';
import { toast } from 'sonner';
// 스키마 커버리지 API와 타입은 shared 레이어에서 가져온다 (feature 간 의존 제거)
import { fetchSchemaCoverage } from '@/shared/api/insightSchemaApi';
import type { SchemaCoverageResponse } from '@/shared/types/insight';

/** Parse a graph node ID into { table, column } for schema-coverage lookup. */
function parseNodeId(nodeId: string): { table: string; column?: string } | null {
  if (nodeId.startsWith('col:')) {
    // col:schema.table.column
    const parts = nodeId.slice(4).split('.');
    if (parts.length >= 3) {
      return { table: parts[parts.length - 2], column: parts[parts.length - 1] };
    }
    if (parts.length === 2) {
      return { table: parts[0], column: parts[1] };
    }
  } else if (nodeId.startsWith('tbl:')) {
    // tbl:schema.table
    const parts = nodeId.slice(4).split('.');
    return { table: parts[parts.length - 1] };
  }
  return null;
}

export function useNodeDataPreview(nodeId: string | null): SchemaCoverageResponse | null {
  const [preview, setPreview] = useState<SchemaCoverageResponse | null>(null);

  useEffect(() => {
    if (!nodeId) {
      setPreview(null);
      return;
    }
    const parsed = parseNodeId(nodeId);
    if (!parsed) {
      setPreview(null);
      return;
    }
    fetchSchemaCoverage(parsed)
      .then(setPreview)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : '알 수 없는 오류';
        toast.error('노드 데이터 프리뷰 로딩 실패', { description: msg });
        setPreview(null);
      });
  }, [nodeId]);

  return preview;
}
