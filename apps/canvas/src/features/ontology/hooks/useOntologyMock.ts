import { useState, useEffect, useCallback } from 'react';
import type { OntologyGraphData, OntologyNode, OntologyEdge, OntologyLayer } from '../types/ontology';

// --- MOCK DATA ---
const mockNodes: OntologyNode[] = [
    // KPIs
    { id: 'kpi_corp', label: '전사경영KPI', layer: 'kpi', properties: { target: '10%' } },
    { id: 'kpi_logistics', label: '물류KPI', layer: 'kpi', properties: { target: '99%' } },
    { id: 'kpi_efficiency', label: '효율KPI', layer: 'kpi', properties: { target: '5%' } },

    // Measures
    { id: 'm_logistics', label: '물류측정', layer: 'measure', properties: { unit: '건수' } },
    { id: 'm_efficiency', label: '효율측정', layer: 'measure', properties: { unit: '시간' } },
    { id: 'm_cost', label: '비용측정', layer: 'measure', properties: { unit: '금액' } },

    // Processes
    { id: 'p_inbound', label: '입고처리', layer: 'process', type: '핵심업무프로세스', properties: { dept: '물류관리팀' } },
    { id: 'p_delivery', label: '배송관리', layer: 'process', type: '핵심업무프로세스', properties: { dept: '배송팀' } },
    { id: 'p_inventory', label: '재고관리', layer: 'process', type: '지원업무프로세스', properties: { dept: '창고팀' } },
    { id: 'p_picking', label: '피킹작업', layer: 'process', type: '단위업무', properties: { dept: '창고팀' } },

    // Resources
    { id: 'r_centerA', label: '물류센터A', layer: 'resource', properties: { location: '서울' } },
    { id: 'r_centerB', label: '물류센터B', layer: 'resource', properties: { location: '부산' } },
    { id: 'r_truck1', label: '운송차량_T1', layer: 'resource', properties: { capacity: '5t' } },
    { id: 'r_erp', label: 'ERP시스템', layer: 'resource', properties: { vendor: 'SAP' } },
];

const mockEdges: OntologyEdge[] = [
    // Process -> Measure (측정)
    { source: 'p_inbound', target: 'm_logistics', type: '측정', label: '입고건수측정' },
    { source: 'p_delivery', target: 'm_logistics', type: '측정', label: '배송건수측정' },
    { source: 'p_picking', target: 'm_efficiency', type: '측정', label: '피킹시간측정' },
    { source: 'p_inventory', target: 'm_cost', type: '측정', label: '재고유지비용' },

    // Measure -> KPI (달성)
    { source: 'm_logistics', target: 'kpi_logistics', type: '달성', label: '물류목표달성' },
    { source: 'm_efficiency', target: 'kpi_efficiency', type: '달성', label: '효율목표달성' },
    { source: 'm_cost', target: 'kpi_corp', type: '달성', label: '비용절감달성' },
    { source: 'kpi_logistics', target: 'kpi_corp', type: '달성', label: '전사기여' },
    { source: 'kpi_efficiency', target: 'kpi_corp', type: '달성', label: '전사기여' },

    // Resource -> Process (참여)
    { source: 'r_centerA', target: 'p_inbound', type: '참여', label: '입고장소' },
    { source: 'r_centerA', target: 'p_inventory', type: '참여', label: '보관장소' },
    { source: 'r_centerB', target: 'p_delivery', type: '참여', label: '출발지' },
    { source: 'r_truck1', target: 'p_delivery', type: '참여', label: '운송수단' },
    { source: 'r_erp', target: 'p_inbound', type: '참여', label: '전산처리' },
    { source: 'r_erp', target: 'p_inventory', type: '참여', label: '전산처리' },
];

export function useOntologyMock() {
    const [data, setData] = useState<OntologyGraphData>({ nodes: [], links: [] });
    const [isLoading, setIsLoading] = useState(true);

    // Initial Load Simulation
    useEffect(() => {
        const timer = setTimeout(() => {
            // Compute initial node degrees (val) for visual sizing in force graph
            const initialNodes = mockNodes.map(n => ({
                ...n,
                val: (mockEdges.filter(e => e.source === n.id || e.target === n.id).length) + 1
            }));

            setData({ nodes: initialNodes, links: mockEdges });
            setIsLoading(false);
        }, 1000); // 1초 로딩 지연

        return () => clearTimeout(timer);
    }, []);

    // Filter Graph Based on Active Layers and Query
    const getFilteredGraph = useCallback((query: string, activeLayers: Set<OntologyLayer>) => {
        if (isLoading) return { nodes: [], links: [] };

        // 1. Filter nodes by layer and query
        const filteredNodes = data.nodes.filter(node => {
            const matchesLayer = activeLayers.has(node.layer);
            const matchesQuery = query === '' || node.label.toLowerCase().includes(query.toLowerCase());
            return matchesLayer && matchesQuery;
        });

        const validNodeIds = new Set(filteredNodes.map(n => n.id));

        // 2. Filter edges targeting valid nodes
        const filteredLinks = data.links.filter(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
            return validNodeIds.has(sourceId) && validNodeIds.has(targetId);
        });

        // 3. Recalculate weights based on filtered edges
        const weightedNodes = filteredNodes.map(n => {
            const edgeCount = filteredLinks.filter(e => {
                const sId = typeof e.source === 'object' ? e.source.id : e.source;
                const tId = typeof e.target === 'object' ? e.target.id : e.target;
                return sId === n.id || tId === n.id;
            }).length;
            return { ...n, val: edgeCount + 1 };
        });

        return { nodes: weightedNodes, links: filteredLinks };
    }, [data, isLoading]);

    // Mock Path Finding (BFS)
    const findShortestPath = useCallback((sourceId: string, targetId: string): string[] => {
        if (!sourceId || !targetId || sourceId === targetId) return [];

        const adjacencyList = new Map<string, string[]>();
        data.nodes.forEach(n => adjacencyList.set(n.id, []));

        data.links.forEach(l => {
            const u = typeof l.source === 'object' ? l.source.id : l.source;
            const v = typeof l.target === 'object' ? l.target.id : l.target;
            adjacencyList.get(u)?.push(v);
            adjacencyList.get(v)?.push(u); // Undirected for conceptual paths
        });

        const queue: { id: string; path: string[] }[] = [{ id: sourceId, path: [sourceId] }];
        const visited = new Set<string>([sourceId]);

        while (queue.length > 0) {
            const { id, path } = queue.shift()!;

            if (id === targetId) return path;

            const neighbors = adjacencyList.get(id) || [];
            for (const neighbor of neighbors) {
                if (!visited.has(neighbor)) {
                    visited.add(neighbor);
                    queue.push({ id: neighbor, path: [...path, neighbor] });
                }
            }
        }
        return []; // No path found
    }, [data]);

    return {
        graphData: data,
        isLoading,
        getFilteredGraph,
        findShortestPath
    };
}
