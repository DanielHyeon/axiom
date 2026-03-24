/**
 * Step 5: 결과 비교
 *
 * - KPI 델타 요약 카드 (초록/빨간색으로 양/음 표시)
 * - Recharts 바 차트로 KPI 변화량 시각화
 * - 이벤트 타임라인 (Event Fork 모드용)
 * - 시나리오 비교 테이블
 * - 시뮬레이션 실행 버튼
 */
import { useCallback, useMemo } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  ArrowDown,
  ArrowUp,
  Loader2,
  Minus,
  Play,
  TrendingDown,
  TrendingUp,
  Clock,
  BarChart3,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { useWhatIfWizard } from '../hooks/useWhatIfWizard';
import { KPIDeltaChart } from './KPIDeltaChart';
import { ScenarioComparisonTable } from './ScenarioComparisonTable';
import type { KpiDeltaSummary, ForkEvent } from '../types/whatifWizard.types';

/** 개별 KPI 델타 요약 카드 */
function KpiDeltaCard({ summary }: { summary: KpiDeltaSummary }) {
  const isPositive = summary.impact === 'positive';
  const isNegative = summary.impact === 'negative';

  return (
    <div
      className={cn(
        'p-3 rounded-lg border transition-colors',
        isPositive && 'bg-emerald-500/5 border-emerald-500/30',
        isNegative && 'bg-red-500/5 border-red-500/30',
        !isPositive && !isNegative && 'bg-muted/20 border-border',
      )}
    >
      {/* KPI 이름 */}
      <p className="text-xs text-muted-foreground mb-1 truncate">{summary.name}</p>

      {/* 값 + 아이콘 */}
      <div className="flex items-center justify-between">
        <span className="text-lg font-bold font-mono">{summary.result.toFixed(1)}</span>
        {isPositive && <TrendingUp className="w-4 h-4 text-emerald-400" />}
        {isNegative && <TrendingDown className="w-4 h-4 text-red-400" />}
        {!isPositive && !isNegative && <Minus className="w-4 h-4 text-muted-foreground" />}
      </div>

      {/* 델타 */}
      <div className="flex items-center gap-1 mt-1">
        {summary.delta > 0 ? (
          <ArrowUp className="w-3 h-3 text-emerald-400" />
        ) : summary.delta < 0 ? (
          <ArrowDown className="w-3 h-3 text-red-400" />
        ) : null}
        <span
          className={cn(
            'text-xs font-mono',
            isPositive && 'text-emerald-400',
            isNegative && 'text-red-400',
            !isPositive && !isNegative && 'text-muted-foreground',
          )}
        >
          {summary.delta > 0 ? '+' : ''}
          {summary.delta.toFixed(2)} ({summary.pctChange > 0 ? '+' : ''}
          {summary.pctChange.toFixed(1)}%)
        </span>
      </div>

      {/* 베이스라인 */}
      <p className="text-[10px] text-muted-foreground mt-1">
        기준: {summary.baseline.toFixed(2)}
      </p>
    </div>
  );
}

/** 이벤트 타임라인 항목 */
function EventTimelineItem({ event }: { event: ForkEvent }) {
  return (
    <div className="flex gap-3 py-2">
      {/* 타임라인 도트 */}
      <div className="flex flex-col items-center">
        <div className="w-2 h-2 rounded-full bg-primary shrink-0 mt-1.5" />
        <div className="w-px flex-1 bg-border" />
      </div>

      {/* 이벤트 내용 */}
      <div className="flex-1 pb-3">
        <div className="flex items-center gap-2 mb-0.5">
          <Badge variant="outline" className="text-[10px]">
            {event.type}
          </Badge>
          <span className="text-[10px] text-muted-foreground">
            {new Date(event.timestamp).toLocaleString('ko-KR')}
          </span>
        </div>
        <p className="text-xs">{event.description}</p>
      </div>
    </div>
  );
}

