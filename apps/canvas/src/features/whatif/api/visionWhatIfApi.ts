import { visionApi } from '@/lib/api/clients';

const base = (caseId: string) => `/api/v3/cases/${caseId}/what-if`;

export interface VisionScenarioCreate {
  scenario_name: string;
  scenario_type: string;
  base_scenario_id?: string;
  parameters?: Record<string, unknown>;
  constraints?: unknown[];
}

export interface VisionScenario {
  id: string;
  scenario_name: string;
  scenario_type: string;
  parameters?: Record<string, unknown>;
  constraints?: unknown[];
  status: string;
  result?: { summary?: { npv_at_wacc?: number }; feasibility_score?: number; [k: string]: unknown };
  started_at?: string;
  completed_at?: string;
  updated_at?: string;
}

export interface CompareItem {
  scenario_id: string;
  scenario_name: string;
  npv_at_wacc?: number;
  feasibility_score?: number;
}

async function normalize<T>(res: unknown): Promise<T> {
  return res as T;
}

export async function listScenarios(caseId: string): Promise<{ data: VisionScenario[]; total: number }> {
  const res = await visionApi.get(base(caseId));
  const body = (res as { data?: VisionScenario[]; total?: number }) ?? {};
  return {
    data: Array.isArray(body.data) ? body.data : [],
    total: typeof body.total === 'number' ? body.total : 0,
  };
}

export async function createScenario(caseId: string, payload: VisionScenarioCreate): Promise<VisionScenario> {
  const res = await visionApi.post(base(caseId), payload);
  return res as unknown as VisionScenario;
}

export async function getScenario(caseId: string, scenarioId: string): Promise<VisionScenario> {
  return normalize(visionApi.get(`${base(caseId)}/${scenarioId}`));
}

export async function updateScenario(
  caseId: string,
  scenarioId: string,
  payload: Partial<VisionScenarioCreate>
): Promise<VisionScenario> {
  return normalize(visionApi.put(`${base(caseId)}/${scenarioId}`, payload));
}

export async function deleteScenario(caseId: string, scenarioId: string): Promise<void> {
  await visionApi.delete(`${base(caseId)}/${scenarioId}`);
}

export async function computeScenario(caseId: string, scenarioId: string): Promise<{ scenario_id: string; status: string; poll_url?: string }> {
  const res = await visionApi.post(`${base(caseId)}/${scenarioId}/compute`, {});
  return res as unknown as { scenario_id: string; status: string; poll_url?: string };
}

export async function getScenarioStatus(caseId: string, scenarioId: string): Promise<{ scenario_id: string; status: string }> {
  const res = await visionApi.get(`${base(caseId)}/${scenarioId}/status`);
  return res as unknown as { scenario_id: string; status: string };
}

export async function getScenarioResult(caseId: string, scenarioId: string): Promise<VisionScenario['result']> {
  const res = await visionApi.get(`${base(caseId)}/${scenarioId}/result`);
  return (res as unknown as VisionScenario).result;
}

export async function compareScenarios(
  caseId: string,
  scenarioIds: string[]
): Promise<{ case_id: string; items: CompareItem[]; total: number }> {
  const ids = scenarioIds.join(',');
  const res = await visionApi.get(`${base(caseId)}/compare`, { params: { scenario_ids: ids } });
  return res as unknown as { case_id: string; items: CompareItem[]; total: number };
}
