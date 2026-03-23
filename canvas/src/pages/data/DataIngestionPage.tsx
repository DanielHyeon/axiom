/**
 * DataIngestionPage — 데이터 수집 메인 페이지
 * 업로드 탭 + 파이프라인 탭 + 수집 이력 탭으로 구성.
 * KAIR UploadTab + PipelineControlPanel 기능을 통합한 Axiom 데이터 수집 UI.
 */

import React, { useEffect, useState } from 'react';
import { Upload, Zap, History, Database } from 'lucide-react';
import { FileDropZone } from '@/features/ingestion/components/FileDropZone';
import { UploadProgress } from '@/features/ingestion/components/UploadProgress';
import { FilePreview } from '@/features/ingestion/components/FilePreview';
import { PipelineControlPanel } from '@/features/ingestion/components/PipelineControlPanel';
import { IngestionHistory } from '@/features/ingestion/components/IngestionHistory';
import { DataSourceManager } from '@/features/ingestion/components/DataSourceManager';
import { ConnectionTestDialog } from '@/features/ingestion/components/ConnectionTestDialog';
import { useFileUpload } from '@/features/ingestion/hooks/useFileUpload';
import { usePipelines } from '@/features/ingestion/hooks/usePipelines';
import { useIngestionStore, type IngestionTab } from '@/features/ingestion/store/useIngestionStore';
import { useDatasources } from '@/features/datasource/hooks/useDatasources';

/** 탭 설정 */
const TAB_CONFIG: { key: IngestionTab; label: string; icon: React.ElementType }[] = [
  { key: 'upload', label: '파일 업로드', icon: Upload },
  { key: 'pipelines', label: 'ETL 파이프라인', icon: Zap },
  { key: 'history', label: '수집 이력', icon: History },
];

