// src/features/olap/hooks/useOlapMock.ts

import { useState, useCallback } from 'react';
import type { PivotConfig, CubeDefinition } from '../types/olap';

// Mock Cube Definitions
export const MOCK_CUBES: CubeDefinition[] = [
    {
        id: 'cube-fin',
        name: '재무제표 분석',
        description: '기업의 분기별 재무 지표를 다차원으로 분석합니다.',
        dimensions: [
            { id: 'dim_period', name: '기간 (년/분기)', type: 'date' },
            { id: 'dim_company', name: '기업명', type: 'string' },
            { id: 'dim_sector', name: '산업군', type: 'string' },
            { id: 'dim_region', name: '지역', type: 'string' },
        ],
        measures: [
            { id: 'm_revenue', name: '매출액 (억)', aggregation: 'sum' },
            { id: 'm_profit', name: '영업이익 (억)', aggregation: 'sum' },
            { id: 'm_debt', name: '부채비율 (%)', aggregation: 'avg' },
        ]
    },
    {
        id: 'cube-hr',
        name: '인사/조직 비용 분석',
        description: '부서별 인건비 및 성과 지표를 분석합니다.',
        dimensions: [
            { id: 'dim_dept', name: '부서', type: 'string' },
            { id: 'dim_role', name: '직급', type: 'string' },
            { id: 'dim_status', name: '재직상태', type: 'string' },
        ],
        measures: [
            { id: 'm_salary', name: '급여합계 (천)', aggregation: 'sum' },
            { id: 'm_headcount', name: '인원수', aggregation: 'count' },
        ]
    }
];

export interface OlapQueryResult {
    headers: string[];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    data: any[][];
    executionTimeMs: number;
}

export function useOlapMock() {
    const [cubes] = useState<CubeDefinition[]>(MOCK_CUBES);
    const [isQuerying, setIsQuerying] = useState(false);
    const [queryResult, setQueryResult] = useState<OlapQueryResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const executeQuery = useCallback(async (config: PivotConfig) => {
        setIsQuerying(true);
        setError(null);

        try {
            // Simulate network delay for analytical engine
            await new Promise(res => setTimeout(res, 800));

            if (!config.cubeId) throw new Error("분석할 큐브를 선택하세요.");
            if (config.measures.length === 0) throw new Error("최소 1개 이상의 측정값을 배치해야 합니다.");
            if (config.rows.length === 0 && config.columns.length === 0) {
                throw new Error("분석할 행 또는 열 차원을 1개 이상 배치해 주세요.");
            }

            // Generate Mock Result based on configuration
            const headers = [
                ...config.rows.map(r => r.name),
                ...config.columns.map(c => c.name),
                ...config.measures.map(m => m.name)
            ];

            // Extremely naive mock data generator
            const generateRow = (index: number) => {
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                const rowData: any[] = [];
                // Rows mock
                config.rows.forEach(r => rowData.push(`값_${r.name}_${index}`));
                // Columns mock
                config.columns.forEach(c => rowData.push(`항목_${c.name}_${index % 3}`));
                // Measures mock
                config.measures.forEach(() => rowData.push(Math.floor(Math.random() * 10000)));
                return rowData;
            };

            const tableData = Array.from({ length: 15 }, (_, i) => generateRow(i));

            setQueryResult({
                headers,
                data: tableData,
                executionTimeMs: Math.floor(Math.random() * 500) + 200 // Mock 200~700ms
            });
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } catch (err: any) {
            setError(err.message || '쿼리 실행 중 오류가 발생했습니다.');
            setQueryResult(null);
        } finally {
            setIsQuerying(false);
        }
    }, []);

    return {
        cubes,
        isQuerying,
        queryResult,
        error,
        executeQuery
    };
}
