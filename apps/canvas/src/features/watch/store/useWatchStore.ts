import { create } from 'zustand';
import type { AlertSeverity, WatchFilters } from '../types/watch';

interface WatchState {
    filters: WatchFilters;
    selectedAlertId: string | null;

    // Actions
    setSearchQuery: (query: string) => void;
    toggleSeverity: (severity: AlertSeverity) => void;
    selectAlert: (id: string | null) => void;
    resetFilters: () => void;
}

const defaultFilters: WatchFilters = {
    query: '',
    severity: new Set(['critical', 'warning', 'info'])
};

export const useWatchStore = create<WatchState>((set) => ({
    filters: defaultFilters,
    selectedAlertId: null,

    setSearchQuery: (query) => set((state) => ({
        filters: { ...state.filters, query }
    })),

    toggleSeverity: (severity) => set((state) => {
        const newSeverity = new Set(state.filters.severity);
        if (newSeverity.has(severity)) {
            newSeverity.delete(severity);
        } else {
            newSeverity.add(severity);
        }
        return { filters: { ...state.filters, severity: newSeverity } };
    }),

    selectAlert: (id) => set({ selectedAlertId: id }),

    resetFilters: () => set({
        filters: {
            query: '',
            severity: new Set(['critical', 'warning', 'info']),
        },
        selectedAlertId: null
    })
}));
