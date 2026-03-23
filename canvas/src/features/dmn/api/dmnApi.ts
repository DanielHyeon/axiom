/**
 * DMN 결정 테이블 API — Synapse DMN 엔진 연동.
 * KG-1: CRUD + 테스트 실행.
 */

import { synapseApi } from '@/lib/api/clients';
import type { DecisionTable, DmnTestRequest, DmnTestResult } from '../types/dmn';

const BASE = '/api/v3/synapse/dmn/tables';

/** 결정 테이블 목록 조회 */
export async function fetchDecisionTables(): Promise<DecisionTable[]> {
  const res = await synapseApi.get(BASE);
  return (res as unknown as { items: DecisionTable[] }).items ?? (res as unknown as DecisionTable[]);
}

/** 결정 테이블 상세 조회 */
export async function fetchDecisionTable(id: string): Promise<DecisionTable> {
  const res = await synapseApi.get(`${BASE}/${id}`);
  return res as unknown as DecisionTable;
}

/** 결정 테이블 생성 */
export async function createDecisionTable(
  payload: Pick<DecisionTable, 'name' | 'hitPolicy' | 'columns' | 'rules' | 'description'>,
): Promise<DecisionTable> {
  const res = await synapseApi.post(BASE, payload);
  return res as unknown as DecisionTable;
}

/** 결정 테이블 수정 */
export async function updateDecisionTable(
  id: string,
  payload: Partial<Pick<DecisionTable, 'name' | 'hitPolicy' | 'columns' | 'rules' | 'description'>>,
): Promise<DecisionTable> {
  const res = await synapseApi.put(`${BASE}/${id}`, payload);
  return res as unknown as DecisionTable;
}

/** 결정 테이블 삭제 */
export async function deleteDecisionTable(id: string): Promise<void> {
  await synapseApi.delete(`${BASE}/${id}`);
}

/** 테스트 실행 — 입력값으로 규칙 평가 */
export async function executeTest(id: string, payload: DmnTestRequest): Promise<DmnTestResult> {
  const res = await synapseApi.post(`${BASE}/${id}/execute`, payload);
  return res as unknown as DmnTestResult;
}
