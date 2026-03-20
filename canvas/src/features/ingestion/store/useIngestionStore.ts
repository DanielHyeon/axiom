/**
 * 데이터 수집 UI 상태 관리 (Zustand)
 * 업로드 파일 목록, 파이프라인 선택 상태, 미리보기 등 클라이언트 UI 상태를 관리한다.
 */

import { create } from 'zustand';
import type {
  UploadFile,
  Pipeline,
  FilePreviewData,
  IngestionRecord,
} from '../types/ingestion';

// ============================================================================
// 탭 타입
// ============================================================================

/** 데이터 수집 페이지 탭 */
export type IngestionTab = 'upload' | 'pipelines' | 'history';

// ============================================================================
// 스토어 인터페이스
// ============================================================================

interface IngestionState {
  // --- 탭 ---
  /** 현재 활성 탭 */
  activeTab: IngestionTab;
  setActiveTab: (tab: IngestionTab) => void;

  // --- 파일 업로드 ---
  /** 업로드 파일 목록 (클라이언트 상태) */
  uploadFiles: UploadFile[];
  /** 파일 추가 */
  addFiles: (files: UploadFile[]) => void;
  /** 파일 진행률 업데이트 */
  updateFileProgress: (id: string, progress: number) => void;
  /** 파일 상태 업데이트 */
  updateFileStatus: (id: string, status: UploadFile['status'], error?: string) => void;
  /** 파일 제거 */
  removeFile: (id: string) => void;
  /** 모든 파일 초기화 */
  clearFiles: () => void;

  // --- 파일 미리보기 ---
  /** 현재 미리보기 중인 파일 ID */
  previewFileId: string | null;
  /** 미리보기 데이터 */
  previewData: FilePreviewData | null;
  setPreview: (fileId: string | null, data: FilePreviewData | null) => void;

  // --- 파이프라인 ---
  /** 선택된 파이프라인 ID */
  selectedPipelineId: string | null;
  setSelectedPipelineId: (id: string | null) => void;

  // --- 수집 이력 필터 ---
  /** 이력 필터 — 파이프라인 ID */
  historyFilterPipelineId: string | null;
  setHistoryFilterPipelineId: (id: string | null) => void;

  // --- 전역 로딩 ---
  /** 업로드 진행 중 여부 */
  isUploading: boolean;
  setIsUploading: (v: boolean) => void;
}

// ============================================================================
// 스토어 생성
// ============================================================================

export const useIngestionStore = create<IngestionState>((set) => ({
  // 탭
  activeTab: 'upload',
  setActiveTab: (tab) => set({ activeTab: tab }),

  // 파일 업로드
  uploadFiles: [],
  addFiles: (files) =>
    set((state) => ({ uploadFiles: [...state.uploadFiles, ...files] })),
  updateFileProgress: (id, progress) =>
    set((state) => ({
      uploadFiles: state.uploadFiles.map((f) =>
        f.id === id ? { ...f, progress } : f,
      ),
    })),
  updateFileStatus: (id, status, error) =>
    set((state) => ({
      uploadFiles: state.uploadFiles.map((f) =>
        f.id === id ? { ...f, status, error } : f,
      ),
    })),
  removeFile: (id) =>
    set((state) => ({
      uploadFiles: state.uploadFiles.filter((f) => f.id !== id),
    })),
  clearFiles: () => set({ uploadFiles: [], previewFileId: null, previewData: null }),

  // 파일 미리보기
  previewFileId: null,
  previewData: null,
  setPreview: (fileId, data) => set({ previewFileId: fileId, previewData: data }),

  // 파이프라인
  selectedPipelineId: null,
  setSelectedPipelineId: (id) => set({ selectedPipelineId: id }),

  // 이력 필터
  historyFilterPipelineId: null,
  setHistoryFilterPipelineId: (id) => set({ historyFilterPipelineId: id }),

  // 전역 로딩
  isUploading: false,
  setIsUploading: (v) => set({ isUploading: v }),
}));