export const DataIngestionPage: React.FC = () => {
  // 스토어
  const { activeTab, setActiveTab, previewFileId, previewData, setPreview } =
    useIngestionStore();

  // 파일 업로드 훅
  const { files, isUploading, startUpload, removeFile, clearFiles } = useFileUpload();

  // 파이프라인 훅
  const {
    pipelines,
    loading: pipelinesLoading,
    runPipeline,
    stopPipeline,
    deletePipeline,
    history,
    historyLoading,
    fetchHistory,
  } = usePipelines();

  // 기존 데이터소스 훅 (대상 선택용)
  const { datasources, loading: dsLoading, refetch: dsRefetch } = useDatasources();

  // 대상 데이터소스 선택
  const [selectedDs, setSelectedDs] = useState<string | null>(null);

  // 연결 테스트 다이얼로그
  const [testDialogDs, setTestDialogDs] = useState<string | null>(null);

  // 이력 탭 진입 시 자동 로드
  useEffect(() => {
    if (activeTab === 'history') {
      fetchHistory();
    }
  }, [activeTab, fetchHistory]);

  /** 파일 드롭 핸들러 */
  const handleFilesDrop = (droppedFiles: File[]) => {
    startUpload(droppedFiles, {
      datasourceName: selectedDs ?? undefined,
    });
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 페이지 헤더 */}
      <div className="px-4 md:px-8 lg:px-12 pt-4 md:pt-8 pb-3 md:pb-4 shrink-0">
        <div className="flex items-start justify-between">
          <div className="space-y-1.5">
            <h1 className="text-2xl md:text-4xl lg:text-5xl font-semibold tracking-tight text-foreground font-heading">
              데이터 수집
            </h1>
            <p className="text-[12px] md:text-[13px] text-muted-foreground font-mono">
              파일 업로드 및 ETL 파이프라인을 통해 데이터를 수집합니다
            </p>
          </div>
        </div>
      </div>

      {/* 탭 헤더 */}
      <div className="px-4 md:px-8 lg:px-12 shrink-0 border-b border-border overflow-x-auto">
        <div className="flex items-center gap-1">
          {TAB_CONFIG.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-[12px] font-heading transition-colors ${
                  isActive
                    ? 'text-foreground font-semibold border-b-2 border-red-600'
                    : 'text-foreground/60 hover:text-muted-foreground'
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 탭 컨텐츠 */}
      <div className="flex-1 overflow-auto px-4 md:px-8 lg:px-12 py-4 md:py-6">
        {/* ============================================================ */}
        {/* 업로드 탭 */}
        {/* ============================================================ */}
        {activeTab === 'upload' && (
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4 md:gap-8 max-w-6xl">
            {/* 좌측: 드롭존 + 진행률 + 미리보기 */}
            <div className="space-y-6">
              <FileDropZone
                onFilesDrop={handleFilesDrop}
                disabled={isUploading}
              />

              {/* 업로드 진행률 */}
              <UploadProgress
                files={files}
                onRemove={removeFile}
                onClearAll={clearFiles}
              />

              {/* 파일 미리보기 */}
              {previewFileId && previewData && (
                <FilePreview
                  fileName={
                    files.find((f) => f.id === previewFileId)?.name ?? ''
                  }
                  data={previewData}
                  onClose={() => setPreview(null, null)}
                />
              )}
            </div>

            {/* 우측: 대상 데이터소스 선택 */}
            <div className="space-y-6">
              <DataSourceManager
                datasources={datasources}
                selectedName={selectedDs}
                onSelect={setSelectedDs}
                loading={dsLoading}
                onRefresh={dsRefetch}
              />

              {/* 연결 테스트 (선택된 데이터소스가 있을 때) */}
              {selectedDs && (
                <button
                  type="button"
                  onClick={() => setTestDialogDs(selectedDs)}
                  className="w-full flex items-center justify-center gap-1.5 px-4 py-2 text-[12px] font-medium text-gray-600 bg-card border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors font-heading"
                >
                  <Database className="h-3.5 w-3.5" />
                  연결 테스트
                </button>
              )}

              {/* 사용 가이드 */}
              <div className="p-4 bg-blue-50/60 rounded-xl border border-blue-100 space-y-3">
                <h4 className="text-[12px] font-semibold text-blue-900 font-heading">
                  사용 가이드
                </h4>
                <ol className="space-y-2 text-[11px] text-blue-800/80 leading-relaxed">
                  <li className="flex gap-2">
                    <span className="shrink-0 flex items-center justify-center w-5 h-5 bg-blue-200 text-blue-800 rounded text-[10px] font-bold">
                      1
                    </span>
                    <span>CSV, JSON, Excel 파일을 드래그하거나 클릭하여 업로드</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="shrink-0 flex items-center justify-center w-5 h-5 bg-blue-200 text-blue-800 rounded text-[10px] font-bold">
                      2
                    </span>
                    <span>대상 데이터소스를 선택하면 해당 DB로 자동 적재</span>
                  </li>
                  <li className="flex gap-2">
                    <span className="shrink-0 flex items-center justify-center w-5 h-5 bg-blue-200 text-blue-800 rounded text-[10px] font-bold">
                      3
                    </span>
                    <span>ETL 파이프라인 탭에서 자동화된 수집 파이프라인 관리</span>
                  </li>
                </ol>
              </div>
            </div>
          </div>
        )}

        {/* ============================================================ */}
        {/* 파이프라인 탭 */}
        {/* ============================================================ */}
        {activeTab === 'pipelines' && (
          <div className="max-w-4xl">
            <PipelineControlPanel
              pipelines={pipelines}
              loading={pipelinesLoading}
              onRun={runPipeline}
              onStop={stopPipeline}
              onDelete={deletePipeline}
              onCreate={() => {
                // TODO: 파이프라인 생성 다이얼로그 구현
              }}
            />
          </div>
        )}

        {/* ============================================================ */}
        {/* 수집 이력 탭 */}
        {/* ============================================================ */}
        {activeTab === 'history' && (
          <div className="max-w-5xl">
            <IngestionHistory
              records={history}
              loading={historyLoading}
              onRefresh={() => fetchHistory()}
            />
          </div>
        )}
      </div>

      {/* 연결 테스트 다이얼로그 */}
      {testDialogDs && (
        <ConnectionTestDialog
          open={!!testDialogDs}
          onClose={() => setTestDialogDs(null)}
          datasourceName={testDialogDs}
        />
      )}
    </div>
  );
};
