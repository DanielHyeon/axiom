// pages/insight/components/InsightSidebar.tsx
// Left sidebar: KPI selector + Driver ranking panel

import { KpiSelector } from '@/features/insight/components/KpiSelector';
import { DriverRankingPanel } from '@/features/insight/components/DriverRankingPanel';
import type { GraphData, CompactEvidence } from '@/features/insight/types/insight';

interface InsightSidebarProps {
  onKpiSelect: (kpiId: string, fingerprint: string) => void;
  graphData: GraphData | null;
  impactEvidence: Record<string, CompactEvidence[]> | null;
  selectedDriverId: string | null;
  onSelectDriver: (driverId: string) => void;
  onHoverDriver: (driverId: string | null) => void;
  loading?: boolean;
}

export function InsightSidebar({
  onKpiSelect,
  graphData,
  impactEvidence,
  selectedDriverId,
  onSelectDriver,
  onHoverDriver,
  loading,
}: InsightSidebarProps) {
  return (
    <aside className="w-60 shrink-0 flex flex-col border-r border-neutral-800 bg-neutral-900/30 overflow-y-auto">
      {/* KPI Selector section */}
      <div className="p-3 border-b border-neutral-800">
        <KpiSelector onSelect={onKpiSelect} loading={loading} />
      </div>

      {/* Driver Ranking section */}
      <div className="p-3 flex-1">
        <DriverRankingPanel
          graphData={graphData}
          impactEvidence={impactEvidence}
          selectedDriverId={selectedDriverId}
          onSelectDriver={onSelectDriver}
          onHoverDriver={onHoverDriver}
        />
      </div>
    </aside>
  );
}
