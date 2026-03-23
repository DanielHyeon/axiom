/**
 * DashboardComposer — 역할별 패널 조합기.
 * useDashboardConfig()이 반환하는 패널 ID 목록에 따라
 * 해당 역할에 맞는 패널만 조건부 렌더링한다.
 */

import type { DashboardPanelId } from '../hooks/useDashboardConfig';
import { MyWorkitemsPanel } from './MyWorkitemsPanel';
import { ApprovalQueuePanel } from './ApprovalQueuePanel';
import { SystemHealthMiniCard } from './SystemHealthMiniCard';
import { DataPipelinePanel } from './DataPipelinePanel';
import { AnalyticsQuickPanel } from './AnalyticsQuickPanel';

/** 패널 ID → 컴포넌트 매핑 */
const PANEL_REGISTRY: Record<DashboardPanelId, React.FC> = {
  myWorkitems: MyWorkitemsPanel,
  approvalQueue: ApprovalQueuePanel,
  systemHealth: SystemHealthMiniCard,
  dataPipeline: DataPipelinePanel,
  analyticsQuick: AnalyticsQuickPanel,
};

interface DashboardComposerProps {
  panels: DashboardPanelId[];
}

export function DashboardComposer({ panels }: DashboardComposerProps) {
  if (panels.length === 0) return null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {panels.map((id) => {
        const Panel = PANEL_REGISTRY[id];
        if (!Panel) return null;
        return <Panel key={id} />;
      })}
    </div>
  );
}
