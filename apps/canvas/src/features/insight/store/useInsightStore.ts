// features/insight/store/useInsightStore.ts
// Zustand store for Insight feature state management

import { create } from 'zustand';
import type {
  GraphData,
  InsightJob,
  DriverDetailResponse,
  TimeRange,
  CompactEvidence,
  ImpactPath,
} from '../types/insight';

interface InsightState {
  // KPI selection
  selectedKpiId: string | null;
  selectedKpiFingerprint: string | null;

  // Graph data
  impactGraph: GraphData | null;
  impactGraphLoading: boolean;
  impactGraphError: string | null;

  // Compact evidence from job result (keyed by node_id)
  impactEvidence: Record<string, CompactEvidence[]> | null;

  // Derived paths (transformed from backend BackendPath[])
  impactPaths: ImpactPath[];

  // Async job
  currentJobId: string | null;
  jobStatus: InsightJob | null;

  // Driver selection / detail
  selectedDriverId: string | null;
  driverDetail: DriverDetailResponse | null;
  driverDetailLoading: boolean;

  // Hover highlight (from DriverRankingPanel hover)
  hoveredNodeId: string | null;

  // Path comparison
  highlightedPaths: string[];

  // Filters
  timeRange: TimeRange;
  datasource: string | null;

  // View state
  nodeDetailOpen: boolean;

  // Actions
  selectKpi: (kpiId: string, fingerprint: string) => void;
  clearKpi: () => void;
  setImpactGraph: (graph: GraphData) => void;
  setImpactGraphLoading: (loading: boolean) => void;
  setImpactGraphError: (error: string | null) => void;
  setImpactEvidence: (ev: Record<string, CompactEvidence[]> | null) => void;
  setImpactPaths: (paths: ImpactPath[]) => void;
  setJobStatus: (job: InsightJob | null) => void;
  selectDriver: (driverId: string | null) => void;
  setDriverDetail: (detail: DriverDetailResponse | null) => void;
  setHoveredNodeId: (id: string | null) => void;
  togglePath: (pathId: string) => void;
  setTimeRange: (range: TimeRange) => void;
  setDatasource: (ds: string | null) => void;
  reset: () => void;
}

const initialState = {
  selectedKpiId: null as string | null,
  selectedKpiFingerprint: null as string | null,
  impactGraph: null as GraphData | null,
  impactGraphLoading: false,
  impactGraphError: null as string | null,
  impactEvidence: null as Record<string, CompactEvidence[]> | null,
  impactPaths: [] as ImpactPath[],
  currentJobId: null as string | null,
  jobStatus: null as InsightJob | null,
  selectedDriverId: null as string | null,
  driverDetail: null as DriverDetailResponse | null,
  driverDetailLoading: false,
  hoveredNodeId: null as string | null,
  highlightedPaths: [] as string[],
  timeRange: '30d' as TimeRange,
  datasource: null as string | null,
  nodeDetailOpen: false,
};

export const useInsightStore = create<InsightState>((set, get) => ({
  ...initialState,

  selectKpi: (kpiId, fingerprint) =>
    set({
      selectedKpiId: kpiId,
      selectedKpiFingerprint: fingerprint,
      selectedDriverId: null,
      driverDetail: null,
      highlightedPaths: [],
      impactGraph: null,
      impactEvidence: null,
      impactPaths: [],
      impactGraphError: null,
    }),

  clearKpi: () =>
    set({
      selectedKpiId: null,
      selectedKpiFingerprint: null,
      impactGraph: null,
      impactEvidence: null,
      impactPaths: [],
      selectedDriverId: null,
      driverDetail: null,
      highlightedPaths: [],
    }),

  setImpactGraph: (graph) =>
    set({ impactGraph: graph, impactGraphLoading: false }),

  setImpactGraphLoading: (loading) =>
    set({ impactGraphLoading: loading }),

  setImpactGraphError: (error) =>
    set({ impactGraphError: error, impactGraphLoading: false }),

  setImpactEvidence: (ev) => set({ impactEvidence: ev }),

  setImpactPaths: (paths) => set({ impactPaths: paths }),

  setJobStatus: (job) =>
    set({ jobStatus: job, currentJobId: job?.job_id ?? null }),

  selectDriver: (driverId) =>
    set({
      selectedDriverId: driverId,
      nodeDetailOpen: driverId !== null,
      driverDetail: null,
      driverDetailLoading: driverId !== null,
    }),

  setDriverDetail: (detail) =>
    set({ driverDetail: detail, driverDetailLoading: false }),

  setHoveredNodeId: (id) => set({ hoveredNodeId: id }),

  togglePath: (pathId) => {
    const current = get().highlightedPaths;
    if (current.includes(pathId)) {
      set({ highlightedPaths: current.filter((p) => p !== pathId) });
    } else if (current.length < 3) {
      set({ highlightedPaths: [...current, pathId] });
    }
    // Max 3 paths; ignore additional toggles
  },

  setTimeRange: (range) => set({ timeRange: range }),
  setDatasource: (ds) => set({ datasource: ds }),

  reset: () => set(initialState),
}));
