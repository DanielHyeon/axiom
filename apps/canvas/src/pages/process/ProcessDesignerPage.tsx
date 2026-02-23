import { useState, useRef, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { Stage, Layer, Rect, Text, Group } from 'react-konva';
import { useProcessDesignerStore } from '@/stores/processDesignerStore';
import type { CanvasNode, CanvasItemType } from '@/stores/processDesignerStore';
import { ROUTES } from '@/lib/routes/routes';
import { PropertyPanel } from './PropertyPanel';
import { Minimap } from './Minimap';

const BOARD_STORAGE_PREFIX = 'process-board-';

// --- Types & Constants ---
const ITEM_COLORS: Record<CanvasItemType, string> = {
    businessEvent: '#ffb703',
    businessAction: '#87ceeb',
    businessEntity: '#ffff99',
    businessRule: '#ffc0cb',
};

const ITEM_LABELS: Record<CanvasItemType, string> = {
    businessEvent: 'Event',
    businessAction: 'Action',
    businessEntity: 'Entity',
    businessRule: 'Rule',
};

// --- Components ---
export function ProcessDesignerPage() {
    const { boardId } = useParams<{ boardId: string }>();
    const [searchParams] = useSearchParams();
    const fromOntology = searchParams.get('fromOntology');
    const { nodes, selectedNodeId, addNode, setNodes, updateNodePosition, updateNodeLabel, setSelectedNode, stageView, setStageView } = useProcessDesignerStore();
    const [stageSize, setStageSize] = useState({ width: 800, height: 600 });
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (containerRef.current) {
            setStageSize({
                width: containerRef.current.offsetWidth,
                height: containerRef.current.offsetHeight,
            });
        }
    }, []);

    useEffect(() => {
        if (!boardId) return;
        const raw = localStorage.getItem(BOARD_STORAGE_PREFIX + boardId);
        if (!raw) return;
        try {
            const parsed = JSON.parse(raw) as unknown;
            if (Array.isArray(parsed) && parsed.length > 0) {
                const valid = parsed.every(
                    (n): n is CanvasNode =>
                        n != null &&
                        typeof n === 'object' &&
                        typeof (n as CanvasNode).id === 'string' &&
                        typeof (n as CanvasNode).x === 'number' &&
                        typeof (n as CanvasNode).y === 'number'
                );
                if (valid) setNodes(parsed as CanvasNode[]);
            }
        } catch {
            // ignore invalid stored data
        }
    }, [boardId, setNodes]);

    const handleSaveBoard = () => {
        if (!boardId) return;
        localStorage.setItem(BOARD_STORAGE_PREFIX + boardId, JSON.stringify(nodes));
    };

    const handleDragStart = (e: React.DragEvent, type: CanvasItemType) => {
        e.dataTransfer.setData('nodeType', type);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        const type = e.dataTransfer.getData('nodeType') as CanvasItemType;
        if (!type) return;

        if (containerRef.current) {
            const rect = containerRef.current.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            addNode({
                type,
                x,
                y,
                label: `New ${ITEM_LABELS[type]} `,
                color: ITEM_COLORS[type],
            });
        }
    };

    const selectedNode = nodes.find(n => n.id === selectedNodeId);

    const handleMinimapClick = (virtualX: number, virtualY: number) => {
        const scale = stageView.scale;
        const cx = -virtualX + (stageSize.width / scale) / 2;
        const cy = -virtualY + (stageSize.height / scale) / 2;
        setStageView({ x: cx, y: cy });
    };

    return (
        <div className="flex flex-col h-[calc(100vh-4rem)] bg-neutral-950 text-white overflow-hidden border-t border-neutral-800">
            {fromOntology && (
                <div className="shrink-0 text-xs text-blue-300 bg-blue-950/50 border-b border-blue-800 px-3 py-1.5">
                    온톨로지 연동: <span className="font-mono">{fromOntology}</span>
                </div>
            )}
            <div className="flex flex-1 min-h-0">
            {/* 1. Toolbox */}
            <div className="w-64 border-r border-neutral-800 bg-neutral-900 flex flex-col">
                <div className="p-4 border-b border-neutral-800 font-bold text-sm text-neutral-300 flex items-center justify-between gap-2">
                    <span>도구 상자 (Toolbox)</span>
                    <div className="flex items-center gap-2 shrink-0">
                        {boardId && (
                            <button
                                type="button"
                                onClick={handleSaveBoard}
                                className="rounded bg-emerald-600 text-white px-2 py-1 text-xs font-medium"
                            >
                                저장
                            </button>
                        )}
                        <Link
                            to={ROUTES.PROCESS_DESIGNER.LIST}
                            className="text-xs text-neutral-400 hover:text-white"
                        >
                            목록
                        </Link>
                    </div>
                </div>
                <div className="p-4 space-y-3 flex-1 overflow-auto">
                    {(Object.keys(ITEM_COLORS) as CanvasItemType[]).map((type) => (
                        <div
                            key={type}
                            draggable
                            onDragStart={(e) => handleDragStart(e, type)}
                            className="px-4 py-3 rounded text-sm text-neutral-900 font-medium cursor-grab active:cursor-grabbing shadow flex items-center gap-2"
                            style={{ backgroundColor: ITEM_COLORS[type] }}
                        >
                            <div className="w-3 h-3 rounded-full bg-white opacity-50" />
                            {ITEM_LABELS[type]}
                        </div>
                    ))}
                </div>
            </div>

            {/* 2. Canvas Area */}
            <div
                className="flex-1 bg-neutral-950 relative"
                ref={containerRef}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={(e) => {
                    // Deselect if clicking on empty stage space
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    if (e.target === (e.target as any).getStage()) {
                        setSelectedNode(null);
                    }
                }}
            >
                <Stage width={stageSize.width} height={stageSize.height}>
                    <Layer>
                        <Group
                            x={stageView.x}
                            y={stageView.y}
                            scaleX={stageView.scale}
                            scaleY={stageView.scale}
                        >
                            <Rect
                                x={-5000}
                                y={-5000}
                                width={10000}
                                height={10000}
                                listening
                                onClick={() => setSelectedNode(null)}
                            />
                            {nodes.map(node => (
                                <Group
                                    key={node.id}
                                    x={node.x}
                                    y={node.y}
                                    draggable
                                    onClick={() => setSelectedNode(node.id)}
                                    onDragEnd={(e) => {
                                        updateNodePosition(node.id, e.target.x(), e.target.y());
                                    }}
                                >
                                    <Rect
                                        width={140}
                                        height={80}
                                        fill={node.color}
                                        cornerRadius={4}
                                        shadowColor="black"
                                        shadowBlur={selectedNodeId === node.id ? 10 : 2}
                                        shadowOpacity={0.3}
                                        stroke={selectedNodeId === node.id ? '#ffffff' : 'transparent'}
                                        strokeWidth={2}
                                    />
                                    <Text
                                        text={node.label}
                                        width={140}
                                        height={80}
                                        fill="#000000"
                                        align="center"
                                        verticalAlign="middle"
                                        fontStyle="bold"
                                        padding={10}
                                    />
                                </Group>
                            ))}
                        </Group>
                    </Layer>
                </Stage>
                <div className="absolute top-4 left-4 bg-neutral-900/80 px-3 py-1.5 rounded text-xs text-neutral-400 pointer-events-none">
                    노드를 드래그하여 배치하세요
                </div>
                <Minimap
                    nodes={nodes}
                    stageSize={stageSize}
                    stageView={stageView}
                    onViewportClick={handleMinimapClick}
                />
            </div>

            <PropertyPanel selectedNode={selectedNode ?? null} onUpdateLabel={updateNodeLabel} />
            </div>
        </div>
    );
}
