// src/pages/whatif/WhatIfPage.tsx

import { useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useWhatIfStore } from '@/features/whatif/store/useWhatIfStore';
import { useWhatIfVision } from '@/features/whatif/hooks/useWhatIfVision';
import type { ScenarioResult } from '@/features/whatif/types/whatif';
import { ScenarioPanel } from './components/ScenarioPanel';
import { ScenarioComparison } from './components/ScenarioComparison';
import { TornadoChart } from './components/TornadoChart';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingDown, TrendingUp, Clock, Activity, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();
 const { caseId } = useParams<{ caseId: string }>();
 const navigate = useNavigate();
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
 name: caseId ? t('whatifPage.mce4388fe') : t('whatifPage.m3dbc19b6'),
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
 <div className="flex h-[calc(100vh-4rem)] bg-background text-foreground overflow-hidden">

 {/* Left Sidebar: Parameter Sliders */}
 {activeScenarioId ? (
 <ScenarioPanel
 scenarioId={activeScenarioId}
 onRunAnalysis={caseId ? onRunAnalysisVision : undefined}
 />
 ) : (
 <div className="w-80 border-r border-border bg-popover p-4 flex items-center justify-center">
 <Loader2 className="animate-spin text-foreground0" />
 </div>
 )}

 {/* Main Content: Results & Charts */}
 <div className="flex-1 flex flex-col overflow-hidden relative">
 {/* Header */}
 <div className="h-14 border-b border-border bg-background px-6 flex items-center justify-between shrink-0">
 <div className="flex items-center gap-4">
 <h1 className="font-semibold flex items-center gap-2 text-lg">
 <span className="text-xl">✨</span> {t('whatifPage.wizardTitle')}
 </h1>
 <span className="text-sm px-2 py-0.5 rounded-full bg-indigo-900/40 text-indigo-300 border border-indigo-800">
 {activeScenario?.name}
 </span>
 </div>
 <div className="flex items-center gap-2">
 <Button variant="outline" size="sm" className="h-8" onClick={() => navigate(ROUTES.ANALYSIS.WHATIF_WIZARD)}>
 {t('whatifPage.m4895869c')}
 </Button>
 <Button variant="outline" size="sm" className="h-8" onClick={handleCompare}>
 {t('whatifPage.m916fd392')}
 </Button>
 </div>
 </div>

 {/* Body */}
 <div className="flex-1 overflow-y-auto p-6 relative">

 {isComputing && (
 <div className="absolute inset-0 bg-sidebar/60 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
 <div className="w-16 h-16 relative flex items-center justify-center mb-4">
 <div className="absolute inset-0 border-4 border-indigo-500/30 rounded-full"></div>
 <div className="absolute inset-0 border-4 border-indigo-500 rounded-full border-t-transparent animate-spin"></div>
 <Activity className="text-primary" size={24} />
 </div>
 <h3 className="text-lg font-semibold text-primary-foreground mb-2">{t('whatifPage.msg9974a85b')}</h3>
 <p className="text-sm text-muted-foreground max-w-sm text-center">
 {t('whatifPage.m2f8410f0')}
 </p>
 </div>
 )}

 {vision.compareResult && vision.compareResult.items.length > 0 && (
 <ScenarioComparison items={vision.compareResult.items} />
 )}

 {!hasResult && !isComputing && (
 <div className="h-full flex flex-col items-center justify-center text-foreground0">
 <Activity size={48} className="mb-4 opacity-20" />
 <p>{t('whatifPage.msg1fc6ab45')} <strong>{t('whatifPage.msg3bb64241')}</strong>{t('whatifPage.msg3630e7ab')}</p>
 </div>
 )}

 {hasResult && activeScenario.result && activeScenario.sensitivity && (
 <div className="animate-in fade-in duration-500 max-w-6xl mx-auto space-y-6">

 {/* Summary Cards */}
 <div className="grid grid-cols-3 gap-6">
 <Card className="bg-card border-border">
 <CardHeader className="pb-2 flex flex-row items-center justify-between">
 <CardTitle className="text-sm font-medium text-muted-foreground">{t('whatifPage.msg962c0c2f')}</CardTitle>
 <TrendingDown className="text-success" size={16} />
 </CardHeader>
 <CardContent>
 <div className="text-3xl font-bold text-primary-foreground mb-1">
 {activeScenario.result.totalSavings.toLocaleString()} <span className="text-lg text-foreground0 font-normal">{t('whatifExt.mockUnit.billion')}</span>
 </div>
 <p className="text-xs text-success flex items-center font-medium">
 {t('whatifPage.savingsChange', { pct: activeScenario.result.savingsChangePct })}
 </p>
 </CardContent>
 </Card>

 <Card className="bg-card border-border">
 <CardHeader className="pb-2 flex flex-row items-center justify-between">
 <CardTitle className="text-sm font-medium text-muted-foreground">{t('whatifPage.msg7f21f31b')}</CardTitle>
 <TrendingUp className="text-primary" size={16} />
 </CardHeader>
 <CardContent>
 <div className="text-3xl font-bold text-primary-foreground mb-1">
 {activeScenario.result.satisfactionScore} <span className="text-lg text-foreground0 font-normal">{t('whatifPage.msg17a7dad1')}</span>
 </div>
 <p className="text-xs text-primary flex items-center font-medium">
 {t('whatifPage.satisfactionChange', { pt: activeScenario.result.satisfactionChangePt })}
 </p>
 </CardContent>
 </Card>

 <Card className="bg-card border-border">
 <CardHeader className="pb-2 flex flex-row items-center justify-between">
 <CardTitle className="text-sm font-medium text-muted-foreground">{t('whatifPage.msg79e9810a')}</CardTitle>
 <Clock className="text-primary" size={16} />
 </CardHeader>
 <CardContent>
 <div className="text-3xl font-bold text-primary-foreground mb-1">
 {activeScenario.result.durationYears} <span className="text-lg text-foreground0 font-normal">{t('whatifExt.mockUnit.year')}</span>
 </div>
 <p className="text-xs text-foreground0 flex items-center">
 {t('whatifPage.m29ca1497')}
 </p>
 </CardContent>
 </Card>
 </div>

 {/* Tornado Chart */}
 <Card className="bg-card border-border">
 <CardContent className="pt-6">
 <TornadoChart
 data={activeScenario.sensitivity}
 baseValue={activeScenario.result.totalSavings}
 />
 </CardContent>
 </Card>

 {/* Data Grid Mock */}
 <div className="border border-border rounded-lg overflow-hidden flex bg-background/50">
 <div className="p-4 flex-1 border-r border-border">
 <div className="text-xs text-foreground0 uppercase tracking-widest font-semibold mb-2">Optimistic Model (A)</div>
 <div className="text-lg font-mono">{t('whatifPage.msga43a722c')}</div>
 <div className="text-xs text-muted-foreground mt-1">{t('whatifPage.msg01d93f70')}</div>
 </div>
 <div className="p-4 flex-1">
 <div className="text-xs text-foreground0 uppercase tracking-widest font-semibold mb-2">Pessimistic Model (B)</div>
 <div className="text-lg font-mono">{t('whatifPage.msg9f36a15e')}</div>
 <div className="text-xs text-muted-foreground mt-1">{t('whatifPage.msga358074f')}</div>
 </div>
 </div>

 </div>
 )}

 </div>
 </div>
 </div>
 );
}
