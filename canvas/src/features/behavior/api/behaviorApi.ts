/**
 * BehaviorModel API 레이어
 *
 * Synapse 마이크로서비스의 behaviors 엔드포인트와 통신한다.
 * - 실행: POST /api/v3/synapse/behaviors/{id}/execute
 * - 코드 생성: POST /api/v3/synapse/behaviors/generate-code
 * - Behavior 코드 생성: POST /api/v3/synapse/behaviors/generate-behavior-code
 * - 결과 저장: POST /api/v3/synapse/behaviors/save-result
 */

import { synapseApi } from '@/lib/api/clients';
import { toast } from 'sonner';
import type {
  ExecuteBehaviorRequest,
  BehaviorExecutionResult,
  GenerateCodeRequest,
  GenerateBehaviorCodeRequest,
  CodeGenerationResult,
  SaveResultRequest,
  SaveResultResponse,
} from '../types/behavior';

// ──────────────────────────────────────
// API 기본 경로
// ──────────────────────────────────────

const BASE = '/api/v3/synapse/behaviors';

// ──────────────────────────────────────
// Behavior 실행
// ──────────────────────────────────────

/**
 * Behavior를 실행하고 결과를 반환한다.
 * 자동 수정(autoFixed)이 발생하면 사용자에게 알림을 보여준다.
 */
export async function executeBehavior(
  behaviorId: string,
  instanceData: Record<string, unknown>,
  options?: Record<string, unknown>,
): Promise<BehaviorExecutionResult> {
  try {
    const payload: ExecuteBehaviorRequest = { instanceData, options };
    const res = (await synapseApi.post(
      `${BASE}/${encodeURIComponent(behaviorId)}/execute`,
      payload,
    )) as unknown as BehaviorExecutionResult;

    // 자동 수정이 발생했으면 사용자에게 알림
    if (res.autoFixed) {
      toast.info(`코드가 자동 수정되었습니다. (${res.attempts ?? 1}회 시도)`);
    }

    return res;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : 'Behavior 실행에 실패했습니다.';
    toast.error(message);
    throw err;
  }
}

// ──────────────────────────────────────
// 범용 코드 생성
// ──────────────────────────────────────

/**
 * LLM을 이용하여 프롬프트 기반 코드를 생성한다.
 */
export async function generateCode(
  prompt: string,
  language = 'python',
  temperature?: number,
  context?: string,
): Promise<CodeGenerationResult> {
  try {
    const payload: GenerateCodeRequest = {
      prompt,
      language,
      ...(temperature !== undefined && { temperature }),
      ...(context !== undefined && { context }),
    };
    const res = (await synapseApi.post(
      `${BASE}/generate-code`,
      payload,
    )) as unknown as CodeGenerationResult;
    return res;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : '코드 생성에 실패했습니다.';
    toast.error(message);
    throw err;
  }
}

// ──────────────────────────────────────
// Behavior 전용 코드 생성
// ──────────────────────────────────────

/**
 * Behavior 메타데이터(이름, 입출력 필드)를 기반으로 코드를 생성한다.
 */
export async function generateBehaviorCode(
  params: GenerateBehaviorCodeRequest,
): Promise<CodeGenerationResult> {
  try {
    const res = (await synapseApi.post(
      `${BASE}/generate-behavior-code`,
      params,
    )) as unknown as CodeGenerationResult;
    return res;
  } catch (err) {
    const message =
      err instanceof Error
        ? err.message
        : 'Behavior 코드 생성에 실패했습니다.';
    toast.error(message);
    throw err;
  }
}

// ──────────────────────────────────────
// 실행 결과 DB 저장
// ──────────────────────────────────────

/**
 * Behavior 실행 결과를 지정된 테이블에 저장한다.
 */
export async function saveResult(
  tableName: string,
  data: Record<string, unknown>[],
  schemaName?: string,
): Promise<SaveResultResponse> {
  try {
    const payload: SaveResultRequest = {
      table_name: tableName,
      data,
      ...(schemaName && { schema_name: schemaName }),
    };
    const res = (await synapseApi.post(
      `${BASE}/save-result`,
      payload,
    )) as unknown as SaveResultResponse;

    toast.success(res.message || `${res.rows_inserted}건 저장 완료`);
    return res;
  } catch (err) {
    const message =
      err instanceof Error ? err.message : '결과 저장에 실패했습니다.';
    toast.error(message);
    throw err;
  }
}
