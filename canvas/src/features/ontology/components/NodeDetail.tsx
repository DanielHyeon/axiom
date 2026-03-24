/**
 * 온톨로지 노드 상세 패널 — 속성 + 연결 + 네비게이션.
 * Sprint 4b: 노드 클릭 시 우측 사이드 패널.
 */

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { X, ExternalLink } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

interface NodeDetailProps {
  node: {
    id: string;
    name: string;
    layer: string;
    properties: Record<string, unknown>;
    connections: Array<{ targetId: string; targetName: string; relationType: string }>;
  } | null;
  onClose: () => void;
}

export function NodeDetail({ node, onClose }: NodeDetailProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  if (!node) return null;

  return (
    <div className="w-80 border-l border-border bg-card p-4 overflow-auto">
      {/* 헤더 */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold">{node.name}</h3>
          <Badge variant="outline" className="mt-1 text-xs">{node.layer}</Badge>
        </div>
        <button onClick={onClose} aria-label={t('common.close')} className="p-1 hover:bg-muted rounded">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* 속성 */}
      <div className="space-y-2 mb-4">
        <h4 className="text-xs font-medium text-muted-foreground">{t('ontologyExt.nodeDetail.properties')}</h4>
        {Object.entries(node.properties).map(([key, value]) => (
          <div key={key} className="flex justify-between text-sm">
            <span className="text-muted-foreground">{key}</span>
            <span className="font-mono text-xs">{String(value)}</span>
          </div>
        ))}
      </div>

      {/* 연결 */}
      <div className="space-y-2 mb-4">
        <h4 className="text-xs font-medium text-muted-foreground">{t('ontologyExt.nodeDetail.connections', { count: node.connections.length })}</h4>
        {node.connections.slice(0, 10).map((conn, i) => (
          <div key={i} className="flex items-center justify-between text-sm">
            <span className="truncate">{conn.targetName}</span>
            <Badge variant="secondary" className="text-[10px] shrink-0">{conn.relationType}</Badge>
          </div>
        ))}
      </div>

      {/* 프로세스 디자이너 연동 */}
      <Button
        variant="outline"
        size="sm"
        className="w-full gap-1"
        onClick={() => navigate(`${ROUTES.PROCESS_DESIGNER.LIST}?ontologyNodeId=${node.id}`)}
      >
        <ExternalLink className="h-3.5 w-3.5" />
        {t('ontologyExt.nodeDetail.viewInDesigner')}
      </Button>
    </div>
  );
}
