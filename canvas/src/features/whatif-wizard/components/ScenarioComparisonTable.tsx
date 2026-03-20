/**
 * ScenarioComparisonTable — 다중 시나리오 비교 테이블
 *
 * 여러 시나리오의 KPI 결과를 가로로 나란히 비교한다.
 * 각 셀에는 절대값과 베이스라인 대비 델타가 표시된다.
 */
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Columns3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ScenarioComparisonResult } from '../types/whatifWizard.types';

interface ScenarioComparisonTableProps {
  /** 비교 결과 데이터 */
  data: ScenarioComparisonResult;
  /** 테이블 제목 */
  title?: string;
}

export function ScenarioComparisonTable({
  data,
  title = '시나리오 비교',
}: ScenarioComparisonTableProps) {
  if (!data || data.scenarios.length === 0 || data.metrics.length === 0) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Columns3 className="w-4 h-4" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground text-center py-6">
            비교할 시나리오 데이터가 없습니다.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Columns3 className="w-4 h-4" />
            {title}
          </CardTitle>
          <Badge variant="secondary" className="text-xs">
            {data.scenarios.length}개 시나리오 x {data.metrics.length}개 지표
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg border border-border overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                {/* 빈 셀 (행 제목 열) */}
                <TableHead className="text-xs font-semibold min-w-[140px] sticky left-0 bg-card z-10">
                  지표
                </TableHead>
                {/* 시나리오 열 헤더 */}
                {data.scenarios.map((scenario) => (
                  <TableHead
                    key={scenario.id}
                    className="text-xs text-center min-w-[120px]"
                  >
                    <div className="space-y-0.5">
                      <p className="font-semibold">{scenario.name}</p>
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.metrics.map((metric) => (
                <TableRow key={metric}>
                  {/* 지표 이름 */}
                  <TableCell className="text-xs font-medium sticky left-0 bg-card z-10">
                    {metric}
                  </TableCell>

                  {/* 시나리오별 값 */}
                  {data.scenarios.map((scenario) => {
                    const value = scenario.values[metric];
                    const delta = scenario.deltas[metric];
                    const hasData = value !== undefined;

                    return (
                      <TableCell key={`${scenario.id}-${metric}`} className="text-center">
                        {hasData ? (
                          <div className="space-y-0.5">
                            {/* 절대값 */}
                            <p className="text-xs font-mono">
                              {value.toFixed(2)}
                            </p>
                            {/* 델타 */}
                            {delta !== undefined && delta !== 0 && (
                              <Badge
                                variant="outline"
                                className={cn(
                                  'text-[9px] font-mono',
                                  delta > 0
                                    ? 'text-emerald-400 border-emerald-500/30'
                                    : 'text-red-400 border-red-500/30',
                                )}
                              >
                                {delta > 0 ? '+' : ''}
                                {delta.toFixed(2)}
                              </Badge>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
