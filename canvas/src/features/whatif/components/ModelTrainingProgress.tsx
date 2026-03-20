/**
 * ModelTrainingProgress — 모델 학습 진행률
 *
 * 각 모델의 학습 상태를 카드 형태로 표시한다.
 * 학습 완료 후 R2 점수와 RMSE를 표시한다.
 */
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2, CheckCircle2, XCircle, Clock } from 'lucide-react';
import type { TrainedModel } from '../types/wizard';

interface ModelTrainingProgressProps {
  models: TrainedModel[];
}

/** 상태별 아이콘과 스타일 */
const STATUS_CONFIG: Record<
  TrainedModel['status'],
  { icon: React.ElementType; label: string; color: string }
> = {
  pending: {
    icon: Clock,
    label: '대기',
    color: 'text-muted-foreground',
  },
  training: {
    icon: Loader2,
    label: '학습 중',
    color: 'text-primary',
  },
  trained: {
    icon: CheckCircle2,
    label: '완료',
    color: 'text-emerald-400',
  },
  failed: {
    icon: XCircle,
    label: '실패',
    color: 'text-destructive',
  },
};

/** R2 점수 색상 결정 */
function r2Color(r2: number): string {
  if (r2 >= 0.5) return 'text-emerald-400';
  if (r2 >= 0.1) return 'text-amber-400';
  return 'text-destructive';
}

export function ModelTrainingProgress({ models }: ModelTrainingProgressProps) {
  const trainedCount = models.filter((m) => m.status === 'trained').length;
  const totalCount = models.length;

  return (
    <div className="space-y-4">
      {/* 전체 진행률 */}
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">
          모델 학습 진행: {trainedCount}/{totalCount}
        </span>
        {trainedCount === totalCount && totalCount > 0 && (
          <Badge variant="outline" className="text-emerald-400 border-emerald-500/30">
            전체 완료
          </Badge>
        )}
      </div>

      {/* 진행 바 */}
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-emerald-500 transition-all duration-500 rounded-full"
          style={{
            width: totalCount > 0 ? `${(trainedCount / totalCount) * 100}%` : '0%',
          }}
        />
      </div>

      {/* 모델별 카드 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {models.map((model) => {
          const cfg = STATUS_CONFIG[model.status];
          const StatusIcon = cfg.icon;

          return (
            <Card
              key={model.modelId}
              className={cn(
                'transition-all',
                model.status === 'trained' && 'border-emerald-500/30',
                model.status === 'failed' && 'border-destructive/30'
              )}
            >
              <CardContent className="pt-4 pb-3">
                {/* 헤더: 이름 + 상태 */}
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium truncate pr-2">
                    {model.name}
                  </span>
                  <div className={cn('flex items-center gap-1 shrink-0', cfg.color)}>
                    <StatusIcon
                      className={cn(
                        'w-4 h-4',
                        model.status === 'training' && 'animate-spin'
                      )}
                    />
                    <span className="text-xs font-medium">{cfg.label}</span>
                  </div>
                </div>

                {/* 학습 완료 시 메트릭 표시 */}
                {model.status === 'trained' && (
                  <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-border">
                    <div className="text-center">
                      <div className={cn('text-sm font-bold', r2Color(model.r2Score))}>
                        {model.r2Score.toFixed(3)}
                      </div>
                      <div className="text-[10px] text-muted-foreground">R2</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm font-bold">
                        {model.rmse.toFixed(2)}
                      </div>
                      <div className="text-[10px] text-muted-foreground">RMSE</div>
                    </div>
                    <div className="text-center">
                      <div className="text-sm font-bold text-muted-foreground">
                        {model.modelType || '-'}
                      </div>
                      <div className="text-[10px] text-muted-foreground">알고리즘</div>
                    </div>
                  </div>
                )}

                {/* Neo4j 등록 상태 */}
                {model.status === 'trained' && (
                  <div className="mt-2 text-xs">
                    <Badge
                      variant="outline"
                      className={cn(
                        model.neo4jSaved
                          ? 'text-emerald-400 border-emerald-500/30'
                          : 'text-destructive border-destructive/30'
                      )}
                    >
                      {model.neo4jSaved ? 'Neo4j 등록 완료' : 'Neo4j 미등록'}
                    </Badge>
                  </div>
                )}

                {/* 실패 시 메시지 */}
                {model.status === 'failed' && (
                  <p className="text-xs text-destructive mt-1">
                    모델 학습에 실패했습니다. 데이터를 확인해주세요.
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
