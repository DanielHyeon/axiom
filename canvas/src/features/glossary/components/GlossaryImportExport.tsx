/**
 * GlossaryImportExport — CSV/JSON 가져오기 · 내보내기 다이얼로그
 */

import React, { useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Upload, Download, FileJson, FileSpreadsheet } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useGlossaryStore } from '../store/useGlossaryStore';
import { exportTerms, importTerms } from '../api/glossaryApi';
import { useQueryClient } from '@tanstack/react-query';
import { glossaryKeys } from '../hooks/useGlossary';

export const GlossaryImportExport: React.FC = () => {
  const { t } = useTranslation();
  const { importExportOpen, closeImportExport, selectedGlossary } = useGlossaryStore();
  const qc = useQueryClient();

  const [activeTab, setActiveTab] = useState<'import' | 'export'>('export');
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const glossaryId = selectedGlossary?.id ?? '';

  /** 내보내기 */
  const handleExport = useCallback(
    async (format: 'csv' | 'json') => {
      if (!glossaryId) return;
      setExporting(true);
      setError(null);
      try {
        const blob = await exportTerms(glossaryId, format);
        // 다운로드 트리거
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${selectedGlossary?.name ?? 'glossary'}_terms.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (e) {
        setError(e instanceof Error ? e.message : t('common.error'));
      } finally {
        setExporting(false);
      }
    },
    [glossaryId, selectedGlossary, t],
  );

  /** 가져오기 — 파일 선택 후 업로드 */
  const handleImport = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file || !glossaryId) return;

      setImporting(true);
      setError(null);
      setImportResult(null);
      try {
        const result = await importTerms(glossaryId, file);
        setImportResult(result);
        // 캐시 무효화하여 목록 새로고침
        qc.invalidateQueries({ queryKey: glossaryKeys.terms(glossaryId) });
        qc.invalidateQueries({ queryKey: glossaryKeys.glossaries() });
      } catch (err) {
        setError(err instanceof Error ? err.message : t('common.error'));
      } finally {
        setImporting(false);
        // 파일 인풋 초기화
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    },
    [glossaryId, qc, t],
  );

  if (!importExportOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) closeImportExport(); }}
      role="dialog"
      aria-modal="true"
      aria-label={t('glossary.importExport.title')}
    >
      <div className="w-[440px] bg-background rounded-lg shadow-xl flex flex-col border">
        {/* 헤더 */}
        <header className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-lg font-semibold">{t('glossary.importExport.title')}</h2>
          <button
            onClick={closeImportExport}
            className="p-1.5 rounded-md text-muted-foreground hover:bg-muted transition-colors"
            aria-label={t('common.close')}
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        {/* 탭 */}
        <div className="flex border-b px-6">
          <button
            onClick={() => { setActiveTab('export'); setError(null); }}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'export'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Download className="h-4 w-4 inline mr-1.5" />
            {t('glossary.importExport.export')}
          </button>
          <button
            onClick={() => { setActiveTab('import'); setError(null); setImportResult(null); }}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'import'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Upload className="h-4 w-4 inline mr-1.5" />
            {t('glossary.importExport.import')}
          </button>
        </div>

        {/* 본문 */}
        <div className="px-6 py-5 space-y-4">
          {error && (
            <div className="px-4 py-3 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm">
              {error}
            </div>
          )}

          {activeTab === 'export' && (
            <>
              <p className="text-sm text-muted-foreground">
                {t('glossary.importExport.exportDesc')}
              </p>
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1 h-20 flex-col gap-1"
                  onClick={() => handleExport('json')}
                  disabled={exporting || !glossaryId}
                >
                  <FileJson className="h-6 w-6" />
                  <span className="text-xs">JSON</span>
                </Button>
                <Button
                  variant="outline"
                  className="flex-1 h-20 flex-col gap-1"
                  onClick={() => handleExport('csv')}
                  disabled={exporting || !glossaryId}
                >
                  <FileSpreadsheet className="h-6 w-6" />
                  <span className="text-xs">CSV</span>
                </Button>
              </div>
            </>
          )}

          {activeTab === 'import' && (
            <>
              <p className="text-sm text-muted-foreground">
                {t('glossary.importExport.importDesc')}
              </p>

              {/* 드롭존 스타일 파일 입력 */}
              <label className="flex flex-col items-center justify-center gap-2 h-28 border-2 border-dashed rounded-lg cursor-pointer hover:bg-muted/50 transition-colors">
                <Upload className="h-6 w-6 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  {importing ? t('common.processing') : t('glossary.importExport.selectFile')}
                </span>
                <span className="text-xs text-muted-foreground">CSV, JSON</span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.json"
                  className="hidden"
                  onChange={handleImport}
                  disabled={importing || !glossaryId}
                />
              </label>

              {/* 가져오기 결과 */}
              {importResult && (
                <div className="px-4 py-3 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-600 text-sm">
                  {t('glossary.importExport.importResult', {
                    imported: importResult.imported,
                    skipped: importResult.skipped,
                  })}
                </div>
              )}
            </>
          )}
        </div>

        {/* 푸터 */}
        <footer className="flex justify-end px-6 py-4 border-t">
          <Button variant="outline" onClick={closeImportExport}>
            {t('common.close')}
          </Button>
        </footer>
      </div>
    </div>
  );
};
