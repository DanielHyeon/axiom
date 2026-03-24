/**
 * TriggerNode — 트리거 노드 표시 컴포넌트
 *
 * 이벤트 유형 뱃지를 표시한다 (예: case_created, webhook 등).
 */

import { Zap } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { TriggerData, TriggerEventType } from '../../types/workflowEditor.types';

// 이벤트 유형별 라벨 (한글)
const EVENT_LABELS: Record<TriggerEventType, string> = {
  case_created: '케이스 생성',
  case_updated: '케이스 수정',
  kpi_threshold: 'KPI 임계값',
  schedule_cron: '스케줄 (Cron)',
  manual: '수동 실행',
  webhook: 'Webhook',
};

interface TriggerNodeProps {
  data: TriggerData;
}

export const TriggerNode: React.FC<TriggerNodeProps> = ({ data }) => (
  <div className="flex flex-col items-center gap-1.5 p-2">
    {/* 아이콘 */}
    <Zap className="h-5 w-5 text-amber-400" />
    {/* 이벤트 유형 뱃지 */}
    <Badge
      variant="outline"
      className="text-[10px] border-amber-500/40 text-amber-300 whitespace-nowrap"
    >
      {EVENT_LABELS[data.eventType] ?? data.eventType}
    </Badge>
  </div>
);
