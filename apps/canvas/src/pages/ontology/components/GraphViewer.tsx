import { useEffect, useRef, useCallback } from 'react';
import cytoscape from 'cytoscape';
import dagre from 'cytoscape-dagre';
import coseBilkent from 'cytoscape-cose-bilkent';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import type { OntologyGraphData } from '@/features/ontology/types/ontology';

// Register layout extensions once
cytoscape.use(dagre);
cytoscape.use(coseBilkent);

const LAYER_COLORS: Record<string, string> = {
    kpi: '#EF4444',
    measure: '#F59E0B',
    process: '#3B82F6',
    resource: '#10B981',
};

const LAYER_SHAPES: Record<string, string> = {
    kpi: 'ellipse',
    measure: 'diamond',
    process: 'round-rectangle',
    resource: 'rectangle',
};

const CYTOSCAPE_STYLE: cytoscape.Stylesheet[] = [
    {
        selector: 'node',
        style: {
            label: 'data(label)',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 6,
            'font-size': 11,
            color: '#d4d4d4',
            'text-outline-width': 2,
            'text-outline-color': '#111111',
            'background-color': '#666',
            width: 'mapData(weight, 1, 10, 24, 56)',
            height: 'mapData(weight, 1, 10, 24, 56)',
            'border-width': 0,
            'overlay-opacity': 0,
        },
    },
    // Layer-specific node styles
    {
        selector: 'node.kpi',
        style: { 'background-color': LAYER_COLORS.kpi, shape: LAYER_SHAPES.kpi as any },
    },
    {
        selector: 'node.measure',
        style: { 'background-color': LAYER_COLORS.measure, shape: LAYER_SHAPES.measure as any },
    },
    {
        selector: 'node.process',
        style: { 'background-color': LAYER_COLORS.process, shape: LAYER_SHAPES.process as any },
    },
    {
        selector: 'node.resource',
        style: { 'background-color': LAYER_COLORS.resource, shape: LAYER_SHAPES.resource as any },
    },
    // Edge base style
    {
        selector: 'edge',
        style: {
            width: 1.5,
            'line-color': '#404040',
            'target-arrow-color': '#404040',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.8,
            label: 'data(label)',
            'font-size': 9,
            color: '#737373',
            'text-rotation': 'autorotate',
            'text-outline-width': 1.5,
            'text-outline-color': '#111111',
            'overlay-opacity': 0,
        },
    },
    // Selected node
    {
        selector: 'node:selected',
        style: {
            'border-width': 3,
            'border-color': '#ffffff',
        },
    },
    // Highlighted (neighbor or path) nodes & edges
    {
        selector: 'node.highlighted',
        style: {
            'border-width': 2,
            'border-color': '#ffffff',
            'z-index': 10,
        },
    },
    {
        selector: 'edge.highlighted',
        style: {
            'line-color': '#ffffff',
            'target-arrow-color': '#ffffff',
            width: 2.5,
            'z-index': 10,
        },
    },
    // Dimmed (not in highlight set)
    {
        selector: 'node.dimmed',
        style: { opacity: 0.15 },
    },
    {
        selector: 'edge.dimmed',
        style: { opacity: 0.08 },
    },
];

interface GraphViewerProps {
    data: OntologyGraphData;
    shortestPathIds: string[];
}

