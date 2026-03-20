/**
 * 파일 업로드 상태 관리 훅
 * 드래그&드롭으로 받은 File[]을 Weaver API에 업로드하고 진행률을 추적한다.
 */

import { useCallback } from 'react';
import { toast } from 'sonner';
import { useIngestionStore } from '../store/useIngestionStore';
import { uploadFile } from '../api/ingestionApi';
import type { UploadFile, UploadMetadata } from '../types/ingestion';

/** 파일 크기 제한 (100MB) */
const MAX_FILE_SIZE = 100 * 1024 * 1024;

/** 허용 확장자 */
const ALLOWED_EXTENSIONS = ['.csv', '.json', '.xlsx', '.xls', '.parquet', '.tsv'];

/** 고유 ID 생성 */
function generateId(): string {
  return `upload-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/** 파일 확장자 추출 */
function getExtension(name: string): string {
  const idx = name.lastIndexOf('.');
  return idx >= 0 ? name.slice(idx).toLowerCase() : '';
}

/** 파일 크기를 사람이 읽기 좋은 형태로 변환 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export function useFileUpload() {
  const {
    uploadFiles,
    addFiles,
    updateFileProgress,
    updateFileStatus,
    removeFile,
    clearFiles,
    isUploading,
    setIsUploading,
  } = useIngestionStore();

  /**
   * 파일 유효성 검사.
   * 크기/확장자 체크 후 유효한 파일 목록과 거부된 파일 목록을 반환.
   */
  const validateFiles = useCallback((files: File[]): { valid: File[]; rejected: string[] } => {
    const valid: File[] = [];
    const rejected: string[] = [];

    // MIME 타입 허용 목록 (defense-in-depth)
    const ALLOWED_MIMES = new Set([
      'text/csv', 'application/json', 'text/tab-separated-values',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel', 'application/octet-stream', '',
    ]);

    for (const file of files) {
      // 경로 순회 방지: 파일명에서 디렉토리 구분자 제거
      const safeName = file.name.replace(/^.*[\\/]/, '');
      if (safeName !== file.name) {
        rejected.push(`${file.name}: 파일명에 경로가 포함되어 있습니다`);
        continue;
      }
      const ext = getExtension(safeName);
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        rejected.push(`${safeName}: 지원하지 않는 파일 형식입니다 (${ext})`);
        continue;
      }
      // MIME 타입 검증 (빈 문자열은 브라우저가 판별 못한 경우 허용)
      if (file.type && !ALLOWED_MIMES.has(file.type)) {
        rejected.push(`${safeName}: MIME 타입이 허용되지 않습니다 (${file.type})`);
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        rejected.push(`${safeName}: 파일 크기가 100MB를 초과합니다`);
        continue;
      }
      valid.push(file);
    }

    return { valid, rejected };
  }, []);

  /**
   * 파일을 스토어에 등록하고 업로드를 시작한다.
   */
  const startUpload = useCallback(
    async (files: File[], metadata: UploadMetadata = {}) => {
      const { valid, rejected } = validateFiles(files);

      // 거부된 파일 알림
      if (rejected.length > 0) {
        rejected.forEach((msg) => toast.error(msg));
      }

      if (valid.length === 0) return;

      // 스토어에 pending 상태로 등록
      const uploadEntries: UploadFile[] = valid.map((file) => ({
        id: generateId(),
        name: file.name,
        size: file.size,
        type: file.type,
        status: 'pending' as const,
        progress: 0,
      }));
      addFiles(uploadEntries);
      setIsUploading(true);

      // 순차 업로드
      for (let i = 0; i < valid.length; i++) {
        const entry = uploadEntries[i];
        const file = valid[i];

        updateFileStatus(entry.id, 'uploading');

        try {
          const res = await uploadFile(file, metadata, (percent) => {
            updateFileProgress(entry.id, percent);
          });
          updateFileStatus(entry.id, 'completed');
          updateFileProgress(entry.id, 100);
        } catch (err) {
          const msg = err instanceof Error ? err.message : '업로드 실패';
          updateFileStatus(entry.id, 'failed', msg);
          toast.error(`${file.name}: ${msg}`);
        }
      }

      setIsUploading(false);

      // 성공 파일 수 알림
      const successCount = uploadEntries.filter(
        (e) => useIngestionStore.getState().uploadFiles.find((f) => f.id === e.id)?.status === 'completed',
      ).length;
      if (successCount > 0) {
        toast.success(`${successCount}개 파일 업로드 완료`);
      }
    },
    [addFiles, updateFileProgress, updateFileStatus, setIsUploading, validateFiles],
  );

  return {
    /** 현재 업로드 파일 목록 */
    files: uploadFiles,
    /** 업로드 진행 중 여부 */
    isUploading,
    /** 업로드 시작 */
    startUpload,
    /** 개별 파일 제거 */
    removeFile,
    /** 전체 파일 초기화 */
    clearFiles,
    /** 파일 유효성 검사 */
    validateFiles,
    /** 허용 확장자 목록 */
    allowedExtensions: ALLOWED_EXTENSIONS,
    /** 최대 파일 크기 */
    maxFileSize: MAX_FILE_SIZE,
  };
}
