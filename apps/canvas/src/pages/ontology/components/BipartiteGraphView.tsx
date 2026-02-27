import { useMemo, useRef, useEffect, useState } from 'react';
import cytoscape from 'cytoscape';
import { Link } from 'lucide-react';
import type { OntologyNode, OntologyLayer, ConceptMapping, SchemaEntity } from '@/features/ontology/types/ontology';

const LAYER_COLORS: Record<OntologyLayer, string> = {
    kpi: '#EF4444',
    measure: '#F59E0B',
    process: '#3B82F6',
    resource: '#10B981',
};

const REL_COLORS: Record<string, string> = {
    MAPS_TO: '#3B82F6',
    DERIVED_FROM: '#F59E0B',
    DEFINES: '#10B981',
};

const SCHEMA_COLOR = '#6B7280';

interface BipartiteGraphViewProps {
    mappings: ConceptMapping[];
    ontologyNodes: OntologyNode[];
    tables: SchemaEntity[];
    height?: number;
}

function buildCyElements(
    mappings: ConceptMapping[],
    ontologyNodes: OntologyNode[],
    tables: SchemaEntity[],
): cytoscape.ElementDefinition[] {
    if (mappings.length === 0) return [];

    const ontologyNodeMap = new Map(ontologyNodes.map((n) => [n.id, n]));
    const elements: cytoscape.ElementDefinition[] = [];
    const nodeIds = new Set<string>();

    // Ontology nodes (left column)
    const mappedSourceIds = new Set(mappings.map((m) => m.source_id));
    let leftIndex = 0;
    for (const srcId of mappedSourceIds) {
        if (nodeIds.has(srcId)) continue;
        nodeIds.add(srcId);
        const ontNode = ontologyNodeMap.get(srcId);
        elements.push({
            group: 'nodes',
            data: {
                id: srcId,
                label: ontNode?.label ?? srcId,
                group: 'ontology',
                layer: ontNode?.layer || 'resource',
                column: 'left',
                order: leftIndex,
            },
            classes: `ontology ${ontNode?.layer || 'resource'}`,
        });
        leftIndex++;
    }

    // Schema table nodes (right column)
    const mappedTargetTables = new Set(mappings.map((m) => m.target_table));
    let rightIndex = 0;
    for (const tblName of mappedTargetTables) {
        const nodeId = `table:${tblName}`;
        if (nodeIds.has(nodeId)) continue;
        nodeIds.add(nodeId);
        const schemaEntity = tables.find((t) => t.name === tblName);
        elements.push({
            group: 'nodes',
            data: {
                id: nodeId,
                label: schemaEntity ? `${schemaEntity.schema}.${tblName}` : tblName,
                group: 'schema',
                column: 'right',
                order: rightIndex,
            },
            classes: 'schema',
        });
        rightIndex++;
    }

    // Edges
    mappings.forEach((m, i) => {
        const targetId = `table:${m.target_table}`;
        if (nodeIds.has(m.source_id) && nodeIds.has(targetId)) {
            elements.push({
                group: 'edges',
                data: {
                    id: `bip-${m.source_id}-${targetId}-${i}`,
                    source: m.source_id,
                    target: targetId,
                    relType: m.rel_type,
                },
            });
        }
    });

    return elements;
}

const BIPARTITE_STYLE: cytoscape.Stylesheet[] = [
    {
        selector: 'node',
        style: {
            label: 'data(label)',
            'font-size': 11,
            color: '#333333',
            'text-outline-width': 2,
            'text-outline-color': '#F5F5F5',
            width: 20,
            height: 20,
            'overlay-opacity': 0,
        },
    },
    // Ontology nodes: circle with layer color, label left
    {
        selector: 'node.ontology',
        style: {
            shape: 'ellipse',
            'text-halign': 'left',
            'text-margin-x': -8,
        },
    },
    {
        selector: 'node.kpi',
        style: { 'background-color': LAYER_COLORS.kpi },
    },
    {
        selector: 'node.measure',
        style: { 'background-color': LAYER_COLORS.measure },
    },
    {
        selector: 'node.process',
        style: { 'background-color': LAYER_COLORS.process },
    },
    {
        selector: 'node.resource',
        style: { 'background-color': LAYER_COLORS.resource },
    },
    // Schema nodes: rectangle, label right
    {
        selector: 'node.schema',
        style: {
            shape: 'round-rectangle',
            'background-color': SCHEMA_COLOR,
            width: 28,
            height: 20,
            'text-halign': 'right',
            'text-margin-x': 8,
        },
    },
    // Edges
    {
        selector: 'edge',
        style: {
            width: 1.5,
            'line-color': '#CCCCCC',
            'target-arrow-color': '#CCCCCC',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.7,
            'overlay-opacity': 0,
        },
    },
    {
        selector: 'edge[relType = "MAPS_TO"]',
        style: { 'line-color': REL_COLORS.MAPS_TO, 'target-arrow-color': REL_COLORS.MAPS_TO },
    },
    {
        selector: 'edge[relType = "DERIVED_FROM"]',
        style: { 'line-color': REL_COLORS.DERIVED_FROM, 'target-arrow-color': REL_COLORS.DERIVED_FROM },
    },
    {
        selector: 'edge[relType = "DEFINES"]',
        style: { 'line-color': REL_COLORS.DEFINES, 'target-arrow-color': REL_COLORS.DEFINES },
    },
    // Highlight / dim
    {
        selector: 'node.highlighted',
        style: { 'border-width': 2, 'border-color': '#333333', 'z-index': 10 },
    },
    {
        selector: 'edge.highlighted',
        style: { width: 2.5, 'z-index': 10 },
    },
    {
        selector: '.dimmed',
        style: { opacity: 0.15 },
    },
];

