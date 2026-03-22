/**
 * Behavior 피처 슬라이스 — 배럴 익스포트
 *
 * BehaviorModel 실행, 코드 생성, 결과 저장 기능을 외부에 노출한다.
 */

// API
export {
  executeBehavior,
  generateCode,
  generateBehaviorCode,
  saveResult,
} from './api/behaviorApi';

// 타입
export type {
  ExecuteBehaviorRequest,
  BehaviorExecutionResult,
  GenerateCodeRequest,
  GenerateBehaviorCodeRequest,
  CodeGenerationResult,
  SaveResultRequest,
  SaveResultResponse,
} from './types/behavior';

// 훅
export { useBehaviorExecution } from './hooks/useBehaviorExecution';

// 컴포넌트
export { BehaviorExecutionPanel } from './components/BehaviorExecutionPanel';
export { CodeViewer } from './components/CodeViewer';
