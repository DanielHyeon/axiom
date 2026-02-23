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

export interface StageViewState {
    x: number;
    y: number;
    scale: number;
}

interface ProcessDesignerState {
    nodes: CanvasNode[];
    selectedNodeId: string | null;
    stageView: StageViewState;
    addNode: (node: Omit<CanvasNode, 'id'>) => void;
    setNodes: (nodes: CanvasNode[]) => void;
    updateNodePosition: (id: string, x: number, y: number) => void;
    updateNodeLabel: (id: string, label: string) => void;
    setSelectedNode: (id: string | null) => void;
    setStageView: (view: Partial<StageViewState>) => void;
}

export const useProcessDesignerStore = create<ProcessDesignerState>((set) => ({
    nodes: [
        { id: '1', type: 'businessEvent', x: 100, y: 150, label: '입고 접수', color: '#ffb703' },
        { id: '2', type: 'businessAction', x: 300, y: 150, label: '검수 시작', color: '#87ceeb' },
    ],
    selectedNodeId: null,
    stageView: { x: 0, y: 0, scale: 1 },
    addNode: (node) => set((state) => ({
        nodes: [...state.nodes, { ...node, id: crypto.randomUUID() }]
    })),
    setNodes: (nodes) => set({ nodes }),
    updateNodePosition: (id, x, y) => set((state) => ({
        nodes: state.nodes.map(n => n.id === id ? { ...n, x, y } : n)
    })),
    updateNodeLabel: (id, label) => set((state) => ({
        nodes: state.nodes.map(n => n.id === id ? { ...n, label } : n)
    })),
    setSelectedNode: (id) => set({ selectedNodeId: id }),
    setStageView: (view) => set((state) => ({
        stageView: { ...state.stageView, ...view }
    })),
}));
