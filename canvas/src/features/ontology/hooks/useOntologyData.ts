import { useCallback, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { OntologyGraphData, OntologyLayer } from '../types/ontology';
import { getCaseOntology, getPath } from '../api/ontologyApi';

export function useOntologyData(caseId: string | null) {
  const { data, isLoading } = useQuery({
    queryKey: ['ontology', 'case', caseId],
    queryFn: () => getCaseOntology(caseId!, { limit: 500 }),
    enabled: !!caseId,
  });

  const graphData: OntologyGraphData = useMemo(() => {
    if (!data) return { nodes: [], links: [] };
    const nodes = data.nodes.map((n) => ({
      ...n,
      val:
        data.links.filter((e) => {
          const sId = typeof e.source === 'object' ? e.source.id : e.source;
          const tId = typeof e.target === 'object' ? e.target.id : e.target;
          return sId === n.id || tId === n.id;
        }).length + 1,
    }));
    return { nodes, links: data.links };
  }, [data]);

  const getFilteredGraph = useCallback(
    (query: string, activeLayers: Set<OntologyLayer>): OntologyGraphData => {
      if (isLoading || !graphData.nodes.length) return { nodes: [], links: [] };

      const filteredNodes = graphData.nodes.filter((node) => {
        const matchesLayer = activeLayers.has(node.layer);
        const matchesQuery =
          query === '' || node.label.toLowerCase().includes(query.toLowerCase());
        return matchesLayer && matchesQuery;
      });

      const validNodeIds = new Set(filteredNodes.map((n) => n.id));

      const filteredLinks = graphData.links.filter((link) => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
        return validNodeIds.has(sourceId) && validNodeIds.has(targetId);
      });

      const weightedNodes = filteredNodes.map((n) => {
        const edgeCount = filteredLinks.filter((e) => {
          const sId = typeof e.source === 'object' ? e.source.id : e.source;
          const tId = typeof e.target === 'object' ? e.target.id : e.target;
          return sId === n.id || tId === n.id;
        }).length;
        return { ...n, val: edgeCount + 1 };
      });

      return { nodes: weightedNodes, links: filteredLinks };
    },
    [graphData, isLoading],
  );

  const findShortestPath = useCallback(
    async (sourceId: string, targetId: string): Promise<string[]> => {
      if (!sourceId || !targetId || sourceId === targetId) return [];
      try {
        return await getPath(sourceId, targetId);
      } catch {
        return [];
      }
    },
    [],
  );

  return { graphData, isLoading, getFilteredGraph, findShortestPath };
}
