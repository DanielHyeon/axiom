// src/features/whatif/types/whatif.ts

export type ScenarioStatus = 'DRAFT' | 'READY' | 'COMPUTING' | 'COMPLETED' | 'FAILED';

export interface ParameterConfig {
    id: string;
    name: string;
    min: number;
    max: number;
    step: number;
    unit: string;
    defaultValue: number;
}

export interface SensitivityData {
    parameter: string;
    parameter_label: string;
    base_value: number;
    high_value: number;
    low_value: number;
    impact: number;
    high_pct_change: number;
    low_pct_change: number;
}

export interface ScenarioResult {
    totalSavings: number;
    savingsChangePct: number;
    satisfactionScore: number;
    satisfactionChangePt: number;
    durationYears: number;
    durationChangePct: number;
}

export interface Scenario {
    id: string;
    name: string;
    status: ScenarioStatus;
    parameters: Record<string, number>;
    result?: ScenarioResult;
    sensitivity?: SensitivityData[];
}
