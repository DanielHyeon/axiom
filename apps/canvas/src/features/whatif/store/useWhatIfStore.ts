// src/features/whatif/store/useWhatIfStore.ts

import { create } from 'zustand';
import type { ParameterConfig, Scenario } from '../types/whatif';

interface WhatIfState {
    caseId: string | null;
    scenarios: Scenario[];
    activeScenarioId: string | null;
    parameters: ParameterConfig[];

    setCaseId: (id: string) => void;
    setScenarios: (scenarios: Scenario[]) => void;
    setActiveScenarioId: (id: string) => void;

    updateParameter: (scenarioId: string, paramId: string, value: number) => void;
    updateScenarioStatus: (scenarioId: string, status: Scenario['status']) => void;
    setScenarioResult: (scenarioId: string, result: Scenario['result'], sensitivity: Scenario['sensitivity']) => void;
}

export const useWhatIfStore = create<WhatIfState>((set) => ({
    caseId: null,
    scenarios: [],
    activeScenarioId: null,

    // These would typically come from an API for the specific case type
    parameters: [
        { id: 'p_alloc', name: '비용배분율', min: 0, max: 100, step: 1, unit: '%', defaultValue: 35 },
        { id: 'p_util', name: '자원 활용률', min: 0, max: 100, step: 1, unit: '%', defaultValue: 55 },
        { id: 'p_cost', name: '운영 비용', min: 0, max: 200, step: 5, unit: '억원', defaultValue: 15 },
        { id: 'p_dur', name: '프로젝트 기간', min: 1, max: 10, step: 0.5, unit: '년', defaultValue: 3 },
    ],

    setCaseId: (id) => set({ caseId: id }),
    setScenarios: (scenarios) => set({ scenarios }),
    setActiveScenarioId: (id) => set({ activeScenarioId: id }),

    updateParameter: (scenarioId, paramId, value) => set((state) => ({
        scenarios: state.scenarios.map(s =>
            s.id === scenarioId
                ? { ...s, parameters: { ...s.parameters, [paramId]: value }, status: 'DRAFT' }
                : s
        )
    })),

    updateScenarioStatus: (scenarioId, status) => set((state) => ({
        scenarios: state.scenarios.map(s =>
            s.id === scenarioId ? { ...s, status } : s
        )
    })),

    setScenarioResult: (scenarioId, result, sensitivity) => set((state) => ({
        scenarios: state.scenarios.map(s =>
            s.id === scenarioId
                ? { ...s, status: 'COMPLETED', result, sensitivity }
                : s
        )
    })),
}));
