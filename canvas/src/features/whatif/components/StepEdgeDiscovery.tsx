/**
 * Step 3: 인과 관계 발견
 *
 * - 분석 파라미터 설정 (maxLag, minCorrelation)
 * - Vision 인과 분석 API 호출
 * - 발견된 엣지 테이블 표시
 * - 사용자가 엣지를 선택/해제 가능
 */
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Search, Loader2, BarChart3, GitBranch, Rows3 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useWhatIfWizardStore } from '../store/useWhatIfWizardStore';
import { useWhatIfWizard } from '../hooks/useWhatIfWizard';
import { CausalEdgeTable } from './CausalEdgeTable';

export function StepEdgeDiscovery() {
  const {
    discoveredEdges,
    discoveryParams,
    setDiscoveryParams,
    toggleEdgeSelection,
  } = useWhatIfWizardStore();

  const {
    isDiscovering,
    error,
    runDiscovery,
    discoveryStats,
  } = useWhatIfWizard();

  const { t } = useTranslation();

  return (
    <div className="space-y-6 max-w-5xl">
      {/* 헤더 */}
      <div>
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Search className="w-5 h-5 text-primary" />
          {t('whatifExt.edgeDiscovery.title')}
        </h3>
        <p className="text-sm text-muted-foreground mt-1">
          {t('whatifExt.edgeDiscovery.description')}
        </p>
      </div>

      {/* 파라미터 설정 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">{t('whatifExt.analysisParams')}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-6 flex-wrap">
            <div className="space-y-1">
              <Label htmlFor="max-lag" className="text-xs">
                {t('whatifExt.edgeDiscovery.maxLag')}
              </Label>
              <Input
                id="max-lag"
                type="number"
                min={1}
                max={12}
                value={discoveryParams.maxLag}
                onChange={(e) =>
                  setDiscoveryParams({
                    ...discoveryParams,
                    maxLag: parseInt(e.target.value) || 3,
                  })
                }
                className="w-24"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="min-corr" className="text-xs">
                {t('whatifExt.edgeDiscovery.minCorrelation')}
              </Label>
              <Input
                id="min-corr"
                type="number"
                min={0.1}
                max={0.9}
                step={0.05}
                value={discoveryParams.minCorrelation}
                onChange={(e) =>
                  setDiscoveryParams({
                    ...discoveryParams,
                    minCorrelation: parseFloat(e.target.value) || 0.3,
                  })
                }
                className="w-24"
              />
            </div>
            <Button
              onClick={runDiscovery}
              disabled={isDiscovering}
              className="h-9"
            >
              {isDiscovering ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  {t('whatifExt.edgeDiscovery.analyzing')}
                </>
              ) : (
                t('whatifExt.startAnalysis')
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

      {/* 결과 요약 카드 */}
      {discoveryStats && (
        <div className="grid grid-cols-3 gap-4">
          <Card className="bg-muted/30">
            <CardContent className="pt-4 pb-3 text-center">
              <Rows3 className="w-5 h-5 mx-auto mb-1 text-primary" />
              <div className="text-2xl font-bold text-primary">
                {discoveryStats.dataRows.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">{t('whatifExt.dataRows')}</div>
            </CardContent>
          </Card>
          <Card className="bg-muted/30">
            <CardContent className="pt-4 pb-3 text-center">
              <BarChart3 className="w-5 h-5 mx-auto mb-1 text-primary" />
              <div className="text-2xl font-bold text-primary">
                {discoveryStats.variablesCount}
              </div>
              <div className="text-xs text-muted-foreground">{t('whatifExt.variables')}</div>
            </CardContent>
          </Card>
          <Card className="bg-muted/30">
            <CardContent className="pt-4 pb-3 text-center">
              <GitBranch className="w-5 h-5 mx-auto mb-1 text-primary" />
              <div className="text-2xl font-bold text-primary">
                {discoveredEdges.length}
              </div>
              <div className="text-xs text-muted-foreground">{t('whatifExt.discoveredRelations')}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 엣지 테이블 */}
      {discoveredEdges.length > 0 && (
        <CausalEdgeTable
          edges={discoveredEdges}
          onToggleEdge={toggleEdgeSelection}
        />
      )}

      {/* 빈 결과 안내 */}
      {discoveryStats && discoveredEdges.length === 0 && (
        <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm">
          {t('whatifExt.edgeDiscovery.noResults')}
        </div>
      )}
    </div>
  );
}
