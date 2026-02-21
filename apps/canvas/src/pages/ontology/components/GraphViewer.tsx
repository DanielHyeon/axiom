import { useEffect, useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { ForceGraphMethods } from 'react-force-graph-2d';
import { useOntologyStore } from '@/features/ontology/store/useOntologyStore';
import type { OntologyNode, OntologyEdge, OntologyGraphData } from '@/features/ontology/types/ontology';

const LAYER_COLORS = {
    kpi: '#EF4444',     // Red
    measure: '#F59E0B', // Orange
    process: '#3B82F6', // Blue
    resource: '#10B981' // Green
};

interface GraphViewerProps {
    data: OntologyGraphData;
    shortestPathIds: string[];
}

export function GraphViewer({ data, shortestPathIds }: GraphViewerProps) {
    const fgRef = useRef<ForceGraphMethods>(null);
    const { selectedNodeId, hoveredNodeId, selectNode, setHoveredNode } = useOntologyStore();

    // Zoom to fit on initial full load
    useEffect(() => {
        if (data.nodes.length > 0 && fgRef.current) {
            fgRef.current.zoomToFit(400, 50); // duration, padding
        }
    }, [data.nodes.length]);

    // Handle Window Resize (optional but good for responsive canvas)
    useEffect(() => {
        const handleResize = () => {
            if (fgRef.current) {
                // The wrapper div will trigger remeasure, but we can force update
                fgRef.current.zoomToFit(100);
            }
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    const highlightNodes = new Set<string>();
    const highlightLinks = new Set<OntologyEdge>();

    // Determine highlighted elements based on Hover, Selection, or Path
    if (shortestPathIds.length > 0) {
        shortestPathIds.forEach(id => highlightNodes.add(id));
        data.links.forEach(link => {
            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
            const targetId = typeof link.target === 'object' ? link.target.id : link.target;

            const sourceIdx = shortestPathIds.indexOf(sourceId);
            const targetIdx = shortestPathIds.indexOf(targetId);

            // If they are adjacent in the path array
            if (sourceIdx !== -1 && targetIdx !== -1 && Math.abs(sourceIdx - targetIdx) === 1) {
                highlightLinks.add(link);
            }
        });
    } else if (hoveredNodeId || selectedNodeId) {
        const activeId = hoveredNodeId || selectedNodeId;
        if (activeId) {
            highlightNodes.add(activeId);
            data.links.forEach(link => {
                const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                if (sourceId === activeId || targetId === activeId) {
                    highlightLinks.add(link);
                    highlightNodes.add(sourceId);
                    highlightNodes.add(targetId);
                }
            });
        }
    }

    const drawNode = useCallback((node: OntologyNode, ctx: CanvasRenderingContext2D, globalScale: number) => {
        // Opacity dampening if something is highlighted but this node isn't
        const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node.id);
        const opacity = isHighlighted ? 1 : 0.2;

        const size = (node.val || 1) * 3; // Base size multiplied by edge degree
        const color = LAYER_COLORS[node.layer];

        ctx.beginPath();
        ctx.globalAlpha = opacity;
        ctx.fillStyle = color;

        // Custom Shapes based on Layer
        // KPI: Circle, Process: Square, Measure: Triangle (Custom drawing), Resource: Diamond
        if (node.layer === 'kpi' || node.layer === 'process') {
            // For simplicity in Canvas mapping, sticking to basic primitives for now
            ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI, false);
            ctx.fill();
        } else if (node.layer === 'resource') {
            ctx.rect(node.x! - size, node.y! - size, size * 2, size * 2);
            ctx.fill();
        } else {
            // Diamond
            ctx.moveTo(node.x!, node.y! - size);
            ctx.lineTo(node.x! + size, node.y!);
            ctx.lineTo(node.x!, node.y! + size);
            ctx.lineTo(node.x! - size, node.y!);
            ctx.closePath();
            ctx.fill();
        }

        // Draw Selection Halo
        if (node.id === selectedNodeId) {
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = '#ffffff';
            ctx.stroke();
        }

        // Label Rendering (only when zoomed in or highlighted)
        if (isHighlighted && globalScale > 1.5) {
            const label = node.label;
            const fontSize = 12 / globalScale;
            ctx.font = `${fontSize}px Sans-Serif`;
            ctx.fillStyle = `rgba(255,255,255, ${opacity})`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(label, node.x!, node.y! + size + fontSize);
        }
        ctx.globalAlpha = 1; // Reset
    }, [highlightNodes, selectedNodeId]);

    const handleNodeClick = useCallback((node: OntologyNode) => {
        if (selectedNodeId === node.id) {
            selectNode(null); // Toggle off
        } else {
            selectNode(node.id);
            // Optional: Pan to Center
            fgRef.current?.centerAt(node.x, node.y, 1000);
            fgRef.current?.zoom(3, 1000); // Level 3 zoom
        }
    }, [selectedNodeId, selectNode]);

    return (
        <div className="flex-1 w-full h-full bg-[#111111] overflow-hidden"
            role="application"
            aria-label={`온톨로지 그래프. 노드 ${data.nodes.length}개 표출됨. 마우스 드래그로 이동.`}>
            {data.nodes.length > 0 ? (
                <ForceGraph2D
                    ref={fgRef as any}
                    graphData={data as any}
                    nodeCanvasObject={(node, ctx, globalScale) => drawNode(node as OntologyNode, ctx, globalScale)}
                    nodeRelSize={6}
                    linkColor={(link) => highlightLinks.has(link as OntologyEdge) ? '#ffffff' : '#404040'}
                    linkWidth={(link) => highlightLinks.has(link as OntologyEdge) ? 2 : 1}
                    linkDirectionalArrowLength={3.5}
                    linkDirectionalArrowRelPos={1}
                    onNodeHover={(node) => setHoveredNode(node ? (node as OntologyNode).id : null)}
                    onNodeClick={(node) => handleNodeClick(node as OntologyNode)}
                    d3AlphaDecay={0.02} // Slower decay for smoother settling
                    d3VelocityDecay={0.3} // Less friction
                />
            ) : (
                <div className="w-full h-full flex items-center justify-center text-neutral-500">
                    데이터가 없습니다.
                </div>
            )}
        </div>
    );
}
