import { useState, useRef, useEffect } from 'react';
import { Stage, Layer, Rect, Text, Group } from 'react-konva';
import { useProcessDesignerStore } from '@/stores/processDesignerStore';
import type { CanvasItemType } from '@/stores/processDesignerStore';

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
    const { nodes, selectedNodeId, addNode, updateNodePosition, setSelectedNode } = useProcessDesignerStore();
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

    return (
        <div className="flex h-[calc(100vh-4rem)] bg-neutral-950 text-white overflow-hidden border-t border-neutral-800">

            {/* 1. Toolbox */}
            <div className="w-64 border-r border-neutral-800 bg-neutral-900 flex flex-col">
                <div className="p-4 border-b border-neutral-800 font-bold text-sm text-neutral-300">
                    도구 상자 (Toolbox)
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
                    </Layer>
                </Stage>
                <div className="absolute top-4 left-4 bg-neutral-900/80 px-3 py-1.5 rounded text-xs text-neutral-400 pointer-events-none">
                    노드를 드래그하여 배치하세요
                </div>
            </div>

            {/* 3. Property Panel */}
            <div className="w-80 border-l border-neutral-800 bg-neutral-900 flex flex-col">
                <div className="p-4 border-b border-neutral-800 font-bold text-sm text-neutral-300">
                    속성 패널 (Property Panel)
                </div>
                <div className="p-4 flex-1">
                    {selectedNode ? (
                        <div className="space-y-4">
                            <div>
                                <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">ID</label>
                                <div className="text-sm font-mono bg-neutral-950 px-2 py-1 rounded text-neutral-400">{selectedNode.id}</div>
                            </div>
                            <div>
                                <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">Type</label>
                                <div className="text-sm px-2 py-1 rounded bg-neutral-950 text-neutral-300">{ITEM_LABELS[selectedNode.type]}</div>
                            </div>
                            <div>
                                <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">Label</label>
                                <input
                                    type="text"
                                    value={selectedNode.label}
                                    readOnly
                                    className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1.5 text-sm text-white"
                                />
                                <p className="text-xs text-neutral-500 mt-1">이름 편집은 캔버스의 인라인 편집을 사용하세요.</p>
                            </div>
                            <div className="grid grid-cols-2 gap-2 mt-4">
                                <div>
                                    <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">X Position</label>
                                    <div className="text-sm px-2 py-1 bg-neutral-950 rounded text-neutral-400">{Math.round(selectedNode.x)}</div>
                                </div>
                                <div>
                                    <label className="text-xs text-neutral-500 uppercase tracking-wider block mb-1">Y Position</label>
                                    <div className="text-sm px-2 py-1 bg-neutral-950 rounded text-neutral-400">{Math.round(selectedNode.y)}</div>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="h-full flex items-center justify-center text-sm text-neutral-500 text-center">
                            캔버스에서 노드를 선택하여<br />속성을 확인하세요.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
