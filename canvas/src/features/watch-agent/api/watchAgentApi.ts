/**
 * Watch Agent API — LLM 기반 모니터링 규칙 자동 생성
 *
 * 백엔드: Core 서비스 — /api/v1/watch-agent
 */
import { coreApi } from '@/lib/api/clients';

/** LLM이 생성한 규칙 제안 */
export interface RuleProposal {
  name: string;
  sql_query: string;
  condition_type: string;
  threshold: number;
  threshold_upper?: number;
  severity: string;
  explanation: string;
}

/** 규칙 생성 요청 결과 */
export interface GenerateResult {
  proposal: RuleProposal;
}

/** 규칙 확인/생성 결과 */
export interface ConfirmResult {
  rule_id: string;
  name: string;
}

/** 자연어 설명으로 모니터링 규칙 제안 받기 */
export async function generateRule(description: string): Promise<RuleProposal> {
  const res = await coreApi.post('/api/v1/watch-agent/generate', { description });
  const body = res as unknown as GenerateResult;
  return body.proposal;
}

/** 제안된 규칙을 확인하고 실제 생성 */
export async function confirmRule(proposal: RuleProposal): Promise<ConfirmResult> {
  const res = await coreApi.post('/api/v1/watch-agent/confirm', proposal);
  return res as unknown as ConfirmResult;
}
