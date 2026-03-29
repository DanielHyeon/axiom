/**
 * WhatIfPage — What-if 시나리오 결과 페이지
 *
 * 좌측: 파라미터 슬라이더 (ScenarioPanel)
 * 우측: 결과 카드 + 토네이도 차트 + 시나리오 비교
 *
 * .pen 디자인 시스템 색상 적용:
 * - 배경: #FAFAFA, 카드: #FFFFFF, 보더: #E5E5E5
 * - 텍스트: #000000, 보조: #5E5E5E, 비활성: #999999
 * - 주요 액센트: #FF8400, 파랑: #3B82F6, 녹색: #22C55E, 빨강: #DC2626
 */
import { useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import { useWhatIfStore } from '@/features/whatif/store/useWhatIfStore';
import { useWhatIfVision } from '@/features/whatif/hooks/useWhatIfVision';
import type { ScenarioResult } from '@/features/whatif/types/whatif';
import { ScenarioPanel } from './components/ScenarioPanel';
import { ScenarioComparison } from './components/ScenarioComparison';
import { TornadoChart } from './components/TornadoChart';
import { TrendingDown, TrendingUp, Clock, Activity, Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

/** Vision API 결과 → 스토어 ScenarioResult 변환 */
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

  // Vision 시나리오를 스토어와 동기화
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
      const mockId = 'scen-1';
      setScenarios([{
        id: mockId,
        name: caseId ? t('whatifPage.mce4388fe') : t('whatifPage.m3dbc19b6'),
        status: 'DRAFT',
        parameters: {},
      }]);
      setActiveScenarioId(mockId);
    }
  }, [caseId, vision.scenarios, vision.loading, scenarios.length, setCaseId, setScenarios, setActiveScenarioId, activeScenarioId]);

  // 시나리오 비교
  const handleCompare = useCallback(() => {
    if (!caseId) return;
    const completed = scenarios.filter((s) => s.status === 'COMPLETED');
    const ids = completed.map((s) => s.id);
    if (ids.length >= 2) vision.fetchCompare(ids);
  }, [caseId, scenarios, vision.fetchCompare]);

  // Vision 분석 실행
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
    [vision.runCompute, updateScenarioStatus, setScenarioResult],
  );

  const activeScenario = scenarios.find((s) => s.id === activeScenarioId);
  const isComputing = activeScenario?.status === 'COMPUTING';
  const hasResult = activeScenario?.status === 'COMPLETED' && activeScenario.result;

  return (
    <div className="flex h-[calc(100vh-4rem)] bg-background text-foreground overflow-hidden">
      {/* 좌측: 파라미터 패널 */}
      {activeScenarioId ? (
        <ScenarioPanel
          scenarioId={activeScenarioId}
          onRunAnalysis={caseId ? onRunAnalysisVision : undefined}
        />
      ) : (
        <div className="w-80 border-r border-border bg-card p-4 flex items-center justify-center">
          <Loader2 className="animate-spin text-text-placeholder" />
        </div>
      )}

      {/* 우측: 결과 영역 */}
      <div className="flex-1 flex flex-col overflow-hidden relative">
        {/* 헤더 */}
        <div className="h-14 border-b border-border bg-card px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <h1 className="font-heading text-lg font-semibold text-foreground">
              What-if Wizard
            </h1>
            {activeScenario && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/30 font-medium">
                {activeScenario.name}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => navigate(ROUTES.ANALYSIS.WHATIF_WIZARD)}
              className="h-8 px-3 text-xs font-medium text-text-secondary border border-border rounded-lg hover:bg-muted transition-colors"
            >
              {t('whatifPage.m4895869c')}
            </button>
            <button
              type="button"
              onClick={handleCompare}
              className="h-8 px-3 text-xs font-medium text-text-secondary border border-border rounded-lg hover:bg-muted transition-colors"
            >
              {t('whatifPage.m916fd392')}
            </button>
          </div>
        </div>

        {/* 본문 */}
        <div className="flex-1 overflow-y-auto p-6 relative">
          {/* 분석 진행 중 오버레이 */}
          {isComputing && (
            <div className="absolute inset-0 bg-card/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
              <div className="w-16 h-16 relative flex items-center justify-center mb-4">
                <div className="absolute inset-0 border-4 border-primary/30 rounded-full" />
                <div className="absolute inset-0 border-4 border-primary rounded-full border-t-transparent animate-spin" />
                <Activity className="text-primary" size={24} />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">{t('whatifPage.msg9974a85b')}</h3>
              <p className="text-sm text-text-secondary max-w-sm text-center">
                {t('whatifPage.m2f8410f0')}
              </p>
            </div>
          )}

          {/* 비교 결과 */}
          {vision.compareResult && vision.compareResult.items.length > 0 && (
            <ScenarioComparison items={vision.compareResult.items} />
          )}

          {/* 빈 상태 */}
          {!hasResult && !isComputing && (
            <div className="h-full flex flex-col items-center justify-center text-text-placeholder">
              <Activity size={48} className="mb-4 opacity-20" />
              <p>
                {t('whatifPage.msg1fc6ab45')}{' '}
                <strong>{t('whatifPage.msg3bb64241')}</strong>
                {t('whatifPage.msg3630e7ab')}
              </p>
            </div>
          )}

          {/* 결과 카드 + 차트 */}
          {hasResult && activeScenario.result && activeScenario.sensitivity && (
            <div className="animate-in fade-in duration-500 max-w-6xl mx-auto space-y-6">
              {/* 요약 카드 3개 */}
              <div className="grid grid-cols-3 gap-6">
                {/* 비용 절감 카드 — 다크모드 대응 토큰 적용 */}
                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-medium text-text-secondary">{t('whatifPage.msg962c0c2f')}</span>
                    <TrendingDown className="text-accent-green" size={16} />
                  </div>
                  <div className="text-3xl font-bold text-foreground mb-1">
                    {activeScenario.result.totalSavings.toLocaleString()}{' '}
                    <span className="text-lg text-text-placeholder font-normal">{t('whatifExt.mockUnit.billion')}</span>
                  </div>
                  <p className="text-xs text-accent-green font-medium">
                    {t('whatifPage.savingsChange', { pct: activeScenario.result.savingsChangePct })}
                  </p>
                </div>

                {/* 만족도 카드 — 다크모드 대응 토큰 적용 */}
                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-medium text-text-secondary">{t('whatifPage.msg7f21f31b')}</span>
                    <TrendingUp className="text-accent-blue" size={16} />
                  </div>
                  <div className="text-3xl font-bold text-foreground mb-1">
                    {activeScenario.result.satisfactionScore}{' '}
                    <span className="text-lg text-text-placeholder font-normal">{t('whatifPage.msg17a7dad1')}</span>
                  </div>
                  <p className="text-xs text-accent-blue font-medium">
                    {t('whatifPage.satisfactionChange', { pt: activeScenario.result.satisfactionChangePt })}
                  </p>
                </div>

                {/* 기간 카드 — 다크모드 대응 토큰 적용 */}
                <div className="bg-card border border-border rounded-xl p-5">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-medium text-text-secondary">{t('whatifPage.msg79e9810a')}</span>
                    <Clock className="text-accent-blue" size={16} />
                  </div>
                  <div className="text-3xl font-bold text-foreground mb-1">
                    {activeScenario.result.durationYears}{' '}
                    <span className="text-lg text-text-placeholder font-normal">{t('whatifExt.mockUnit.year')}</span>
                  </div>
                  <p className="text-xs text-text-secondary">
                    {t('whatifPage.m29ca1497')}
                  </p>
                </div>
              </div>

              {/* 토네이도 차트 */}
              <div className="bg-card border border-border rounded-xl p-6">
                <TornadoChart
                  data={activeScenario.sensitivity}
                  baseValue={activeScenario.result.totalSavings}
                />
              </div>

              {/* 모델 비교 */}
              <div className="border border-border rounded-xl overflow-hidden flex bg-card">
                <div className="p-4 flex-1 border-r border-border">
                  <div className="text-[10px] text-text-secondary uppercase tracking-widest font-semibold mb-2">
                    Optimistic Model (A)
                  </div>
                  <div className="text-lg font-mono text-foreground">{t('whatifPage.msga43a722c')}</div>
                  <div className="text-xs text-text-placeholder mt-1">{t('whatifPage.msg01d93f70')}</div>
                </div>
                <div className="p-4 flex-1">
                  <div className="text-[10px] text-text-secondary uppercase tracking-widest font-semibold mb-2">
                    Pessimistic Model (B)
                  </div>
                  <div className="text-lg font-mono text-foreground">{t('whatifPage.msg9f36a15e')}</div>
                  <div className="text-xs text-text-placeholder mt-1">{t('whatifPage.msga358074f')}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
