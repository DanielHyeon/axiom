/**
 * useBehaviorExecution — Behavior 실행 & 코드 생성 통합 훅
 *
 * 세 가지 비동기 작업의 로딩 상태와 결과를 관리한다:
 * 1. Behavior 실행 (execute)
 * 2. 코드 생성 (generateCode)
 * 3. 결과 저장 (saveResult)
 */

import { useState, useCallback } from 'react';
import {
  executeBehavior as apiExecute,
  generateCode as apiGenerateCode,
  saveResult as apiSaveResult,
} from '../api/behaviorApi';
import type {
  BehaviorExecutionResult,
  CodeGenerationResult,
  SaveResultResponse,
} from '../types/behavior';

// ──────────────────────────────────────
// 훅 반환 타입
// ──────────────────────────────────────

interface UseBehaviorExecutionReturn {
  /** Behavior 실행 */
  execute: (
    behaviorId: string,
    instanceData: Record<string, unknown>,
    options?: Record<string, unknown>,
  ) => Promise<BehaviorExecutionResult>;
  /** LLM 코드 생성 */
  generateCode: (
    prompt: string,
    language?: string,
    temperature?: number,
  ) => Promise<CodeGenerationResult>;
  /** 실행 결과 DB 저장 */
  saveResult: (
    tableName: string,
    data: Record<string, unknown>[],
    schemaName?: string,
  ) => Promise<SaveResultResponse>;
  /** 실행 중 여부 */
  isExecuting: boolean;
  /** 코드 생성 중 여부 */
  isGenerating: boolean;
  /** 저장 중 여부 */
  isSaving: boolean;
  /** 마지막 실행 결과 */
  lastResult: BehaviorExecutionResult | null;
  /** 마지막 생성된 코드 */
  lastCode: CodeGenerationResult | null;
  /** 마지막 에러 메시지 */
  lastError: string | null;
  /** 상태 초기화 */
  reset: () => void;
}

// ──────────────────────────────────────
// 훅 구현
// ──────────────────────────────────────

export function useBehaviorExecution(): UseBehaviorExecutionReturn {
  // 로딩 상태
  const [isExecuting, setIsExecuting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // 결과 상태
  const [lastResult, setLastResult] = useState<BehaviorExecutionResult | null>(null);
  const [lastCode, setLastCode] = useState<CodeGenerationResult | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  /** Behavior 실행 — 결과를 상태에 저장하고 반환한다 */
  const execute = useCallback(
    async (
      behaviorId: string,
      instanceData: Record<string, unknown>,
      options?: Record<string, unknown>,
    ): Promise<BehaviorExecutionResult> => {
      setIsExecuting(true);
      setLastError(null);
      try {
        const result = await apiExecute(behaviorId, instanceData, options);
        setLastResult(result);
        return result;
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : 'Behavior 실행에 실패했습니다.';
        setLastError(msg);
        throw err;
      } finally {
        setIsExecuting(false);
      }
    },
    [],
  );

  /** LLM 코드 생성 — 생성된 코드를 상태에 저장하고 반환한다 */
  const generateCode = useCallback(
    async (
      prompt: string,
      language = 'python',
      temperature?: number,
    ): Promise<CodeGenerationResult> => {
      setIsGenerating(true);
      setLastError(null);
      try {
        const result = await apiGenerateCode(prompt, language, temperature);
        setLastCode(result);
        return result;
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : '코드 생성에 실패했습니다.';
        setLastError(msg);
        throw err;
      } finally {
        setIsGenerating(false);
      }
    },
    [],
  );

  /** 실행 결과를 DB 테이블에 저장한다 */
  const saveResult = useCallback(
    async (
      tableName: string,
      data: Record<string, unknown>[],
      schemaName?: string,
    ): Promise<SaveResultResponse> => {
      setIsSaving(true);
      setLastError(null);
      try {
        const result = await apiSaveResult(tableName, data, schemaName);
        return result;
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : '결과 저장에 실패했습니다.';
        setLastError(msg);
        throw err;
      } finally {
        setIsSaving(false);
      }
    },
    [],
  );

  /** 모든 상태를 초기값으로 되돌린다 */
  const reset = useCallback(() => {
    setLastResult(null);
    setLastCode(null);
    setLastError(null);
  }, []);

  return {
    execute,
    generateCode,
    saveResult,
    isExecuting,
    isGenerating,
    isSaving,
    lastResult,
    lastCode,
    lastError,
    reset,
  };
}
