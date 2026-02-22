import { create } from 'zustand';

export type CanvasItemType =
    | 'businessEvent'
    | 'businessAction'
    | 'businessEntity'
    | 'businessRule';

export interface CanvasNode {
    id: string;
    type: CanvasItemType;
    x: number;
    y: number;
    label: string;
    color: string;
}

interface ProcessDesignerState {
    nodes: CanvasNode[];
    selectedNodeId: string | null;
    addNode: (node: Omit<CanvasNode, 'id'>) => void;
    setNodes: (nodes: CanvasNode[]) => void;
    updateNodePosition: (id: string, x: number, y: number) => void;
    setSelectedNode: (id: string | null) => void;
}

export const useProcessDesignerStore = create<ProcessDesignerState>((set) => ({
    nodes: [
        { id: '1', type: 'businessEvent', x: 100, y: 150, label: '입고 접수', color: '#ffb703' },
        { id: '2', type: 'businessAction', x: 300, y: 150, label: '검수 시작', color: '#87ceeb' },
    ],
    selectedNodeId: null,
    addNode: (node) => set((state) => ({
        nodes: [...state.nodes, { ...node, id: crypto.randomUUID() }]
    })),
    setNodes: (nodes) => set({ nodes }),
    updateNodePosition: (id, x, y) => set((state) => ({
        nodes: state.nodes.map(n => n.id === id ? { ...n, x, y } : n)
    })),
    setSelectedNode: (id) => set({ selectedNodeId: id })
}));
