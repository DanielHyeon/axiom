// src/features/olap/types/olap.ts

/**
 * OLAP Data Types representing Cubes, Dimensions, and Measures.
 */

export interface Dimension {
    id: string;
    name: string;
    type: 'string' | 'date' | 'numeric';
}

export interface Measure {
    id: string;
    name: string;
    aggregation: 'sum' | 'count' | 'avg' | 'min' | 'max';
}

export interface OlapFilter {
    dimensionId: string;
    operator: 'eq' | 'neq' | 'in' | 'contains' | 'gt' | 'lt';
    value: string | number | string[] | number[];
}

export interface DrilldownStep {
    dimensionId: string;
    value: string;
}

export interface CubeDefinition {
    id: string;
    name: string;
    description: string;
    dimensions: Dimension[];
    measures: Measure[];
}

/**
 * Pivot Configuration managed by Zustand
 */
export interface PivotConfig {
    cubeId: string | null;
    rows: Dimension[];
    columns: Dimension[];
    measures: Measure[];
    filters: OlapFilter[];
    drilldownPath: DrilldownStep[];
}
