/**
 * CEP 규칙 CRUD + 평가 + 이력 조회 API
 *
 * 백엔드: Core 서비스 — /api/v1/cep/rules
 */
import { coreApi } from '@/lib/api/clients';
import type { CEPRule, CEPRulePayload, CEPResult, CEPHistoryItem } from '../types/cep';

/** 전체 규칙 목록 조회 */
export async function listRules(): Promise<CEPRule[]> {
  const res = await coreApi.get('/api/v1/cep/rules');
  const payload = (res as { data?: unknown })?.data ?? res;
  return Array.isArray(payload) ? (payload as CEPRule[]) : [];
}

/** 규칙 생성 */
export async function createRule(rule: CEPRulePayload): Promise<CEPRule> {
  const res = await coreApi.post('/api/v1/cep/rules', rule);
  return res as unknown as CEPRule;
}

/** 규칙 수정 */
export async function updateRule(id: string, rule: Partial<CEPRulePayload>): Promise<CEPRule> {
  const res = await coreApi.put(`/api/v1/cep/rules/${id}`, rule);
  return res as unknown as CEPRule;
}

/** 규칙 삭제 */
export async function deleteRule(id: string): Promise<void> {
  await coreApi.delete(`/api/v1/cep/rules/${id}`);
}

/** 규칙 수동 평가 — 입력값에 대해 조건 충족 여부 확인 */
export async function evaluateRule(id: string, value: number): Promise<CEPResult> {
  const res = await coreApi.post(`/api/v1/cep/rules/${id}/evaluate`, { value });
  return res as unknown as CEPResult;
}

/** 규칙 평가 이력 조회 */
export async function getRuleHistory(id: string): Promise<CEPHistoryItem[]> {
  const res = await coreApi.get(`/api/v1/cep/rules/${id}/history`);
  const payload = (res as { data?: unknown })?.data ?? res;
  return Array.isArray(payload) ? (payload as CEPHistoryItem[]) : [];
}
