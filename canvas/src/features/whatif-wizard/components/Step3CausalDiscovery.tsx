/**
 * Step 3: 인과 관계 발견
 *
 * - 발견된 인과관계 요약 표시
 * - 신뢰도 임계값 슬라이더
 * - 관계 목록 (source → target, weight, lag)
 * - Event Fork 모드에서는 건너뛰기 가능
 */
import { useCallback, useMemo } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ArrowRight, GitFork, Loader2, Sparkles, SkipForward } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { useWhatIfWizard } from '../hooks/useWhatIfWizard';

/** 신뢰도에 따른 시각적 표시 색상 */
function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'text-emerald-400';
  if (confidence >= 0.5) return 'text-amber-400';
  return 'text-red-400';
}

/** 방향 표시 텍스트 */
function directionLabel(dir: 'positive' | 'negative'): string {
  return dir === 'positive' ? '양(+)' : '음(-)';
}

export function Step3CausalDiscovery() {
  const { t } = useTranslation();
  const {
    simulationMode,
    causalRelations,
    confidenceThreshold,
    setConfidenceThreshold,
    selectedNodeIds,
    nextStep,
    caseId,
  } = useWhatIfWizardStore();

  const { isDiscovering, runCausalDiscovery, error } = useWhatIfWizard();

  // 임계값 이상의 관계만 필터링
  const filteredRelations = useMemo(
    () => causalRelations.filter((r) => r.confidence >= confidenceThreshold),
    [causalRelations, confidenceThreshold],
  );

  // 인과 분석 실행 — 스토어의 caseId 사용
  const handleDiscover = useCallback(async () => {
    await runCausalDiscovery(caseId);
  }, [runCausalDiscovery, caseId]);

  // Event Fork 모드에서 스킵 가능
  const isEventForkMode = simulationMode === 'event-fork';

  return (
    <div className="space-y-6 max-w-4xl">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <GitFork className="w-5 h-5 text-primary" />
            {t('whatifWizard.step3.title', '인과 관계 발견')}
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            {t(
              'whatifWizard.step3.description',
              '선택한 노드 간의 인과 관계를 자동으로 분석합니다.',
            )}
          </p>
        </div>

        {/* Event Fork 모드: 건너뛰기 버튼 */}
        {isEventForkMode && (
          <Button variant="outline" size="sm" onClick={nextStep} className="gap-1.5">
            <SkipForward className="w-4 h-4" />
            건너뛰기
          </Button>
        )}
      </div>

      {/* Event Fork 모드 안내 */}
      {isEventForkMode && (
        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-sm">
          Event Fork 모드에서는 인과 관계 분석이 필수가 아닙니다. 분석을 건너뛰고 바로
          개입 설정으로 이동할 수 있습니다.
        </div>
      )}

      {/* 분석 실행 카드 */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm flex items-center gap-2">
              <Sparkles className="w-4 h-4" />
              인과 분석
            </CardTitle>
            <Badge variant="outline" className="text-xs">
              {selectedNodeIds.length}개 노드 대상
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 신뢰도 임계값 슬라이더 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">신뢰도 임계값</Label>
              <span className="text-xs font-mono text-muted-foreground">
                {(confidenceThreshold * 100).toFixed(0)}%
              </span>
            </div>
            <Slider
              value={[confidenceThreshold]}
              min={0}
              max={1}
              step={0.05}
              onValueChange={([v]) => setConfidenceThreshold(v)}
              className="w-full"
            />
            <p className="text-xs text-muted-foreground">
              임계값 이상의 신뢰도를 가진 관계만 표시합니다.
            </p>
          </div>

          {/* 분석 실행 버튼 */}
          <Button
            onClick={handleDiscover}
            disabled={isDiscovering || selectedNodeIds.length === 0}
            className="w-full"
          >
            {isDiscovering ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                분석 중...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                인과 관계 분석 실행
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* 에러 표시 */}
      {error && (
        <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* 발견된 인과관계 요약 */}
      {causalRelations.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">발견된 인과관계</CardTitle>
              <div className="flex gap-2">
                <Badge variant="secondary" className="text-xs">
                  총 {causalRelations.length}개
                </Badge>
                <Badge variant="outline" className="text-xs">
                  필터 후 {filteredRelations.length}개
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* 관계 테이블 */}
            <div className="rounded-lg border border-border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">소스</TableHead>
                    <TableHead className="text-xs w-8" />
                    <TableHead className="text-xs">타겟</TableHead>
                    <TableHead className="text-xs text-right">가중치</TableHead>
                    <TableHead className="text-xs text-right">시차(일)</TableHead>
                    <TableHead className="text-xs text-right">신뢰도</TableHead>
                    <TableHead className="text-xs text-center">방향</TableHead>
                    <TableHead className="text-xs text-center">방법</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRelations.map((rel, idx) => (
                    <TableRow key={`${rel.sourceId}-${rel.targetId}-${idx}`}>
                      <TableCell className="text-xs font-medium">
                        {rel.sourceName}
                      </TableCell>
                      <TableCell className="text-center">
                        <ArrowRight className="w-3 h-3 text-muted-foreground inline" />
                      </TableCell>
                      <TableCell className="text-xs font-medium">
                        {rel.targetName}
                      </TableCell>
                      <TableCell className="text-xs text-right font-mono">
                        {rel.weight.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-xs text-right font-mono">
                        {rel.lag}
                      </TableCell>
                      <TableCell
                        className={cn(
                          'text-xs text-right font-mono',
                          confidenceColor(rel.confidence),
                        )}
                      >
                        {(rel.confidence * 100).toFixed(0)}%
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge
                          variant="outline"
                          className={cn(
                            'text-[10px]',
                            rel.direction === 'positive'
                              ? 'text-emerald-400 border-emerald-500/30'
                              : 'text-red-400 border-red-500/30',
                          )}
                        >
                          {directionLabel(rel.direction)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        <Badge variant="outline" className="text-[10px]">
                          {rel.method}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {filteredRelations.length === 0 && causalRelations.length > 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                현재 임계값({(confidenceThreshold * 100).toFixed(0)}%)을 만족하는 관계가
                없습니다. 임계값을 낮춰보세요.
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
