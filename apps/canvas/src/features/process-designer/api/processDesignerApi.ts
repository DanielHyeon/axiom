// features/process-designer/api/processDesignerApi.ts
// Synapse API 클라이언트 — 프로세스 마이닝 (설계 §5.2)

import { synapseApi } from '@/lib/api/clients';
import type { EventLogBindingData } from '../types/processDesigner';

// ---------------------------------------------------------------------------
// 1. 프로세스 발견 (pm4py)
// ---------------------------------------------------------------------------

export interface DiscoverRequest {
  sourceTable: string;
  timestampColumn: string;
  caseIdColumn: string;
  activityColumn: string;
  algorithm?: 'alpha' | 'inductive' | 'heuristic';
}

export interface DiscoveredActivity {
  name: string;
  frequency: number;
  isStart: boolean;
  isEnd: boolean;
}

export interface DiscoveredTransition {
  source: string;
  target: string;
  frequency: number;
}

export interface DiscoveredProcess {
  activities: DiscoveredActivity[];
  transitions: DiscoveredTransition[];
}

export function discoverProcess(req: DiscoverRequest): Promise<DiscoveredProcess> {
  return synapseApi.post('/process-mining/discover', req);
}

// ---------------------------------------------------------------------------
// 2. 적합도 검사
// ---------------------------------------------------------------------------

export interface ConformanceDeviation {
  path: string[];
  frequency: number;
  percentage: number;
}

export interface ConformanceResult {
  fitnessScore: number;
  deviations: ConformanceDeviation[];
}

export function getConformance(
  boardId: string,
  bindings: EventLogBindingData[],
): Promise<ConformanceResult> {
  return synapseApi.post('/process-mining/conformance', { boardId, bindings });
}

// ---------------------------------------------------------------------------
// 3. 병목 분석
// ---------------------------------------------------------------------------

export interface BottleneckEntry {
  activityName: string;
  avgWaitTime: number;
  slaViolationRate: number;
  severity: 'low' | 'medium' | 'high';
}

export interface BottleneckResult {
  bottlenecks: BottleneckEntry[];
}

export function getBottlenecks(
  boardId: string,
  bindings: EventLogBindingData[],
): Promise<BottleneckResult> {
  return synapseApi.post('/process-mining/bottleneck', { boardId, bindings });
}
