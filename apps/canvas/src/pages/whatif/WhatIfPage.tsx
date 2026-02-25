// src/pages/whatif/WhatIfPage.tsx

import { useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { useWhatIfStore } from '@/features/whatif/store/useWhatIfStore';
import { useWhatIfVision } from '@/features/whatif/hooks/useWhatIfVision';
import type { ScenarioResult } from '@/features/whatif/types/whatif';
import { ScenarioPanel } from './components/ScenarioPanel';
import { ScenarioComparison } from './components/ScenarioComparison';
import { TornadoChart } from './components/TornadoChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingDown, TrendingUp, Clock, Activity, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

function mapVisionResultToStore(visionResult: Record<string, unknown> | undefined): ScenarioResult {
  const summary = (visionResult?.summary as Record<string, unknown>) ?? {};
  const npv = Number(summary.npv_at_wacc) || 0;
  const score = Number(visionResult?.feasibility_score) || 0;
  return {
    totalSavings: npv,
    savingsChangePct: 0,
    satisfactionScore: score,
    satisfactionChangePt: 0,
    durationYears: 0,
    durationChangePct: 0,
  };
}

export function WhatIfPage() {
    const { caseId } = useParams<{ caseId: string }>();
    const {
        setCaseId,
        scenarios,
        activeScenarioId,
        setActiveScenarioId,
        setScenarios,
        updateScenarioStatus,
        setScenarioResult,
    } = useWhatIfStore();
    const vision = useWhatIfVision(caseId ?? undefined);

    // Sync Vision scenarios to store when caseId and Vision data load
    useEffect(() => {
        if (caseId) setCaseId(caseId);
        if (caseId && vision.scenarios.length > 0) {
            const mapped = vision.scenarios.map((v) => ({
                id: v.id,
                name: v.scenario_name,
                status: v.status as 'DRAFT' | 'READY' | 'COMPUTING' | 'COMPLETED' | 'FAILED',
                parameters: (v.parameters as Record<string, number>) ?? {},
                result: v.result ? mapVisionResultToStore(v.result) : undefined,
                sensitivity: [],
            }));
            setScenarios(mapped);
            if (!activeScenarioId && mapped[0]) setActiveScenarioId(mapped[0].id);
        } else if (!vision.loading && scenarios.length === 0) {
            // No Vision scenarios available (or no caseId) — create a default draft
            const mockId = 'scen-1';
            setScenarios([{
                id: mockId,
                name: caseId ? '새 What-if 시나리오' : '기본 물류 최적화 시나리오',
                status: 'DRAFT',
                parameters: {}
            }]);
            setActiveScenarioId(mockId);
        }
    }, [caseId, vision.scenarios, vision.loading, scenarios.length, setCaseId, setScenarios, setActiveScenarioId, activeScenarioId]);

    const handleCompare = useCallback(() => {
        if (!caseId) return;
        const completed = scenarios.filter((s) => s.status === 'COMPLETED');
        const ids = completed.map((s) => s.id);
        if (ids.length >= 2) vision.fetchCompare(ids);
    }, [caseId, scenarios, vision.fetchCompare]);

    const onRunAnalysisVision = useCallback(
        async (scenarioId: string) => {
            updateScenarioStatus(scenarioId, 'COMPUTING');
            const result = await vision.runCompute(scenarioId);
            if (result) {
                setScenarioResult(scenarioId, mapVisionResultToStore(result), []);
            } else {
                updateScenarioStatus(scenarioId, 'FAILED');
            }
        },
        [vision.runCompute, updateScenarioStatus, setScenarioResult]
    );

    const activeScenario = scenarios.find(s => s.id === activeScenarioId);
    const isComputing = activeScenario?.status === 'COMPUTING';
    const hasResult = activeScenario?.status === 'COMPLETED' && activeScenario.result;

    return (
        <div className="flex h-[calc(100vh-4rem)] bg-neutral-950 text-neutral-100 overflow-hidden">

            {/* Left Sidebar: Parameter Sliders */}
            {activeScenarioId ? (
                <ScenarioPanel
                    scenarioId={activeScenarioId}
                    onRunAnalysis={caseId ? onRunAnalysisVision : undefined}
                />
            ) : (
                <div className="w-80 border-r border-neutral-800 bg-[#161616] p-4 flex items-center justify-center">
                    <Loader2 className="animate-spin text-neutral-500" />
                </div>
            )}

            {/* Main Content: Results & Charts */}
            <div className="flex-1 flex flex-col overflow-hidden relative">
                {/* Header */}
                <div className="h-14 border-b border-neutral-800 bg-[#121212] px-6 flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-4">
                        <h1 className="font-semibold flex items-center gap-2 text-lg">
                            <span className="text-xl">✨</span> What-if 시나리오 빌더
                        </h1>
                        <span className="text-sm px-2 py-0.5 rounded-full bg-indigo-900/40 text-indigo-300 border border-indigo-800">
                            {activeScenario?.name}
                        </span>
                    </div>
                    <div>
                        <Button variant="outline" size="sm" className="h-8" onClick={handleCompare}>
                            시나리오 비교 (Compare)
                        </Button>
                    </div>
                </div>

                {/* Body */}
                <div className="flex-1 overflow-y-auto p-6 relative">

                    {isComputing && (
                        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
                            <div className="w-16 h-16 relative flex items-center justify-center mb-4">
                                <div className="absolute inset-0 border-4 border-indigo-500/30 rounded-full"></div>
                                <div className="absolute inset-0 border-4 border-indigo-500 rounded-full border-t-transparent animate-spin"></div>
                                <Activity className="text-indigo-400" size={24} />
                            </div>
                            <h3 className="text-lg font-semibold text-white mb-2">시나리오 계산 중...</h3>
                            <p className="text-sm text-neutral-400 max-w-sm text-center">
                                수십만 건의 경로 데이터를 기반으로 변경된 매개변수에 대한 결괏값을 시뮬레이션하고 있습니다.
                            </p>
                        </div>
                    )}

                    {vision.compareResult && vision.compareResult.items.length > 0 && (
                        <ScenarioComparison items={vision.compareResult.items} />
                    )}

                    {!hasResult && !isComputing && (
                        <div className="h-full flex flex-col items-center justify-center text-neutral-500">
                            <Activity size={48} className="mb-4 opacity-20" />
                            <p>좌측 패널에서 슬라이더를 조정하고 <strong>"분석 실행"</strong>을 클릭하세요.</p>
                        </div>
                    )}

                    {hasResult && activeScenario.result && activeScenario.sensitivity && (
                        <div className="animate-in fade-in duration-500 max-w-6xl mx-auto space-y-6">

                            {/* Summary Cards */}
                            <div className="grid grid-cols-3 gap-6">
                                <Card className="bg-neutral-900 border-neutral-800">
                                    <CardHeader className="pb-2 flex flex-row items-center justify-between">
                                        <CardTitle className="text-sm font-medium text-neutral-400">예상 총 비용절감액</CardTitle>
                                        <TrendingDown className="text-emerald-500" size={16} />
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-3xl font-bold text-white mb-1">
                                            {activeScenario.result.totalSavings.toLocaleString()} <span className="text-lg text-neutral-500 font-normal">억원</span>
                                        </div>
                                        <p className="text-xs text-emerald-400 flex items-center font-medium">
                                            기준 대비 ▲ {activeScenario.result.savingsChangePct}%
                                        </p>
                                    </CardContent>
                                </Card>

                                <Card className="bg-neutral-900 border-neutral-800">
                                    <CardHeader className="pb-2 flex flex-row items-center justify-between">
                                        <CardTitle className="text-sm font-medium text-neutral-400">이해관계자 만족도 향상</CardTitle>
                                        <TrendingUp className="text-blue-500" size={16} />
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-3xl font-bold text-white mb-1">
                                            {activeScenario.result.satisfactionScore} <span className="text-lg text-neutral-500 font-normal">점</span>
                                        </div>
                                        <p className="text-xs text-blue-400 flex items-center font-medium">
                                            기준점(40점) 대비 ▲ {activeScenario.result.satisfactionChangePt}p
                                        </p>
                                    </CardContent>
                                </Card>

                                <Card className="bg-neutral-900 border-neutral-800">
                                    <CardHeader className="pb-2 flex flex-row items-center justify-between">
                                        <CardTitle className="text-sm font-medium text-neutral-400">소요 기간</CardTitle>
                                        <Clock className="text-indigo-500" size={16} />
                                    </CardHeader>
                                    <CardContent>
                                        <div className="text-3xl font-bold text-white mb-1">
                                            {activeScenario.result.durationYears} <span className="text-lg text-neutral-500 font-normal">년</span>
                                        </div>
                                        <p className="text-xs text-neutral-500 flex items-center">
                                            초기 계획과 동일함
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Tornado Chart */}
                            <Card className="bg-neutral-900 border-neutral-800">
                                <CardContent className="pt-6">
                                    <TornadoChart
                                        data={activeScenario.sensitivity}
                                        baseValue={activeScenario.result.totalSavings}
                                    />
                                </CardContent>
                            </Card>

                            {/* Data Grid Mock */}
                            <div className="border border-neutral-800 rounded-lg overflow-hidden flex bg-neutral-950/50">
                                <div className="p-4 flex-1 border-r border-neutral-800">
                                    <div className="text-xs text-neutral-500 uppercase tracking-widest font-semibold mb-2">Optimistic Model (A)</div>
                                    <div className="text-lg font-mono">2,140 억원 절감 예측</div>
                                    <div className="text-xs text-neutral-600 mt-1">배분율 42%, 활용률 65%</div>
                                </div>
                                <div className="p-4 flex-1">
                                    <div className="text-xs text-neutral-500 uppercase tracking-widest font-semibold mb-2">Pessimistic Model (B)</div>
                                    <div className="text-lg font-mono">980 억원 절감 예측</div>
                                    <div className="text-xs text-neutral-600 mt-1">배분율 20%, 활용률 40%</div>
                                </div>
                            </div>

                        </div>
                    )}

                </div>
            </div>
        </div>
    );
}
