/**
 * useNl2SqlChat — NL2SQL 채팅 상태 관리 훅
 *
 * 이 훅은 채팅 메시지, 스트리밍, HIL(사람-개입), 에러 상태를 한 곳에서 관리한다.
 * 페이지 컴포넌트가 얇아지도록 모든 비즈니스 로직을 여기에 모아둠.
 */
import { useState, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import {
  postReactStream,
  postAsk,
  type AskResponse,
  type ReactStreamStep,
} from '@/features/nl2sql/api/oracleNl2sqlApi';
import { AppError } from '@/lib/api/errors';
import type { ChartConfig, ExecutionMetadata, HilRequest, HilResponse } from '@/features/nl2sql/types/nl2sql';

// === 채팅 메시지 타입 ===
export type ChatMessage =
  | { role: 'user'; content: string }
  | {
      role: 'assistant';
      content: string;
      sql?: string;
      result?: AskResponse['data'];
      error?: string;
      streaming?: boolean;
      /** HIL 질문 메시지 — 경고 스타일로 표시 */
      isHilQuestion?: boolean;
    };

/** 행 제한 옵션 목록 */
export const ROW_LIMIT_OPTIONS = [100, 500, 1000, 2000, 5000, 10000];

// === 훅 파라미터 ===
interface UseNl2SqlChatParams {
  /** 선택된 데이터소스 ID */
  datasourceId: string;
  /** URL에서 가져온 case ID */
  caseId?: string;
  /** 행 제한 수 */
  rowLimit: number;
  /** 쿼리 모드: react(스트림) 또는 ask(단발 요청) */
  mode: 'react' | 'ask';
}

// === 훅 반환 타입 ===
export interface UseNl2SqlChatReturn {
  /** 채팅 메시지 목록 */
  messages: ChatMessage[];
  /** ReAct 스트림 단계 목록 */
  reactSteps: ReactStreamStep[];
  /** 최종 결과 데이터 */
  finalResult: AskResponse['data'] | null;
  /** 에러 메시지 */
  error: string | null;
  /** 로딩 중인지 여부 */
  loading: boolean;
  /** HIL 요청 (에이전트가 사용자에게 질문하는 경우) */
  hilRequest: HilRequest | null;
  /** HIL 제출 중 여부 */
  hilSubmitting: boolean;

  /** 질문 제출 — 폼에서 호출 */
  submitQuestion: (question: string) => Promise<void>;
  /** HIL 응답 제출 — 사용자가 에이전트 질문에 답할 때 */
  handleHilSubmit: (response: HilResponse) => Promise<void>;
  /** HIL 취소 — 에이전트 질문을 무시할 때 */
  handleHilCancel: () => void;
  /** 전체 초기화 — 새 대화 시작 */
  handleClear: () => void;

  /** 차트 설정 (자동 감지 포함) */
  effectiveChartConfig: ChartConfig | null;
  /** 결과 컬럼 목록 */
  resultColumns: { name: string; type: string }[];
  /** 결과 행 목록 */
  resultRows: unknown[][];
}

export function useNl2SqlChat({
  datasourceId,
  caseId,
  rowLimit,
  mode,
}: UseNl2SqlChatParams): UseNl2SqlChatReturn {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  // === 핵심 상태 ===
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [reactSteps, setReactSteps] = useState<ReactStreamStep[]>([]);
  const [finalResult, setFinalResult] = useState<AskResponse['data'] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // === HIL 상태 ===
  const [hilRequest, setHilRequest] = useState<HilRequest | null>(null);
  const [hilSubmitting, setHilSubmitting] = useState(false);

  // === Ref (렌더에 영향 안 주는 값) ===
  const abortRef = useRef<AbortController | null>(null);
  const currentQuestionRef = useRef<string>('');

  // === 전체 초기화 ===
  const handleClear = useCallback(() => {
    setMessages([]);
    setFinalResult(null);
    setReactSteps([]);
    setError(null);
    setHilRequest(null);
    setHilSubmitting(false);
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setLoading(false);
  }, []);

  // === NDJSON 스트림 콜백 — ReAct 단계별 처리 + HIL 이벤트 감지 ===
  const buildStreamCallbacks = useCallback(
    (question: string) => ({
      onMessage: (step: ReactStreamStep) => {
        setReactSteps((prev) => [...prev, step]);

        // HIL: needs_user_input 이벤트 처리
        if (step.step === 'needs_user_input' && step.data) {
          const d = step.data as Record<string, unknown>;
          const hilReq: HilRequest = {
            type: (d.type as HilRequest['type']) || 'text',
            question: String(d.question_to_user ?? d.question ?? t('nl2sql.hilNeedInfo')),
            options: d.options as HilRequest['options'],
            context: d.context ? String(d.context) : d.partial_sql ? String(d.partial_sql) : undefined,
            session_state: String(d.session_state ?? ''),
          };
          setHilRequest(hilReq);
          // 에이전트 질문을 채팅 히스토리에 추가
          setMessages((prev) => {
            const rest = prev.slice(0, -1); // 스트리밍 메시지 제거
            return [
              ...rest,
              {
                role: 'assistant',
                content: hilReq.question,
                isHilQuestion: true,
              },
            ];
          });
          setLoading(false); // 스트림이 일시 정지됨 — 로딩 해제
          return;
        }

        // 결과 이벤트
        if (step.step === 'result' && step.data) {
          const d = step.data as Record<string, unknown>;
          const table = d.result as
            | { columns: { name: string; type: string }[]; rows: unknown[][]; row_count: number }
            | undefined;
          if (table || d.sql) {
            const resultData = {
              question,
              sql: String(d.sql ?? ''),
              result: table ?? { columns: [], rows: [], row_count: 0 },
              summary: d.summary != null ? String(d.summary) : null,
              visualization:
                d.visualization != null
                  ? (d.visualization as { chart_type: string; config?: Record<string, string> })
                  : null,
              metadata: d.metadata as ExecutionMetadata | undefined,
            };
            setFinalResult(resultData);
            setMessages((prev) => {
              const rest = prev.slice(0, -1);
              return [
                ...rest,
                {
                  role: 'assistant',
                  content: resultData.summary ?? t('nl2sql.queryComplete'),
                  sql: resultData.sql,
                  result: resultData,
                },
              ];
            });
            queryClient.invalidateQueries({ queryKey: ['nl2sql', 'history'] });
          }
        }

        // 에러 이벤트
        if (step.step === 'error' && step.data) {
          const msg =
            (step.data as { message?: string }).message ?? t('nl2sql.reactError');
          setError(msg);
          setMessages((prev) => {
            const rest = prev.slice(0, -1);
            return [...rest, { role: 'assistant', content: msg, error: msg }];
          });
        }
      },
      onComplete: () => setLoading(false),
      onError: (err: Error) => {
        const msg = err.message || t('nl2sql.streamFailed');
        setError(msg);
        setMessages((prev) => {
          const rest = prev.slice(0, -1);
          return [...rest, { role: 'assistant', content: msg, error: msg }];
        });
        setLoading(false);
      },
    }),
    [t, queryClient],
  );

  // === 질문 제출 ===
  const submitQuestion = useCallback(
    async (question: string) => {
      if (!question || loading || !datasourceId) return;

      // 질문 기록 (HIL 재개 시 참조)
      currentQuestionRef.current = question;

      setLoading(true);
      setError(null);
      setFinalResult(null);
      setReactSteps([]);
      setHilRequest(null);
      setMessages((prev) => [...prev, { role: 'user', content: question }]);

      if (mode === 'ask') {
        // 단일 요청 모드
        try {
          const res = await postAsk(question, datasourceId, { case_id: caseId, row_limit: rowLimit });
          if (res.success && res.data) {
            const d = res.data;
            setFinalResult(d);
            setMessages((prev) => [
              ...prev,
              {
                role: 'assistant',
                content: d.summary ?? t('nl2sql.queryComplete'),
                sql: d.sql,
                result: d,
              },
            ]);
            queryClient.invalidateQueries({ queryKey: ['nl2sql', 'history'] });
          } else {
            const errMsg = res.error?.message ?? t('nl2sql.requestFailed');
            setError(errMsg);
            setMessages((prev) => [...prev, { role: 'assistant', content: errMsg, error: errMsg }]);
          }
        } catch (err) {
          const errMsg =
            err instanceof AppError
              ? err.userMessage
              : (err as Error).message || t('nl2sql.oracleApiFailed');
          setError(errMsg);
          setMessages((prev) => [...prev, { role: 'assistant', content: errMsg, error: errMsg }]);
        } finally {
          setLoading(false);
        }
        return;
      }

      // ReAct 스트림 모드
      setMessages((prev) => [...prev, { role: 'assistant', content: '', streaming: true }]);

      try {
        abortRef.current = await postReactStream(
          question,
          datasourceId,
          buildStreamCallbacks(question),
          { case_id: caseId, row_limit: rowLimit },
        );
      } catch (err) {
        const errMsg =
          err instanceof AppError
            ? err.userMessage
            : (err as Error).message || t('nl2sql.startFailed');
        setError(errMsg);
        setMessages((prev) => {
          const rest = prev.slice(0, -1);
          return [...rest, { role: 'assistant', content: errMsg, error: errMsg }];
        });
        setLoading(false);
      }
    },
    [datasourceId, caseId, rowLimit, mode, loading, t, queryClient, buildStreamCallbacks],
  );

  // === HIL 응답 제출 — 세션을 이어서 ReAct 스트림 재개 ===
  const handleHilSubmit = useCallback(
    async (response: HilResponse) => {
      setHilSubmitting(true);
      setHilRequest(null);
      setLoading(true);

      // 사용자 답변을 채팅 히스토리에 추가
      setMessages((prev) => [
        ...prev,
        { role: 'user', content: response.user_response },
        { role: 'assistant', content: '', streaming: true },
      ]);

      try {
        abortRef.current = await postReactStream(
          currentQuestionRef.current,
          datasourceId,
          buildStreamCallbacks(currentQuestionRef.current),
          {
            case_id: caseId,
            row_limit: rowLimit,
            session_state: response.session_state,
            user_response: response.user_response,
          },
        );
      } catch (err) {
        const errMsg =
          err instanceof AppError
            ? err.userMessage
            : (err as Error).message || t('nl2sql.hilResumeFailed');
        setError(errMsg);
        setMessages((prev) => {
          const rest = prev.slice(0, -1);
          return [...rest, { role: 'assistant', content: errMsg, error: errMsg }];
        });
        setLoading(false);
      } finally {
        setHilSubmitting(false);
      }
    },
    [datasourceId, caseId, rowLimit, t, buildStreamCallbacks],
  );

  // === HIL 취소 — 현재 세션을 중단 ===
  const handleHilCancel = useCallback(() => {
    setHilRequest(null);
    setLoading(false);
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  // === 파생 상태: 차트 설정 (자동 감지 포함) ===
  const resultColumns = finalResult?.result?.columns ?? [];
  const resultRows = finalResult?.result?.rows ?? [];

  const chartConfig: ChartConfig | null =
    finalResult?.visualization?.chart_type && finalResult.visualization.config
      ? {
          chart_type: finalResult.visualization.chart_type as ChartConfig['chart_type'],
          config: finalResult.visualization.config,
        }
      : null;

  // 단일 숫자 결과이면 KPI 카드로 자동 감지
  const effectiveChartConfig: ChartConfig | null = (() => {
    if (chartConfig) return chartConfig;
    if (
      finalResult?.result &&
      finalResult.result.columns.length === 1 &&
      finalResult.result.rows.length === 1 &&
      typeof finalResult.result.rows[0]?.[0] === 'number'
    ) {
      return {
        chart_type: 'kpi_card' as ChartConfig['chart_type'],
        config: { value_column: finalResult.result.columns[0].name },
      };
    }
    return null;
  })();

  return {
    messages,
    reactSteps,
    finalResult,
    error,
    loading,
    hilRequest,
    hilSubmitting,
    submitQuestion,
    handleHilSubmit,
    handleHilCancel,
    handleClear,
    effectiveChartConfig,
    resultColumns,
    resultRows,
  };
}
