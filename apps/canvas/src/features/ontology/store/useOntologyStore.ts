import { create } from 'zustand';
import type { OntologyLayer, OntologyFilters, ViewMode } from '../types/ontology';

interface OntologyState {
    caseId: string | null;
    filters: OntologyFilters;
    selectedNodeId: string | null;
    hoveredNodeId: string | null;
    viewMode: ViewMode;

    // Actions
    setCaseId: (id: string | null) => void;
    setSearchQuery: (query: string) => void;
    toggleLayer: (layer: OntologyLayer) => void;
    setDepth: (depth: number) => void;
    selectNode: (id: string | null) => void;
    setHoveredNode: (id: string | null) => void;
    setViewMode: (mode: ViewMode) => void;
    resetFilters: () => void;
}

const defaultFilters: OntologyFilters = {
    query: '',
    layers: new Set(['kpi', 'measure', 'process', 'resource']),
    depth: 2
};

export const useOntologyStore = create<OntologyState>((set) => ({
    caseId: null,
    filters: defaultFilters,
    selectedNodeId: null,
    hoveredNodeId: null,
    viewMode: 'graph',

    setCaseId: (id) => set({ caseId: id }),
    setSearchQuery: (query) => set((state) => ({
        filters: { ...state.filters, query }
    })),

    toggleLayer: (layer) => set((state) => {
        const newLayers = new Set(state.filters.layers);
        if (newLayers.has(layer)) {
            newLayers.delete(layer);
        } else {
            newLayers.add(layer);
        }
        return { filters: { ...state.filters, layers: newLayers } };
    }),

    setDepth: (depth) => set((state) => ({
        filters: { ...state.filters, depth }
    })),

    selectNode: (id) => set({ selectedNodeId: id }),
    setHoveredNode: (id) => set({ hoveredNodeId: id }),
    setViewMode: (mode) => set({ viewMode: mode }),

    resetFilters: () => set({
        filters: {
            query: '',
            layers: new Set(['kpi', 'measure', 'process', 'resource']),
            depth: 2
        },
        selectedNodeId: null,
        viewMode: 'graph',
    })
}));
