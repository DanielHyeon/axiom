// src/features/olap/store/usePivotConfig.ts

import { create } from 'zustand';
import type { PivotConfig, Dimension, Measure, OlapFilter, DrilldownStep } from '../types/olap';

interface PivotConfigState extends PivotConfig {
    setCubeId: (id: string | null) => void;
    setRows: (rows: Dimension[]) => void;
    setColumns: (columns: Dimension[]) => void;
    setMeasures: (measures: Measure[]) => void;
    setFilters: (filters: OlapFilter[]) => void;
    setDrilldownPath: (path: DrilldownStep[]) => void;

    // Helpers for DnD actions
    addFieldToZone: (zone: 'rows' | 'columns' | 'measures' | 'filters', field: Dimension | Measure) => void;
    removeFieldFromZone: (zone: 'rows' | 'columns' | 'measures' | 'filters', fieldId: string) => void;
    reorderZone: (zone: 'rows' | 'columns' | 'measures' | 'filters', oldIndex: number, newIndex: number) => void;
    clearAll: () => void;
}

const initialState: PivotConfig = {
    cubeId: null,
    rows: [],
    columns: [],
    measures: [],
    filters: [],
    drilldownPath: [],
};

export const usePivotConfig = create<PivotConfigState>((set) => ({
    ...initialState,

    setCubeId: (id) => set({ cubeId: id, rows: [], columns: [], measures: [], filters: [], drilldownPath: [] }),
    setRows: (rows) => set({ rows, drilldownPath: [] }), // Reset drilldown when rows change
    setColumns: (columns) => set({ columns }),
    setMeasures: (measures) => set({ measures }),
    setFilters: (filters) => set({ filters }),
    setDrilldownPath: (drilldownPath) => set({ drilldownPath }),

    addFieldToZone: (zone, field) => set((state) => {
        const list = state[zone] as (Dimension | Measure)[];
        // Prevent duplicates
        if (!list.find((item) => item.id === field.id)) {
            return { [zone]: [...list, field] };
        }
        return state;
    }),

    removeFieldFromZone: (zone, fieldId) => set((state) => {
        const list = state[zone] as (Dimension | Measure)[];
        return { [zone]: list.filter((item) => item.id !== fieldId) };
    }),

    reorderZone: (zone, oldIndex, newIndex) => set((state) => {
        const list = [...(state[zone] as (Dimension | Measure)[])];
        const [removed] = list.splice(oldIndex, 1);
        list.splice(newIndex, 0, removed);
        return { [zone]: list };
    }),

    clearAll: () => set(initialState)
}));
