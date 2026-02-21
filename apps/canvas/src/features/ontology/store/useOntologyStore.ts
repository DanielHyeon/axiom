import { create } from 'zustand';
import type { OntologyLayer, OntologyFilters } from '../types/ontology';

interface OntologyState {
    filters: OntologyFilters;
    selectedNodeId: string | null;
    hoveredNodeId: string | null;
    isTableMode: boolean;

    // Actions
    setSearchQuery: (query: string) => void;
    toggleLayer: (layer: OntologyLayer) => void;
    setDepth: (depth: number) => void;
    selectNode: (id: string | null) => void;
    setHoveredNode: (id: string | null) => void;
    toggleViewMode: () => void;
    resetFilters: () => void;
}

const defaultFilters: OntologyFilters = {
    query: '',
    layers: new Set(['kpi', 'measure', 'process', 'resource']),
    depth: 2
};

export const useOntologyStore = create<OntologyState>((set) => ({
    filters: defaultFilters,
    selectedNodeId: null,
    hoveredNodeId: null,
    isTableMode: false,

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
    toggleViewMode: () => set((state) => ({ isTableMode: !state.isTableMode })),

    resetFilters: () => set({
        filters: {
            query: '',
            layers: new Set(['kpi', 'measure', 'process', 'resource']),
            depth: 2
        },
        selectedNodeId: null
    })
}));
