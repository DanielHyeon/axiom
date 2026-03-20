/**
 * 워크플로 에디터 Zustand 스토어
 *
 * 노드·엣지 CRUD, 선택 상태, 저장/불러오기를 관리한다.
 * Cytoscape 캔버스와 속성 패널이 이 스토어를 공유한다.
 */

import { create } from 'zustand';
import { toast } from 'sonner';
import type {
  WorkflowNode,
  WorkflowEdge,
  WorkflowDefinition,
  WorkflowMetadata,
  WorkflowNodeData,
} from '../types/workflowEditor.types';

// ──────────────────────────────────────
// 스토어 인터페이스
// ──────────────────────────────────────

interface WorkflowEditorState {
  /** 현재 워크플로 노드 목록 */
  nodes: WorkflowNode[];
  /** 현재 워크플로 엣지 목록 */
  edges: WorkflowEdge[];
  /** 메타데이터 */
  metadata: WorkflowMetadata;
  /** 선택된 노드 ID */
  selectedNodeId: string | null;
  /** 변경 여부 (저장 안 된 상태) */
  isDirty: boolean;

  // ── 노드 CRUD ──
  addNode: (node: WorkflowNode) => void;
  removeNode: (id: string) => void;
  updateNode: (id: string, patch: Partial<Omit<WorkflowNode, 'id'>>) => void;
  updateNodeData: (id: string, data: WorkflowNodeData) => void;

  // ── 엣지 CRUD ──
  addEdge: (edge: WorkflowEdge) => void;
  removeEdge: (id: string) => void;

  // ── 선택 ──
  setSelectedNode: (id: string | null) => void;

  // ── 저장 / 불러오기 ──
  /** 현재 상태를 WorkflowDefinition으로 직렬화 후 저장 */
  save: () => void;
  /** WorkflowDefinition을 스토어에 로드 */
  load: (definition: WorkflowDefinition) => void;
  /** 초기 상태로 리셋 */
  reset: () => void;

  // ── 메타데이터 ──
  updateMetadata: (patch: Partial<WorkflowMetadata>) => void;
}

// ──────────────────────────────────────
// 초기값
// ──────────────────────────────────────

const createDefaultMetadata = (): WorkflowMetadata => ({
  id: crypto.randomUUID(),
  name: '새 워크플로',
  description: '',
  version: 1,
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  createdBy: '',
  enabled: false,
});

// ──────────────────────────────────────
// 스토어 생성
// ──────────────────────────────────────

export const useWorkflowEditorStore = create<WorkflowEditorState>((set, get) => ({
  nodes: [],
  edges: [],
  metadata: createDefaultMetadata(),
  selectedNodeId: null,
  isDirty: false,

  // ── 노드 ──

  addNode: (node) =>
    set((s) => ({
      nodes: [...s.nodes, node],
      isDirty: true,
    })),

  removeNode: (id) =>
    set((s) => ({
      // 노드 삭제 시 연결된 엣지도 함께 제거
      nodes: s.nodes.filter((n) => n.id !== id),
      edges: s.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: s.selectedNodeId === id ? null : s.selectedNodeId,
      isDirty: true,
    })),

  updateNode: (id, patch) =>
    set((s) => ({
      nodes: s.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)),
      isDirty: true,
    })),

  updateNodeData: (id, data) =>
    set((s) => ({
      nodes: s.nodes.map((n) => (n.id === id ? { ...n, data } : n)),
      isDirty: true,
    })),

  // ── 엣지 ──

  addEdge: (edge) =>
    set((s) => {
      // 중복 엣지 방지
      const exists = s.edges.some(
        (e) => e.source === edge.source && e.target === edge.target,
      );
      if (exists) {
        toast.warning('이미 연결된 엣지입니다.');
        return s;
      }
      return { edges: [...s.edges, edge], isDirty: true };
    }),

  removeEdge: (id) =>
    set((s) => ({
      edges: s.edges.filter((e) => e.id !== id),
      isDirty: true,
    })),

  // ── 선택 ──

  setSelectedNode: (id) => set({ selectedNodeId: id }),

  // ── 저장 / 불러오기 ──

  save: () => {
    const { nodes, edges, metadata } = get();
    const definition: WorkflowDefinition = {
      nodes,
      edges,
      metadata: { ...metadata, updatedAt: new Date().toISOString() },
    };

    // 로컬 스토리지에 임시 저장 (추후 API 연동)
    try {
      localStorage.setItem(
        `workflow_${definition.metadata.id}`,
        JSON.stringify(definition),
      );
      set({
        isDirty: false,
        metadata: { ...metadata, updatedAt: new Date().toISOString() },
      });
      toast.success('워크플로가 저장되었습니다.');
    } catch (err) {
      toast.error('저장에 실패했습니다.');
      console.error('[WorkflowEditor] 저장 오류:', err);
    }
  },

  load: (definition) =>
    set({
      nodes: definition.nodes,
      edges: definition.edges,
      metadata: definition.metadata,
      selectedNodeId: null,
      isDirty: false,
    }),

  reset: () =>
    set({
      nodes: [],
      edges: [],
      metadata: createDefaultMetadata(),
      selectedNodeId: null,
      isDirty: false,
    }),

  // ── 메타데이터 ──

  updateMetadata: (patch) =>
    set((s) => ({
      metadata: { ...s.metadata, ...patch },
      isDirty: true,
    })),
}));
