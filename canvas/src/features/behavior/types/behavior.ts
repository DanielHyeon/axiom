/**
 * BehaviorModel 실행 & 코드 생성 관련 타입 정의
 *
 * Synapse API v3 behaviors 엔드포인트의 요청/응답 타입을 정의한다.
 */

// ──────────────────────────────────────
// 실행 (Execute)
// ──────────────────────────────────────

/** Behavior 실행 요청 페이로드 */
export interface ExecuteBehaviorRequest {
  /** 인스턴스 데이터 (키-값 형태) */
  instanceData: Record<string, unknown>;
  /** 실행 옵션 (언어, 타임아웃 등) */
  options?: Record<string, unknown>;
}

/** Behavior 실행 결과 응답 */
export interface BehaviorExecutionResult {
  /** 실행 성공 여부 */
  success: boolean;
  /** 실행 결과 데이터 */
  result: unknown;
  /** Behavior 이름 */
  behaviorName: string;
  /** 결과 메시지 */
  message: string;
  /** 실행된 코드 (자동 수정 시 반환) */
  code?: string;
  /** 자동 수정 여부 */
  autoFixed?: boolean;
  /** 자동 수정 시도 횟수 */
  attempts?: number;
}

// ──────────────────────────────────────
// 코드 생성 (Code Generation)
// ──────────────────────────────────────

/** 범용 코드 생성 요청 */
export interface GenerateCodeRequest {
  /** LLM 프롬프트 */
  prompt: string;
  /** 생성할 언어 (기본: python) */
  language?: string;
  /** LLM 온도 파라미터 (0.0~2.0) */
  temperature?: number;
  /** 최대 출력 토큰 수 */
  max_output_tokens?: number;
  /** 추가 컨텍스트 (스키마, 필드 정보 등) */
  context?: string;
}

/** Behavior 전용 코드 생성 요청 */
export interface GenerateBehaviorCodeRequest {
  /** Behavior 이름 */
  behavior_name: string;
  /** 입력 필드 목록 */
  input_fields: string[];
  /** 출력 필드 */
  output_field: string;
  /** Behavior 설명 */
  description: string;
  /** 생성할 언어 (기본: python) */
  language?: string;
}

/** 코드 생성 응답 */
export interface CodeGenerationResult {
  /** 생성 성공 여부 */
  success: boolean;
  /** 생성된 코드 문자열 */
  code: string;
  /** 코드 언어 */
  language: string;
}

// ──────────────────────────────────────
// 결과 저장 (Save Result)
// ──────────────────────────────────────

/** 결과 저장 요청 */
export interface SaveResultRequest {
  /** 저장할 테이블 이름 */
  table_name: string;
  /** 스키마 이름 (기본: public) */
  schema_name?: string;
  /** 저장할 데이터 행 배열 */
  data: Record<string, unknown>[];
}

/** 결과 저장 응답 */
export interface SaveResultResponse {
  /** 저장 성공 여부 */
  success: boolean;
  /** 삽입된 행 수 */
  rows_inserted: number;
  /** 결과 메시지 */
  message: string;
}
