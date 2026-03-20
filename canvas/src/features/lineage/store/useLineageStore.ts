/**
 * 리니지 UI 상태 관리 (Zustand)
 * 선택된 노드, 필터, 검색어 등 클라이언트 사이드 상태
 */

import { create } from 'zustand';
import type {
  LineageNode,
  LineageEdge,
  LineageDirection,
  LineageNodeType,
  LineageFilters,
  LineageStats,
} from '../types/lineage';

interface LineageState {
  // --- 그래프 데이터 ---
  nodes: LineageNode[];
  edges: LineageEdge[];
  stats: LineageStats | null;

  // --- UI 상태 ---
  selectedNodeId: string | null;
  selectedNode: LineageNode | null;
  filters: LineageFilters;
  isDetailOpen: boolean;

  // --- Actions ---
  setGraphData: (nodes: LineageNode[], edges: LineageEdge[]) => void;
  setStats: (stats: LineageStats) => void;
  selectNode: (node: LineageNode | null) => void;
  setDirection: (direction: LineageDirection) => void;
  setDepth: (depth: number) => void;
  setSearchQuery: (query: string) => void;
  toggleNodeType: (type: LineageNodeType) => void;
  closeDetail: () => void;
  resetFilters: () => void;
}

/** 기본 필터 — 모든 노드 타입 활성화, 깊이 3, 양방향 */
const defaultFilters: LineageFilters = {
  direction: 'both',
  depth: 3,
  nodeTypes: new Set<LineageNodeType>([
    'source',
    'table',
    'column',
    'view',
    'transform',
    'report',
  ]),
  searchQuery: '',
};

export const useLineageStore = create<LineageState>((set) => ({
  // 초기 상태
  nodes: [],
  edges: [],
  stats: null,
  selectedNodeId: null,
  selectedNode: null,
  filters: defaultFilters,
  isDetailOpen: false,

  // --- Actions ---

  setGraphData: (nodes, edges) => set({ nodes, edges }),

  setStats: (stats) => set({ stats }),

  selectNode: (node) =>
    set({
      selectedNodeId: node?.id ?? null,
      selectedNode: node,
      isDetailOpen: node !== null,
    }),

  setDirection: (direction) =>
    set((state) => ({
      filters: { ...state.filters, direction },
    })),

  setDepth: (depth) =>
    set((state) => ({
      filters: { ...state.filters, depth },
    })),

  setSearchQuery: (searchQuery) =>
    set((state) => ({
      filters: { ...state.filters, searchQuery },
    })),

  toggleNodeType: (type) =>
    set((state) => {
      const next = new Set(state.filters.nodeTypes);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return { filters: { ...state.filters, nodeTypes: next } };
    }),

  closeDetail: () =>
    set({ isDetailOpen: false, selectedNodeId: null, selectedNode: null }),

  resetFilters: () =>
    set({
      filters: {
        direction: 'both',
        depth: 3,
        nodeTypes: new Set<LineageNodeType>([
          'source',
          'table',
          'column',
          'view',
          'transform',
          'report',
        ]),
        searchQuery: '',
      },
      selectedNodeId: null,
      selectedNode: null,
      isDetailOpen: false,
    }),
}));
