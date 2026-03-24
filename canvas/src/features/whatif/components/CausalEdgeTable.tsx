/**
 * CausalEdgeTable — 인과 관계 엣지 테이블
 *
 * 발견된 인과 관계를 테이블로 표시하고
 * 사용자가 개별 엣지를 선택/해제할 수 있다.
 */
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import type { CausalEdge } from '../types/wizard';

interface CausalEdgeTableProps {
  /** 인과 관계 엣지 목록 */
  edges: CausalEdge[];
  /** 엣지 선택/해제 토글 핸들러 */
  onToggleEdge: (index: number) => void;
}

export function CausalEdgeTable({ edges, onToggleEdge }: CausalEdgeTableProps) {
  const { t } = useTranslation();
  const selectedCount = edges.filter((e) => e.selected).length;

  return (
    <div>
      {/* 요약 */}
      <div className="flex items-center justify-between mb-3">
        <h5 className="text-sm font-semibold">
          {t('whatifExt.causalEdge.discoveredCount', { count: edges.length })}
        </h5>
        <span className="text-xs text-muted-foreground">
          {t('whatifExt.causalEdge.selectedCount', { count: selectedCount })}
        </span>
      </div>

      {/* 테이블 */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50">
              <th className="w-10 px-3 py-2 text-center" />
              <th className="px-3 py-2 text-left font-medium">{t('whatifExt.causalEdge.source')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('whatifExt.causalEdge.field')}</th>
              <th className="px-1 py-2 text-center text-muted-foreground">
                &rarr;
              </th>
              <th className="px-3 py-2 text-left font-medium">{t('whatifExt.causalEdge.target')}</th>
              <th className="px-3 py-2 text-left font-medium">{t('whatifExt.causalEdge.field')}</th>
              <th className="px-3 py-2 text-right font-medium">{t('whatifExt.causalEdge.strength')}</th>
              <th className="px-3 py-2 text-right font-medium">Lag</th>
              <th className="px-3 py-2 text-right font-medium">Pearson</th>
              <th className="px-3 py-2 text-right font-medium">p-value</th>
              <th className="px-3 py-2 text-center font-medium">{t('whatifExt.causalEdge.direction')}</th>
            </tr>
          </thead>
          <tbody>
            {edges.map((edge, idx) => (
              <tr
                key={`${edge.source}-${edge.sourceField}-${edge.target}-${edge.targetField}`}
                className={cn(
                  'border-t border-border transition-colors',
                  edge.selected
                    ? 'hover:bg-muted/30'
                    : 'opacity-40 line-through hover:bg-muted/20'
                )}
              >
                {/* 체크박스 */}
                <td className="px-3 py-2 text-center">
                  <Checkbox
                    checked={edge.selected}
                    onCheckedChange={() => onToggleEdge(idx)}
                    aria-label={`${edge.sourceField} -> ${edge.targetField}`}
                  />
                </td>

                {/* 소스 */}
                <td className="px-3 py-2 text-xs text-muted-foreground max-w-[140px] truncate">
                  {edge.sourceName}
                </td>
                <td className="px-3 py-2 font-medium">{edge.sourceField}</td>

                {/* 화살표 */}
                <td className="px-1 py-2 text-center text-muted-foreground">
                  &rarr;
                </td>

                {/* 타겟 */}
                <td className="px-3 py-2 text-xs text-muted-foreground max-w-[140px] truncate">
                  {edge.targetName}
                </td>
                <td className="px-3 py-2 font-medium">{edge.targetField}</td>

                {/* 강도 */}
                <td className="px-3 py-2 text-right">
                  <span className="text-primary font-semibold">
                    {edge.strength.toFixed(3)}
                  </span>
                </td>

                {/* Lag */}
                <td className="px-3 py-2 text-right text-muted-foreground">
                  {edge.lag}
                </td>

                {/* Pearson */}
                <td className="px-3 py-2 text-right">
                  <span
                    className={cn(
                      'font-mono',
                      edge.pearson > 0 ? 'text-emerald-400' : 'text-red-400'
                    )}
                  >
                    {edge.pearson.toFixed(3)}
                  </span>
                </td>

                {/* p-value */}
                <td className="px-3 py-2 text-right font-mono text-muted-foreground">
                  {edge.pValue.toFixed(4)}
                </td>

                {/* 방향 */}
                <td className="px-3 py-2 text-center">
                  <Badge
                    variant="outline"
                    className={cn(
                      'text-[10px]',
                      edge.direction === 'positive'
                        ? 'text-emerald-400 border-emerald-500/30'
                        : 'text-red-400 border-red-500/30'
                    )}
                  >
                    {edge.direction === 'positive' ? t('whatifExt.causalEdge.positive') : t('whatifExt.causalEdge.negative')}
                  </Badge>
                </td>
              </tr>
            ))}

            {edges.length === 0 && (
              <tr>
                <td
                  colSpan={11}
                  className="px-3 py-8 text-center text-muted-foreground"
                >
                  {t('whatifExt.causalEdge.noRelations')}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
