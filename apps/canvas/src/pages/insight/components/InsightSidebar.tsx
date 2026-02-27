// pages/insight/components/InsightSidebar.tsx
// Insight page: KPI selector + Driver ranking — now inline instead of sidebar

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
    <div className="space-y-6">
      {/* KPI Selector section */}
      <div>
        <KpiSelector onSelect={onKpiSelect} loading={loading} />
      </div>

      {/* Driver Ranking section */}
      <div>
        <DriverRankingPanel
          graphData={graphData}
          impactEvidence={impactEvidence}
          selectedDriverId={selectedDriverId}
          onSelectDriver={onSelectDriver}
          onHoverDriver={onHoverDriver}
        />
      </div>
    </div>
  );
}
