/**
 * Step 4: 모델 학습
 *
 * - 모델 구성 확인 (스펙 목록)
 * - 학습 실행
 * - 학습 진행률 및 결과 표시
 */
import { useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Loader2, Cog, ArrowRight, RefreshCw } from 'lucide-react';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { useWhatIfWizard } from '../hooks/useWhatIfWizard';
import { ModelTrainingProgress } from './ModelTrainingProgress';

export function StepTrainModels() {
  const {
    modelSpecs,
    trainedModels,
    discoveredEdges,
  } = useWhatIfWizardStore();

  const {
    isTraining,
    isBuildingGraph,
    error,
    buildModelGraph,
    runTraining,
  } = useWhatIfWizard();

  // 모델 스펙이 없으면 자동으로 그래프 구성 실행
  useEffect(() => {
    if (modelSpecs.length === 0 && discoveredEdges.some((e) => e.selected)) {
      buildModelGraph();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTrain = useCallback(() => {
    runTraining();
  }, [runTraining]);

  const handleRebuild = useCallback(() => {
    buildModelGraph();
  }, [buildModelGraph]);

  const hasTrainedModels = trainedModels.length > 0;
  const allTrained = trainedModels.length > 0 && trainedModels.every((m) => m.status === 'trained');
  const anyFailed = trainedModels.some((m) => m.status === 'failed');

  return (
    <div className="space-y-6 max-w-4xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Cog className="w-5 h-5 text-primary" />
          모델 학습 및 등록
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          인과 관계를 기반으로 예측 모델을 학습하고 Neo4j 온톨로지에 등록합니다.
        </p>
      </div>

      {/* 모델 구성 중 로딩 */}
      {isBuildingGraph && (
        <div className="flex flex-col items-center py-12 gap-3">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">모델 그래프 구성 중...</p>
        </div>
      )}

      {/* 에러 표시 */}
      {error && (
        <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* 모델 스펙 카드 (학습 전) */}
      {modelSpecs.length > 0 && !hasTrainedModels && !isTraining && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">
              제안된 모델 ({modelSpecs.length}개)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {modelSpecs.map((spec, idx) => (
              <div
                key={spec.modelId}
                className="flex items-center gap-4 p-3 rounded-lg bg-muted/30 border border-border"
              >
                {/* 순서 */}
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold shrink-0">
                  {idx + 1}
                </span>

                {/* 입력 */}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium">{spec.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    입력: {spec.features.map((f) => f.field).join(', ')}
                  </div>
                </div>

                {/* 화살표 */}
                <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />

                {/* 출력 */}
                <div className="text-sm font-medium text-primary shrink-0">
                  {spec.targetField}
                </div>
              </div>
            ))}

            <div className="flex gap-3 pt-3">
              <Button onClick={handleTrain} disabled={isTraining}>
                {isTraining ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    학습 중...
                  </>
                ) : (
                  '모델 학습 시작'
                )}
              </Button>
              <Button variant="outline" onClick={handleRebuild} disabled={isBuildingGraph}>
                <RefreshCw className="w-4 h-4 mr-2" />
                모델 재구성
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 학습 진행률 */}
      {(hasTrainedModels || isTraining) && (
        <ModelTrainingProgress models={trainedModels} />
      )}

      {/* 학습 완료 메시지 */}
      {allTrained && (
        <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm">
          모든 모델의 학습이 완료되었습니다. 다음 단계에서 시뮬레이션을 실행하세요.
        </div>
      )}

      {/* 재학습 버튼 (실패 시) */}
      {anyFailed && !isTraining && (
        <Button onClick={handleTrain} variant="destructive" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          재학습
        </Button>
      )}
    </div>
  );
}