export function GraphViewer({ data, shortestPathIds }: GraphViewerProps) {
    const cyRef = useRef<cytoscape.Core | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const { selectedNodeId, hoveredNodeId, selectNode, setHoveredNode } = useOntologyStore();

    // Convert OntologyGraphData → Cytoscape elements
    const toCyElements = useCallback((): cytoscape.ElementDefinition[] => {
        const nodes: cytoscape.ElementDefinition[] = data.nodes.map((n) => ({
            group: 'nodes' as const,
            data: {
                id: n.id,
                label: n.label,
                layer: n.layer,
                weight: Math.min(n.val || 1, 10),
                ...n.properties,
            },
            classes: n.layer,
        }));

        const edges: cytoscape.ElementDefinition[] = data.links.map((e, i) => {
            const sourceId = typeof e.source === 'object' ? e.source.id : e.source;
            const targetId = typeof e.target === 'object' ? e.target.id : e.target;
            return {
                group: 'edges' as const,
                data: {
                    id: `e-${sourceId}-${targetId}-${i}`,
                    source: sourceId,
                    target: targetId,
                    label: e.label || '',
                    relType: e.type,
                },
            };
        });

        return [...nodes, ...edges];
    }, [data]);

    // Initialize Cytoscape instance
    useEffect(() => {
        if (!containerRef.current) return;

        const cy = cytoscape({
            container: containerRef.current,
            style: CYTOSCAPE_STYLE,
            elements: [],
            minZoom: 0.2,
            maxZoom: 5,
            wheelSensitivity: 0.3,
        });

        cyRef.current = cy;

        // Event: node click → select
        cy.on('tap', 'node', (evt) => {
            const nodeId = evt.target.id();
            const store = useOntologyStore.getState();
            if (store.selectedNodeId === nodeId) {
                selectNode(null);
            } else {
                selectNode(nodeId);
                cy.animate({ center: { eles: evt.target }, zoom: 2 }, { duration: 500 });
            }
        });

        // Event: background click → deselect
        cy.on('tap', (evt) => {
            if (evt.target === cy) {
                selectNode(null);
            }
        });

        // Event: node hover
        cy.on('mouseover', 'node', (evt) => setHoveredNode(evt.target.id()));
        cy.on('mouseout', 'node', () => setHoveredNode(null));

        return () => {
            cy.destroy();
            cyRef.current = null;
        };
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    // Sync elements when data changes
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy) return;

        const elements = toCyElements();
        cy.elements().remove();

        if (elements.length === 0) return;

        cy.add(elements);

        // Run layout
        cy.layout({
            name: 'cose-bilkent',
            animate: false,
            nodeDimensionsIncludeLabels: true,
            idealEdgeLength: 120,
            nodeRepulsion: 6000,
            gravity: 0.25,
            numIter: 2500,
            tile: true,
        } as any).run();

        // Fit to viewport after layout
        setTimeout(() => cy.fit(undefined, 40), 100);
    }, [toCyElements]);

    // Sync selection state from store → cytoscape
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy) return;

        cy.nodes().unselect();
        if (selectedNodeId) {
            const node = cy.getElementById(selectedNodeId);
            if (node.length) node.select();
        }
    }, [selectedNodeId]);

    // Highlight logic: path or hover/selection neighbors
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy || cy.elements().length === 0) return;

        // Clear previous highlights
        cy.elements().removeClass('highlighted dimmed');

        if (shortestPathIds.length > 0) {
            // Path mode: highlight path nodes and edges between them
            const pathSet = new Set(shortestPathIds);
            const pathNodes = cy.nodes().filter((n) => pathSet.has(n.id()));
            const pathEdges = cy.edges().filter((e) => {
                const srcIdx = shortestPathIds.indexOf(e.source().id());
                const tgtIdx = shortestPathIds.indexOf(e.target().id());
                return srcIdx !== -1 && tgtIdx !== -1 && Math.abs(srcIdx - tgtIdx) === 1;
            });

            pathNodes.addClass('highlighted');
            pathEdges.addClass('highlighted');
            cy.elements().not(pathNodes.union(pathEdges)).addClass('dimmed');
        } else if (hoveredNodeId || selectedNodeId) {
            // Neighbor mode
            const activeId = hoveredNodeId || selectedNodeId;
            if (activeId) {
                const activeNode = cy.getElementById(activeId);
                if (activeNode.length) {
                    const neighborhood = activeNode.closedNeighborhood();
                    neighborhood.addClass('highlighted');
                    cy.elements().not(neighborhood).addClass('dimmed');
                }
            }
        }
    }, [shortestPathIds, hoveredNodeId, selectedNodeId]);

    // Resize observer
    useEffect(() => {
        const el = containerRef.current;
        const cy = cyRef.current;
        if (!el || !cy) return;

        const ro = new ResizeObserver(() => cy.resize());
        ro.observe(el);
        return () => ro.disconnect();
    }, []);

    return (
        <div className="flex-1 w-full h-full bg-[#111111] overflow-hidden relative"
            role="application"
            aria-label={`온톨로지 그래프. 노드 ${data.nodes.length}개 표출됨. 마우스 드래그로 이동.`}>
            {data.nodes.length > 0 ? (
                <div ref={containerRef} className="w-full h-full" />
            ) : (
                <div className="w-full h-full flex items-center justify-center text-neutral-500">
                    데이터가 없습니다.
                </div>
            )}
        </div>
    );
}
