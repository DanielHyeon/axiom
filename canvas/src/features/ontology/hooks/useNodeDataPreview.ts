// features/ontology/hooks/useNodeDataPreview.ts
// Fetches querylog + driver_score coverage for an Ontology node (P2-B Phase 1).
// Parses nodeId in the form "tbl:schema.table" or "col:schema.table.column"
// and calls GET /api/insight/schema-coverage.

import { useState, useEffect } from 'react';
import { fetchSchemaCoverage } from '@/features/insight/api/insightApi';
import type { SchemaCoverageResponse } from '@/features/insight/api/insightApi';

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
      .catch(() => setPreview(null));
  }, [nodeId]);

  return preview;
}