export function BipartiteGraphView({
    mappings,
    ontologyNodes,
    tables,
    height = 400,
}: BipartiteGraphViewProps) {
    const cyRef = useRef<cytoscape.Core | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState(800);

    const elements = useMemo(
        () => buildCyElements(mappings, ontologyNodes, tables),
        [mappings, ontologyNodes, tables],
    );

    // Track container width
    useEffect(() => {
        if (!containerRef.current) return;
        const observer = new ResizeObserver((entries) => {
            for (const entry of entries) {
                setContainerWidth(entry.contentRect.width);
            }
        });
        observer.observe(containerRef.current);
        return () => observer.disconnect();
    }, []);

    // Init cytoscape
    useEffect(() => {
        if (!containerRef.current) return;

        const cy = cytoscape({
            container: containerRef.current,
            style: BIPARTITE_STYLE,
            elements: [],
            userZoomingEnabled: true,
            userPanningEnabled: true,
            minZoom: 0.3,
            maxZoom: 4,
        });

        // Hover highlight
        cy.on('mouseover', 'node', (evt) => {
            const node = evt.target;
            const neighborhood = node.closedNeighborhood();
            neighborhood.addClass('highlighted');
            cy.elements().not(neighborhood).addClass('dimmed');
        });

        cy.on('mouseout', 'node', () => {
            cy.elements().removeClass('highlighted dimmed');
        });

        cyRef.current = cy;
        return () => {
            cy.destroy();
            cyRef.current = null;
        };
    }, []);

    // Sync elements & apply bipartite layout
    useEffect(() => {
        const cy = cyRef.current;
        if (!cy) return;

        cy.elements().remove();
        if (elements.length === 0) return;

        cy.add(elements);

        // Manual bipartite positioning: left column / right column
        const leftX = containerWidth * 0.25;
        const rightX = containerWidth * 0.75;

        cy.nodes('.ontology').forEach((node) => {
            const order = node.data('order') as number;
            node.position({ x: leftX, y: 60 + order * 60 });
        });

        cy.nodes('.schema').forEach((node) => {
            const order = node.data('order') as number;
            node.position({ x: rightX, y: 60 + order * 60 });
        });

        // Lock positions to prevent physics drift
        cy.nodes().lock();

        setTimeout(() => cy.fit(undefined, 30), 50);
    }, [elements, containerWidth]);

    if (mappings.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12 text-[#999]">
                <Link size={24} className="mb-2 opacity-30" />
                <p className="text-sm font-[IBM_Plex_Mono]">매핑이 없습니다. 위에서 새 매핑을 추가하면 시각화가 표시됩니다.</p>
            </div>
        );
    }

    return (
        <div className="w-full border border-[#E5E5E5] rounded bg-[#F5F5F5] overflow-hidden">
            {/* Legend */}
            <div className="flex items-center gap-4 px-3 py-2 border-b border-[#E5E5E5] text-[10px] text-[#999] font-[IBM_Plex_Mono]">
                <span className="font-medium text-[#5E5E5E]">범례:</span>
                {Object.entries(LAYER_COLORS).map(([layer, color]) => (
                    <span key={layer} className="flex items-center gap-1">
                        <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: color }} />
                        {layer.toUpperCase()}
                    </span>
                ))}
                <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded inline-block" style={{ backgroundColor: SCHEMA_COLOR }} />
                    Table
                </span>
                <span className="border-l border-[#E5E5E5] pl-3 ml-1" />
                {Object.entries(REL_COLORS).map(([rel, color]) => (
                    <span key={rel} className="flex items-center gap-1">
                        <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: color }} />
                        {rel}
                    </span>
                ))}
            </div>
            <div ref={containerRef} style={{ height }} className="w-full" />
        </div>
    );
}
