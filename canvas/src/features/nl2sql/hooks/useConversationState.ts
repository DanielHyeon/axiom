/**
 * useConversationState — 멀티턴 대화 상태 관리 훅
 *
 * Oracle /text2sql/react 엔드포인트의 conversation_state 토큰을 관리한다.
 * 각 턴의 result 스텝에서 반환되는 conversation_state를 저장하고,
 * 다음 턴 요청 시 자동으로 전달하여 맥락을 유지한다.
 *
 * sessionStorage를 사용하여 탭 새로고침 시에도 대화 상태가 유지된다.
 */
import { useState, useCallback, useEffect } from 'react';

// sessionStorage 키
const STORAGE_KEY = 'nl2sql:conversationState';
const TURN_COUNT_KEY = 'nl2sql:turnCount';

/** 멀티턴 대화 상태 반환 타입 */
export interface UseConversationStateReturn {
  /** 현재 conversation_state 토큰 (null이면 새 대화) */
  conversationState: string | null;
  /** result 스텝에서 받은 새 토큰 저장 */
  updateState: (newState: string) => void;
  /** 대화 초기화 — 새 대화 시작 */
  clearState: () => void;
  /** 현재 대화의 턴 수 */
  turnCount: number;
  /** 멀티턴 대화 진행 중 여부 (2턴 이상) */
  isMultiTurn: boolean;
  /** 턴 카운트 증가 — 질문 제출 시 호출 */
  incrementTurn: () => void;
}

/**
 * 멀티턴 대화 상태를 관리하는 훅.
 * sessionStorage에 영속화하여 탭 새로고침에도 상태를 유지한다.
 */
export function useConversationState(): UseConversationStateReturn {
  // sessionStorage에서 초기값 복원
  const [conversationState, setConversationState] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(STORAGE_KEY) || null;
    } catch {
      return null;
    }
  });

  const [turnCount, setTurnCount] = useState<number>(() => {
    try {
      const stored = sessionStorage.getItem(TURN_COUNT_KEY);
      return stored ? parseInt(stored, 10) : 0;
    } catch {
      return 0;
    }
  });

  // conversationState 변경 시 sessionStorage에 동기화
  useEffect(() => {
    try {
      if (conversationState) {
        sessionStorage.setItem(STORAGE_KEY, conversationState);
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch {
      // sessionStorage 접근 실패 시 무시
    }
  }, [conversationState]);

  // turnCount 변경 시 sessionStorage에 동기화
  useEffect(() => {
    try {
      sessionStorage.setItem(TURN_COUNT_KEY, String(turnCount));
    } catch {
      // sessionStorage 접근 실패 시 무시
    }
  }, [turnCount]);

  /** result 스텝에서 받은 새 토큰 저장 */
  const updateState = useCallback((newState: string) => {
    setConversationState(newState);
  }, []);

  /** 대화 초기화 — 새 대화 시작 */
  const clearState = useCallback(() => {
    setConversationState(null);
    setTurnCount(0);
  }, []);

  /** 턴 카운트 증가 */
  const incrementTurn = useCallback(() => {
    setTurnCount((prev) => prev + 1);
  }, []);

  return {
    conversationState,
    updateState,
    clearState,
    turnCount,
    isMultiTurn: turnCount >= 2,
    incrementTurn,
  };
}
