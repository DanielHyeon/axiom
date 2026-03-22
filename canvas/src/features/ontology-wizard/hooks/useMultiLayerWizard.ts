/**
 * Deep Agents 멀티레이어 온톨로지 생성 위자드 훅
 * SSE 스트리밍을 통해 실시간 진행 상황을 추적하고 위자드 흐름을 관리
 */
import { useState, useCallback, useRef, useEffect } from 'react';
import {
  streamMultiLayerGeneration,
  type MultiLayerRequest,
} from '../api/multiLayerApi';
import type {
  WizardStep,
  TargetLayer,
  LayerProgress,
  GenerationResult,
} from '../types/wizard';

/** 모든 5계층 레이어 기본값 */
const DEFAULT_LAYERS: TargetLayer[] = ['kpi', 'measure', 'driver', 'process', 'resource'];

/** 레이어 진행 상태 초기값 생성 */
function createInitialProgress(layers: string[]): Map<string, LayerProgress> {
  const map = new Map<string, LayerProgress>();
  for (const layer of layers) {
    map.set(layer, {
      layer,
      progress: 0,
      message: '',
      nodeCount: 0,
      relationCount: 0,
      status: 'pending',
    });
  }
  return map;
}

/** 위자드 훅 반환 타입 */
export interface MultiLayerWizardReturn {
  /** 현재 위자드 단계 */
  step: WizardStep;
  /** 레이어별 진행 상태 (레이어 이름 → 진행 정보) */
  layerProgress: Map<string, LayerProgress>;
  /** 최종 생성 결과 */
  result: GenerationResult | null;
  /** 생성 진행 중 여부 */
  isGenerating: boolean;
  /** 에러 메시지 */
  error: string | null;
  /** 생성 시작 */
  startGeneration: (inputText: string, domainHint?: string, targetLayers?: TargetLayer[]) => void;
  /** 위자드 초기화 (INPUT 단계로 복귀) */
  reset: () => void;
  /** 현재 생성 중단 */
  abort: () => void;
}

/**
 * 멀티레이어 온톨로지 생성 위자드 상태 관리 훅
 */
export function useMultiLayerWizard(): MultiLayerWizardReturn {
  const [step, setStep] = useState<WizardStep>('INPUT');
  const [layerProgress, setLayerProgress] = useState<Map<string, LayerProgress>>(new Map());
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // AbortController 참조 (취소용)
  const abortRef = useRef<AbortController | null>(null);

  // 언마운트 시 활성 스트림 정리 — 메모리 누수 방지
  useEffect(() => {
    return () => {
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
    };
  }, []);

  /** 레이어 진행 상태 업데이트 헬퍼 */
  const updateLayerProgress = useCallback(
    (layerName: string, updates: Partial<LayerProgress>) => {
      setLayerProgress((prev) => {
        const next = new Map(prev);
        const current = next.get(layerName);
        if (current) {
          next.set(layerName, { ...current, ...updates });
        }
        return next;
      });
    },
    [],
  );

  /** 생성 시작 */
  const startGeneration = useCallback(
    (inputText: string, domainHint?: string, targetLayers?: TargetLayer[]) => {
      // 이전 에러 초기화
      setError(null);
      setResult(null);

      const layers = targetLayers ?? DEFAULT_LAYERS;

      // 진행 상태 초기화
      setLayerProgress(createInitialProgress(layers));
      setStep('GENERATING');
      setIsGenerating(true);

      const request: MultiLayerRequest = {
        input_text: inputText,
        domain_hint: domainHint || undefined,
        target_layers: layers,
        parallel: true,
      };

      // AbortController를 먼저 생성 — 스트림 시작 전에 abort 가능하도록
      const controller = new AbortController();
      abortRef.current = controller;

      // SSE 스트림 시작
      streamMultiLayerGeneration(request, {
        onStart: (targetLayers) => {
          if (controller.signal.aborted) return;
          setLayerProgress(createInitialProgress(targetLayers));
        },

        onLayerProgress: (layer, progress, message) => {
          if (controller.signal.aborted) return;
          updateLayerProgress(layer, {
            progress,
            message,
            status: 'in_progress',
          });
        },

        onLayerComplete: (layer, nodeCount, relationCount) => {
          if (controller.signal.aborted) return;
          updateLayerProgress(layer, {
            progress: 100,
            message: '완료',
            nodeCount,
            relationCount,
            status: 'complete',
          });
        },

        onComplete: (generationResult) => {
          if (controller.signal.aborted) return;
          setResult(generationResult);
          setIsGenerating(false);
          setStep('REVIEW');
        },

        onError: (err) => {
          if (controller.signal.aborted) return;
          setError(err.message);
          setIsGenerating(false);
        },
      }).catch((err) => {
        if (controller.signal.aborted) return;
        setError((err as Error).message);
        setIsGenerating(false);
      });
    },
    [updateLayerProgress],
  );

  /** 위자드 초기화 */
  const reset = useCallback(() => {
    // 진행 중이면 먼저 중단
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStep('INPUT');
    setLayerProgress(new Map());
    setResult(null);
    setIsGenerating(false);
    setError(null);
  }, []);

  /** 생성 중단 */
  const abort = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setIsGenerating(false);
    setError('사용자에 의해 생성이 취소되었습니다.');
  }, []);

  return {
    step,
    layerProgress,
    result,
    isGenerating,
    error,
    startGeneration,
    reset,
    abort,
  };
}
