import { useMemo, useRef, useCallback, useState, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { ForceGraphMethods } from 'react-force-graph-2d';
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

interface BipartiteNode {
    id: string;
    label: string;
    group: 'ontology' | 'schema';
    layer?: OntologyLayer;
    fx?: number;
    fy?: number | null;
    x?: number;
    y?: number;
}

interface BipartiteLink {
    source: string;
    target: string;
    relType: string;
}

interface BipartiteGraphViewProps {
    mappings: ConceptMapping[];
    ontologyNodes: OntologyNode[];
    tables: SchemaEntity[];
    height?: number;
}

function buildBipartiteData(
    mappings: ConceptMapping[],
    ontologyNodes: OntologyNode[],
    tables: SchemaEntity[],
    containerWidth: number,
): { nodes: BipartiteNode[]; links: BipartiteLink[] } {
    if (mappings.length === 0) return { nodes: [], links: [] };

    const ontologyNodeMap = new Map(ontologyNodes.map((n) => [n.id, n]));
    const leftX = containerWidth * 0.25;
    const rightX = containerWidth * 0.75;

    // Collect unique mapped source IDs and target tables
    const mappedSourceIds = new Set(mappings.map((m) => m.source_id));
    const mappedTargetTables = new Set(mappings.map((m) => m.target_table));

    const nodes: BipartiteNode[] = [];
    const nodeIds = new Set<string>();

    // Ontology nodes (left column)
    let leftIndex = 0;
    for (const srcId of mappedSourceIds) {
        if (nodeIds.has(srcId)) continue;
        nodeIds.add(srcId);
        const ontNode = ontologyNodeMap.get(srcId);
        nodes.push({
            id: srcId,
            label: ontNode?.label ?? srcId,
            group: 'ontology',
            layer: ontNode?.layer,
            fx: leftX,
            fy: 80 + leftIndex * 60,
        });
        leftIndex++;
    }

    // Schema table nodes (right column)
    let rightIndex = 0;
    for (const tblName of mappedTargetTables) {
        const nodeId = `table:${tblName}`;
        if (nodeIds.has(nodeId)) continue;
        nodeIds.add(nodeId);
        const schemaEntity = tables.find((t) => t.name === tblName);
        nodes.push({
            id: nodeId,
            label: schemaEntity ? `${schemaEntity.schema}.${tblName}` : tblName,
            group: 'schema',
            fx: rightX,
            fy: 80 + rightIndex * 60,
        });
        rightIndex++;
    }

    // Links
    const links: BipartiteLink[] = mappings
        .filter((m) => nodeIds.has(m.source_id) && nodeIds.has(`table:${m.target_table}`))
        .map((m) => ({
            source: m.source_id,
            target: `table:${m.target_table}`,
            relType: m.rel_type,
        }));

    return { nodes, links };
}

export function BipartiteGraphView({
    mappings,
    ontologyNodes,
    tables,
    height = 400,
}: BipartiteGraphViewProps) {
    const fgRef = useRef<ForceGraphMethods>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [containerWidth, setContainerWidth] = useState(800);
    const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

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

    const graphData = useMemo(
        () => buildBipartiteData(mappings, ontologyNodes, tables, containerWidth),
        [mappings, ontologyNodes, tables, containerWidth],
    );

    // Highlight sets for hover
    const highlightNodes = useMemo(() => {
        const set = new Set<string>();
        if (!hoveredNodeId) return set;
        set.add(hoveredNodeId);
        graphData.links.forEach((l) => {
            const srcId = typeof l.source === 'object' ? (l.source as BipartiteNode).id : l.source;
            const tgtId = typeof l.target === 'object' ? (l.target as BipartiteNode).id : l.target;
            if (srcId === hoveredNodeId || tgtId === hoveredNodeId) {
                set.add(srcId);
                set.add(tgtId);
            }
        });
        return set;
    }, [hoveredNodeId, graphData.links]);

    const highlightLinkSet = useMemo(() => {
        const set = new Set<BipartiteLink>();
        if (!hoveredNodeId) return set;
        graphData.links.forEach((l) => {
            const srcId = typeof l.source === 'object' ? (l.source as BipartiteNode).id : l.source;
            const tgtId = typeof l.target === 'object' ? (l.target as BipartiteNode).id : l.target;
            if (srcId === hoveredNodeId || tgtId === hoveredNodeId) {
                set.add(l);
            }
        });
        return set;
    }, [hoveredNodeId, graphData.links]);

    const drawNode = useCallback(
        (node: BipartiteNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
            const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node.id);
            const opacity = isHighlighted ? 1 : 0.3;
            const x = node.x ?? 0;
            const y = node.y ?? 0;

            ctx.globalAlpha = opacity;

            if (node.group === 'ontology') {
                // Circle with layer color
                const color = node.layer ? LAYER_COLORS[node.layer] : '#9CA3AF';
                const radius = 6;
                ctx.beginPath();
                ctx.arc(x, y, radius, 0, 2 * Math.PI);
                ctx.fillStyle = color;
                ctx.fill();

                // Label to the left
                const fontSize = Math.max(10 / globalScale, 3);
                ctx.font = `${fontSize}px sans-serif`;
                ctx.fillStyle = `rgba(255,255,255,${opacity})`;
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                ctx.fillText(node.label, x - radius - 4, y);
            } else {
                // Rounded rectangle for schema tables
                const w = 8;
                const h = 6;
                const r = 2;
                ctx.beginPath();
                ctx.moveTo(x - w + r, y - h);
                ctx.lineTo(x + w - r, y - h);
                ctx.arcTo(x + w, y - h, x + w, y - h + r, r);
                ctx.lineTo(x + w, y + h - r);
                ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
                ctx.lineTo(x - w + r, y + h);
                ctx.arcTo(x - w, y + h, x - w, y + h - r, r);
                ctx.lineTo(x - w, y - h + r);
                ctx.arcTo(x - w, y - h, x - w + r, y - h, r);
                ctx.closePath();
                ctx.fillStyle = SCHEMA_COLOR;
                ctx.fill();

                // Label to the right
                const fontSize = Math.max(10 / globalScale, 3);
                ctx.font = `${fontSize}px sans-serif`;
                ctx.fillStyle = `rgba(255,255,255,${opacity})`;
                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillText(node.label, x + w + 4, y);
            }

            ctx.globalAlpha = 1;
        },
        [highlightNodes],
    );

    if (mappings.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-12 text-neutral-600">
                <Link size={24} className="mb-2 opacity-30" />
                <p className="text-sm">매핑이 없습니다. 위에서 새 매핑을 추가하면 시각화가 표시됩니다.</p>
            </div>
        );
    }

    return (
        <div ref={containerRef} className="w-full border border-neutral-800 rounded-lg bg-[#111111] overflow-hidden">
            {/* Legend */}
            <div className="flex items-center gap-4 px-3 py-2 border-b border-neutral-800/50 text-[10px] text-neutral-500">
                <span className="font-medium text-neutral-400">범례:</span>
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
                <span className="border-l border-neutral-700 pl-3 ml-1" />
                {Object.entries(REL_COLORS).map(([rel, color]) => (
                    <span key={rel} className="flex items-center gap-1">
                        <span className="w-4 h-0.5 inline-block" style={{ backgroundColor: color }} />
                        {rel}
                    </span>
                ))}
            </div>
            <ForceGraph2D
                ref={fgRef as unknown as React.MutableRefObject<ForceGraphMethods>}
                graphData={graphData as unknown as { nodes: object[]; links: object[] }}
                width={containerWidth}
                height={height}
                nodeCanvasObject={(node, ctx, globalScale) =>
                    drawNode(node as unknown as BipartiteNode, ctx, globalScale)
                }
                nodeRelSize={6}
                linkColor={(link) => {
                    const l = link as unknown as BipartiteLink;
                    if (highlightLinkSet.size > 0 && !highlightLinkSet.has(l)) {
                        return 'rgba(64,64,64,0.3)';
                    }
                    return REL_COLORS[l.relType] ?? '#404040';
                }}
                linkWidth={(link) => (highlightLinkSet.has(link as unknown as BipartiteLink) ? 2 : 1)}
                linkDirectionalArrowLength={4}
                linkDirectionalArrowRelPos={1}
                onNodeHover={(node) =>
                    setHoveredNodeId(node ? (node as unknown as BipartiteNode).id : null)
                }
                d3AlphaDecay={0.05}
                d3VelocityDecay={0.4}
                warmupTicks={50}
                cooldownTicks={100}
                enableZoomInteraction={true}
                enablePanInteraction={true}
            />
        </div>
    );
}
