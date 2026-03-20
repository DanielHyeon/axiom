/**
 * 데이터 수집/파이프라인 관련 TypeScript 타입 정의
 * KAIR UploadTab + PipelineControlPanel 기능을 Axiom 패턴으로 이식
 */

// ============================================================================
// 파일 업로드 관련 타입
// ============================================================================

/** 업로드 파일 상태 */
export type UploadFileStatus =
  | 'pending'
  | 'uploading'
  | 'processing'
  | 'completed'
  | 'failed';

/** 업로드 파일 항목 */
export interface UploadFile {
  /** 클라이언트 생성 고유 ID */
  id: string;
  /** 파일 이름 (경로 포함 가능) */
  name: string;
  /** 파일 크기 (bytes) */
  size: number;
  /** MIME 타입 */
  type: string;
  /** 업로드 상태 */
  status: UploadFileStatus;
  /** 업로드 진행률 (0~100) */
  progress: number;
  /** 에러 메시지 (실패 시) */
  error?: string;
  /** 업로드 완료 시 서버 응답 파일 ID */
  remoteId?: string;
}

/** 파일 업로드 요청 메타데이터 */
export interface UploadMetadata {
  /** 대상 데이터소스 이름 */
  datasourceName?: string;
  /** 파일 포맷 힌트 */
  format?: 'csv' | 'json' | 'excel' | 'parquet';
  /** 구분자 (CSV용) */
  delimiter?: string;
  /** 인코딩 */
  encoding?: string;
}

/** 파일 미리보기 데이터 (CSV/JSON 파싱 결과) */
export interface FilePreviewData {
  /** 컬럼 이름 목록 */
  columns: string[];
  /** 미리보기 행 데이터 (최대 20행) */
  rows: Record<string, unknown>[];
  /** 전체 행 수 */
  totalRows: number;
  /** 파일 포맷 */
  format: string;
}

// ============================================================================
// 파이프라인 관련 타입
// ============================================================================

/** 파이프라인 상태 */
export type PipelineStatus = 'idle' | 'running' | 'paused' | 'completed' | 'failed';

/** 파이프라인 단계 유형 */
export type PipelineStepType = 'extract' | 'transform' | 'load' | 'validate';

/** 파이프라인 단계 상태 */
export type PipelineStepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped';

/** 파이프라인 단계 */
export interface PipelineStep {
  /** 단계 이름 */
  name: string;
  /** 단계 유형 (ETL + Validate) */
  type: PipelineStepType;
  /** 단계 상태 */
  status: PipelineStepStatus;
  /** 소요 시간 (ms) */
  duration?: number;
  /** 처리된 행 수 */
  rowsProcessed?: number;
  /** 에러 메시지 */
  error?: string;
}

/** 파이프라인 */
export interface Pipeline {
  /** 파이프라인 고유 ID */
  id: string;
  /** 파이프라인 이름 */
  name: string;
  /** 연결된 데이터소스 ID */
  datasourceId: string;
  /** 파이프라인 상태 */
  status: PipelineStatus;
  /** ETL 단계 목록 */
  steps: PipelineStep[];
  /** 마지막 실행 시각 (ISO string) */
  lastRunAt?: string;
  /** 스케줄 (cron 표현식) */
  schedule?: string;
  /** 생성 시각 */
  createdAt?: string;
  /** 수정 시각 */
  updatedAt?: string;
}

// ============================================================================
// 수집 이력 관련 타입
// ============================================================================

/** 수집 이력 항목 */
export interface IngestionRecord {
  /** 이력 ID */
  id: string;
  /** 파이프라인 ID */
  pipelineId?: string;
  /** 파이프라인 이름 */
  pipelineName?: string;
  /** 대상 데이터소스 */
  datasource: string;
  /** 실행 상태 */
  status: 'running' | 'completed' | 'failed';
  /** 처리된 행 수 */
  rowsProcessed: number;
  /** 소요 시간 (ms) */
  duration: number;
  /** 시작 시각 */
  startedAt: string;
  /** 완료 시각 */
  completedAt?: string;
  /** 에러 메시지 */
  error?: string;
}

// ============================================================================
// API 응답 타입
// ============================================================================

/** 파일 업로드 응답 */
export interface UploadResponse {
  /** 업로드된 파일 ID */
  fileId: string;
  /** 파일 이름 */
  fileName: string;
  /** 파일 크기 */
  size: number;
  /** 미리보기 (첫 몇 행) */
  preview?: FilePreviewData;
}

/** 파이프라인 목록 응답 */
export interface PipelineListResponse {
  pipelines: Pipeline[];
  total: number;
}

/** 파이프라인 실행 상태 응답 */
export interface PipelineStatusResponse {
  pipelineId: string;
  status: PipelineStatus;
  steps: PipelineStep[];
  startedAt?: string;
  completedAt?: string;
}

/** 수집 이력 목록 응답 */
export interface IngestionHistoryResponse {
  records: IngestionRecord[];
  total: number;
}
