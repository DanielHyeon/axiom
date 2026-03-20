/**
 * Step 5: 시뮬레이션 실행
 *
 * - 스냅샷 데이터 로드 (베이스라인)
 * - 파라미터 슬라이더로 개입 값 설정
 * - Vision DAG simulate API 호출
 * - SimulationResultPanel + ParameterSweepChart로 결과 표시
 */
import { useEffect, useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Slider } from '@/components/ui/slider';
import { Badge } from '@/components/ui/badge';
import { Loader2, Play, RotateCcw, Zap } from 'lucide-react';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { useWhatIfWizard } from '../hooks/useWhatIfWizard';
import { SimulationResultPanel } from './SimulationResultPanel';
import { ParameterSweepChart } from './ParameterSweepChart';

export function StepSimulation() {
  const {
    snapshotData,
    simulationResults,
  } = useWhatIfWizardStore();

  const {
    isSimulating,
    isLoadingSnapshot,
    error,
    loadSnapshot,
    runSimulation,
  } = useWhatIfWizard();

  // 편집 가능한 스냅샷 값 (로컬 상태)
  const [editableValues, setEditableValues] = useState<Record<string, number>>({});
  const [originalValues, setOriginalValues] = useState<Record<string, number>>({});

  // 스냅샷 로드
  useEffect(() => {
    if (!snapshotData) {
      loadSnapshot();
    }
  }, [snapshotData, loadSnapshot]);

  // 스냅샷이 로드되면 편집 가능 값 초기화
  useEffect(() => {
    if (snapshotData?.snapshot) {
      setEditableValues({ ...snapshotData.snapshot });
      setOriginalValues({ ...snapshotData.snapshot });
    }
  }, [snapshotData]);

  // 값 변경 핸들러
  const handleValueChange = useCallback((key: string, value: number) => {
    setEditableValues((prev) => ({ ...prev, [key]: value }));
  }, []);

  // 초기화
  const handleReset = useCallback(() => {
    setEditableValues({ ...originalValues });
  }, [originalValues]);

  // 변경된 변수 추적
  const changedVars = Object.entries(editableValues)
    .filter(([key, val]) => {
      const orig = originalValues[key];
      return orig !== undefined && Math.abs(val - orig) > 1e-6;
    })
    .map(([key, current]) => ({
      key,
      original: originalValues[key],
      current,
    }));

  // 시뮬레이션 실행
  const handleRunSimulation = useCallback(async () => {
    if (changedVars.length === 0) return;

    const interventions = changedVars.map((cv) => {
      const [nodeId, field] = cv.key.includes('::')
        ? cv.key.split('::')
        : [cv.key, cv.key];
      return {
        nodeId,
        field,
        value: cv.current,
        description: `${field}: ${cv.original.toFixed(2)} -> ${cv.current.toFixed(2)}`,
      };
    });

    await runSimulation(interventions);
  }, [changedVars, runSimulation]);

  // 필드 라벨 생성
  const fieldLabel = (key: string): string => {
    const field = key.split('::').pop() ?? key;
    return snapshotData?.fieldDescriptions?.[field] ?? field;
  };

  // 최신 시뮬레이션 결과
  const latestResult =
    simulationResults.length > 0
      ? simulationResults[simulationResults.length - 1]
      : null;

  return (
    <div className="space-y-6 max-w-5xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Zap className="w-5 h-5 text-primary" />
          시뮬레이션 실행
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          변수 값을 변경하여 모델 체인을 통한 연쇄 영향을 시뮬레이션합니다.
        </p>
      </div>

      {/* 스냅샷 로딩 */}
      {isLoadingSnapshot && (
        <div className="flex flex-col items-center py-12 gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">스냅샷 로드 중...</p>
        </div>
      )}

      {/* 에러 */}
      {error && (
        <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* 파라미터 슬라이더 카드 */}
      {snapshotData && !isLoadingSnapshot && (
        <>
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm">
                  스냅샷 파라미터
                  {snapshotData.date && (
                    <Badge variant="outline" className="ml-2 text-xs">
                      {snapshotData.date}
                    </Badge>
                  )}
                </CardTitle>
                {changedVars.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleReset}
                    className="h-7 text-xs"
                  >
                    <RotateCcw className="w-3 h-3 mr-1" />
                    초기화
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {/* 노드별 그룹 */}
              {snapshotData.snapshotByNode &&
                Object.entries(snapshotData.snapshotByNode).map(
                  ([nodeId, nodeInfo]) => (
                    <div
                      key={nodeId}
                      className="mb-4 last:mb-0 p-3 rounded-lg bg-muted/20 border border-border"
                    >
                      <h6 className="text-xs font-semibold mb-3 text-muted-foreground uppercase tracking-wider">
                        {nodeInfo.nodeName}
                      </h6>
                      <div className="space-y-4">
                        {Object.entries(nodeInfo.fields).map(
                          ([fieldName, _value]) => {
                            const fullKey = `${nodeId}::${fieldName}`;
                            const current = editableValues[fullKey] ?? 0;
                            const original = originalValues[fullKey] ?? 0;
                            const isChanged = Math.abs(current - original) > 1e-6;
                            // 슬라이더 범위: 원래 값의 0~200%
                            const sliderMin = original * 0;
                            const sliderMax = original === 0 ? 100 : original * 2;
                            const step = original === 0 ? 1 : original * 0.01;

                            return (
                              <div key={fullKey} className="space-y-1.5">
                                <div className="flex items-center justify-between">
                                  <Label className="text-xs">
                                    {fieldLabel(fullKey)}
                                  </Label>
                                  <div className="flex items-center gap-2">
                                    <Input
                                      type="number"
                                      step="any"
                                      value={current}
                                      onChange={(e) =>
                                        handleValueChange(
                                          fullKey,
                                          parseFloat(e.target.value) || 0
                                        )
                                      }
                                      className={`w-24 h-7 text-xs text-right font-mono ${
                                        isChanged
                                          ? 'border-primary text-primary'
                                          : ''
                                      }`}
                                    />
                                    {isChanged && (
                                      <span className="text-[10px] text-amber-400">
                                        ({original.toFixed(1)})
                                      </span>
                                    )}
                                  </div>
                                </div>
                                <Slider
                                  value={[current]}
                                  min={sliderMin}
                                  max={sliderMax}
                                  step={step}
                                  onValueChange={([v]) =>
                                    handleValueChange(fullKey, v)
                                  }
                                  className="w-full"
                                />
                              </div>
                            );
                          }
                        )}
                      </div>
                    </div>
                  )
                )}

              {/* 변경 요약 + 실행 버튼 */}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                <div className="flex items-center gap-2 flex-wrap">
                  {changedVars.length > 0 ? (
                    <>
                      <Badge variant="secondary" className="text-xs">
                        {changedVars.length}개 변수 변경됨
                      </Badge>
                      {changedVars.slice(0, 3).map((cv) => (
                        <Badge
                          key={cv.key}
                          variant="outline"
                          className="text-[10px] font-mono"
                        >
                          {fieldLabel(cv.key)}: {cv.original.toFixed(1)} &rarr;{' '}
                          {cv.current.toFixed(1)}
                        </Badge>
                      ))}
                      {changedVars.length > 3 && (
                        <span className="text-xs text-muted-foreground">
                          +{changedVars.length - 3}개
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      슬라이더를 조절하여 값을 변경하세요.
                    </span>
                  )}
                </div>

                <Button
                  onClick={handleRunSimulation}
                  disabled={isSimulating || changedVars.length === 0}
                  className="shrink-0"
                >
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

          {/* 시뮬레이션 결과 */}
          {latestResult && (
            <>
              <ParameterSweepChart result={latestResult} />
              <SimulationResultPanel result={latestResult} />
            </>
          )}
        </>
      )}
    </div>
  );
}
