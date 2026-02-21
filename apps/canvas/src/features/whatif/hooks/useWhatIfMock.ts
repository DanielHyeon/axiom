// src/features/whatif/hooks/useWhatIfMock.ts

import { useCallback, useRef } from 'react';
import { useWhatIfStore } from '../store/useWhatIfStore';
import type { SensitivityData } from '../types/whatif';


export function useWhatIfMock() {
    const {
        updateScenarioStatus,
        setScenarioResult
    } = useWhatIfStore();
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Helper to generate mock sensitivity based on current params
    const generateMockSensitivity = (params: Record<string, number>): SensitivityData[] => {
        return [
            {
                parameter: 'p_alloc',
                parameter_label: '비용배분율',
                base_value: params['p_alloc'] || 35,
                low_value: (params['p_alloc'] || 35) * 0.8,
                high_value: (params['p_alloc'] || 35) * 1.2,
                impact: 120, // arbitrary impact score
                low_pct_change: -15,
                high_pct_change: 18,
            },
            {
                parameter: 'p_util',
                parameter_label: '자원 활용률',
                base_value: params['p_util'] || 55,
                low_value: (params['p_util'] || 55) * 0.8,
                high_value: (params['p_util'] || 55) * 1.2,
                impact: 95,
                low_pct_change: -10,
                high_pct_change: 12,
            },
            {
                parameter: 'p_cost',
                parameter_label: '운영 비용 (억)',
                base_value: params['p_cost'] || 15,
                low_value: (params['p_cost'] || 15) * 0.8,
                high_value: (params['p_cost'] || 15) * 1.2,
                impact: 60,
                low_pct_change: 8, // cost down is usually good, but let's just make it simple
                high_pct_change: -5,
            },
            {
                parameter: 'p_dur',
                parameter_label: '프로젝트 기간 (년)',
                base_value: params['p_dur'] || 3,
                low_value: (params['p_dur'] || 3) * 0.8,
                high_value: (params['p_dur'] || 3) * 1.2,
                impact: 40,
                low_pct_change: 5,
                high_pct_change: -8,
            }
        ].sort((a, b) => b.impact - a.impact); // Tornado charts usually sort by impact
    };

    const runAnalysis = useCallback(async (scenarioId: string) => {
        const scenario = useWhatIfStore.getState().scenarios.find(s => s.id === scenarioId);
        if (!scenario) return;

        // 1. Start Computing (POST /compute -> 202 Accepted)
        updateScenarioStatus(scenarioId, 'COMPUTING');

        // 2. Mock Polling (GET /status)
        let polls = 0;

        if (pollingRef.current) clearInterval(pollingRef.current);

        pollingRef.current = setInterval(() => {
            polls++;

            // Simulate completion after ~3 polls (6 seconds)
            if (polls >= 3) {
                if (pollingRef.current) clearInterval(pollingRef.current);

                // 3. Mock Result and Sensitivity (GET /result, POST /sensitivity)
                const params = scenario.parameters;

                // Naive mock logic: more alloc & util = more savings
                const allocBoost = (params['p_alloc'] || 35) / 35;
                const utilBoost = (params['p_util'] || 55) / 55;

                const baseSavings = 250;
                const computedSavings = Math.round(baseSavings * (allocBoost * 0.6 + utilBoost * 0.4));
                const savingsChangePct = Math.round(((computedSavings - baseSavings) / baseSavings) * 100);

                setScenarioResult(
                    scenarioId,
                    {
                        totalSavings: computedSavings,
                        savingsChangePct,
                        satisfactionScore: Math.min(100, Math.round(40 * utilBoost)),
                        satisfactionChangePt: Math.round(40 * utilBoost) - 40,
                        durationYears: params['p_dur'] || 3,
                        durationChangePct: 0
                    },
                    generateMockSensitivity(params)
                );

                console.log("분석 완료: 시나리오 시뮬레이션 계산이 완료되었습니다.");
            }
        }, 2000); // Poll every 2 seconds

    }, [updateScenarioStatus, setScenarioResult]);

    // Cleanup polling on unmount
    useCallback(() => {
        return () => {
            if (pollingRef.current) clearInterval(pollingRef.current);
        }
    }, []);

    return {
        runAnalysis
    };
}
