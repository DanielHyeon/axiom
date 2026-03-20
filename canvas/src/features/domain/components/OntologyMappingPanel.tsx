/**
 * OntologyMappingPanel — 온톨로지 매핑 시각화 패널
 *
 * ObjectType과 Axiom 4계층 온톨로지(KPI/Driver/Measure/Process/Resource) 간
 * 매핑 상태를 보여주고 연결/해제를 지원한다.
 */

import React from 'react';
import { Network, Link2, Unlink, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { ObjectType } from '../types/domain';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface OntologyMappingPanelProps {
  /** 현재 ObjectType */
  objectType: ObjectType;
  /** 연결 콜백 */
  onLink?: (objectTypeId: string) => void;
  /** 연결 해제 콜백 */
  onUnlink?: (objectTypeId: string) => void;
}

// ──────────────────────────────────────
// 레이어 색상
// ──────────────────────────────────────

const LAYER_COLORS: Record<string, string> = {
  kpi: 'text-red-400 bg-red-400/10',
  driver: 'text-amber-400 bg-amber-400/10',
  measure: 'text-orange-400 bg-orange-400/10',
  process: 'text-emerald-400 bg-emerald-400/10',
  resource: 'text-blue-400 bg-blue-400/10',
};

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const OntologyMappingPanel: React.FC<OntologyMappingPanelProps> = ({
  objectType,
  onLink,
  onUnlink,
}) => {
  const isLinked = !!objectType.ontologyNodeId;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold flex items-center gap-2">
          <Network className="h-4 w-4 text-primary" />
          온톨로지 매핑
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLinked ? (
          <div className="flex items-center justify-between p-3 border border-primary/20 bg-primary/5 rounded-lg">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-8 h-8 rounded-md bg-primary/10 text-primary">
                <Link2 className="h-4 w-4" />
              </div>
              <div>
                <p className="text-sm font-medium text-foreground">
                  온톨로지 노드에 연결됨
                </p>
                <p className="text-xs text-muted-foreground">
                  ID: {objectType.ontologyNodeId}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => {
                  /* 온톨로지 페이지로 이동하는 로직 (추후 구현) */
                }}
              >
                <ExternalLink className="h-3 w-3 mr-1" />
                보기
              </Button>
              {onUnlink && (
                <Button
                  variant="outline"
                  size="sm"
                  className="text-xs text-destructive hover:text-destructive"
                  onClick={() => onUnlink(objectType.id)}
                >
                  <Unlink className="h-3 w-3 mr-1" />
                  해제
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <div className="flex items-center justify-center w-10 h-10 rounded-full bg-muted">
              <Unlink className="h-5 w-5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">
                온톨로지 노드에 연결되지 않았습니다.
              </p>
              <p className="text-xs text-muted-foreground mt-0.5">
                온톨로지에 매핑하면 그래프 분석과 영향도 분석에 활용됩니다.
              </p>
            </div>
            {onLink && (
              <Button
                variant="outline"
                size="sm"
                className="text-xs"
                onClick={() => onLink(objectType.id)}
              >
                <Link2 className="h-3 w-3 mr-1" />
                온톨로지 노드 연결
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};