export function Step5ResultCompare() {
  const { t } = useTranslation();
  const {
    simulationMode,
    scenarioName,
    forkResults,
    comparisonResult,
    branches,
    caseId,
  } = useWhatIfWizardStore();

  const {
    isSimulating,
    isComparing,
    error,
    kpiDeltaSummaries,
    runDagSimulation,
    runEventForkSimulation,
    runComparison,
  } = useWhatIfWizard();

  // 시뮬레이션 실행 — 스토어의 caseId 사용
  const handleRun = useCallback(async () => {
    if (simulationMode === 'dag') {
      await runDagSimulation(caseId);
    } else {
      await runEventForkSimulation(caseId);
    }
  }, [simulationMode, runDagSimulation, runEventForkSimulation, caseId]);

  // 비교 실행
  const handleCompare = useCallback(async () => {
    await runComparison(caseId);
  }, [runComparison, caseId]);

  // 가장 최근 결과의 이벤트 타임라인
  const latestEvents = useMemo(() => {
    if (forkResults.length === 0) return [];
    return forkResults[forkResults.length - 1].events;
  }, [forkResults]);

  const hasResults = forkResults.length > 0;
  const completedBranches = branches.filter((b) => b.status === 'completed');

  return (
    <div className="space-y-6 max-w-5xl">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-primary" />
            {t('whatifWizard.step5.title', '결과 비교')}
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            {t(
              'whatifWizard.step5.description',
              '시뮬레이션 결과를 확인하고 시나리오를 비교합니다.',
            )}
          </p>
        </div>

        {/* 시뮬레이션 모드 표시 */}
        <Badge variant="outline" className="text-xs">
          {simulationMode === 'dag' ? 'DAG 전파' : 'Event Fork'}
        </Badge>
      </div>

      {/* 시뮬레이션 실행 버튼 */}
      <Card>
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">
                {scenarioName || '시뮬레이션'}
              </p>
              <p className="text-xs text-muted-foreground">
                {simulationMode === 'dag'
                  ? '인과 DAG를 통해 개입 효과를 전파합니다.'
                  : '이벤트 스트림을 포크하여 시뮬레이션합니다.'}
              </p>
            </div>
            <Button onClick={handleRun} disabled={isSimulating}>
              {isSimulating ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  실행 중...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  시뮬레이션 실행
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 에러 표시 */}
      {error && (
        <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* 결과 영역 */}
      {hasResults && (
        <>
          {/* KPI 델타 요약 카드 */}
          {kpiDeltaSummaries.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">KPI 변화 요약</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {kpiDeltaSummaries.map((summary) => (
                    <KpiDeltaCard key={summary.name} summary={summary} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* KPI 델타 바 차트 */}
          <KPIDeltaChart data={kpiDeltaSummaries} title="KPI 변화량 (%)"/>

          {/* Event Fork 모드: 이벤트 타임라인 */}
          {simulationMode === 'event-fork' && latestEvents.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Clock className="w-4 h-4" />
                  이벤트 타임라인
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-64 overflow-y-auto">
                  {latestEvents.map((event) => (
                    <EventTimelineItem key={event.id} event={event} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* 시나리오 비교 */}
          {completedBranches.length >= 2 && (
            <div className="space-y-3">
              <Button
                variant="outline"
                onClick={handleCompare}
                disabled={isComparing}
                className="w-full"
              >
                {isComparing ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    비교 중...
                  </>
                ) : (
                  `${completedBranches.length}개 시나리오 비교`
                )}
              </Button>

              {comparisonResult && (
                <ScenarioComparisonTable data={comparisonResult} />
              )}
            </div>
          )}
        </>
      )}

      {/* 결과 없음 */}
      {!hasResults && !isSimulating && (
        <div className="flex flex-col items-center py-12 text-center">
          <BarChart3 className="w-10 h-10 text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">
            시뮬레이션을 실행하면 결과가 여기에 표시됩니다.
          </p>
        </div>
      )}
    </div>
  );
}
