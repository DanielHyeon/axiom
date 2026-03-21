/**
 * MondrianXmlEditor — Mondrian XML 편집기.
 *
 * XML 텍스트 에디터 + 읽기 전용 미리보기를 제공한다.
 * Monaco Editor는 향후 통합 예정 — 현재는 textarea 기반.
 *
 * 기능:
 * - 편집 / 미리보기 모드 토글
 * - 클립보드 복사, 파일 업로드/다운로드
 * - 선택적 검증 콜백
 * - 문자 수 및 줄 수 상태 바
 */
import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Copy, Check, Upload, Download, Eye, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';

// ─── Props ────────────────────────────────────────────────

interface MondrianXmlEditorProps {
  /** 현재 XML 값 */
  value: string;
  /** 값 변경 핸들러 */
  onChange: (xml: string) => void;
  /** 읽기 전용 모드 */
  readOnly?: boolean;
  /** 파일 업로드 완료 콜백 */
  onUpload?: (xml: string) => void;
  /** XML 검증 콜백 */
  onValidate?: (xml: string) => void;
}

// ─── 컴포넌트 ────────────────────────────────────────────

export function MondrianXmlEditor({
  value,
  onChange,
  readOnly = false,
  onUpload,
  onValidate,
}: MondrianXmlEditorProps) {
  const [mode, setMode] = useState<'edit' | 'preview'>('edit');
  const [copied, setCopied] = useState(false);

  // 클립보드 복사
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      console.warn('[MondrianXmlEditor] 클립보드 복사 실패');
    }
  }, [value]);

  // .xml/.mondrian 파일 업로드
  const handleFileUpload = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.xml,.mondrian';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const text = await file.text();
      onChange(text);
      onUpload?.(text);
    };
    input.click();
  }, [onChange, onUpload]);

  // XML 파일 다운로드
  const handleDownload = useCallback(() => {
    const blob = new Blob([value], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mondrian-schema.xml';
    a.click();
    URL.revokeObjectURL(url);
  }, [value]);

  return (
    <div className="flex flex-col h-full border border-[#E5E5E5] rounded-lg overflow-hidden">
      {/* ─── 툴바 ─────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[#F5F5F5] border-b border-[#E5E5E5] shrink-0">
        {/* 편집 / 미리보기 모드 토글 */}
        <div className="flex items-center gap-0.5">
          <button
            type="button"
            onClick={() => setMode('edit')}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-[IBM_Plex_Mono] transition-colors',
              mode === 'edit'
                ? 'bg-white shadow-sm text-foreground/70'
                : 'text-foreground/30',
            )}
          >
            <Edit3 className="h-3 w-3" /> 편집
          </button>
          <button
            type="button"
            onClick={() => setMode('preview')}
            className={cn(
              'flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-[IBM_Plex_Mono] transition-colors',
              mode === 'preview'
                ? 'bg-white shadow-sm text-foreground/70'
                : 'text-foreground/30',
            )}
          >
            <Eye className="h-3 w-3" /> 미리보기
          </button>
        </div>

        {/* 액션 버튼 그룹 */}
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleFileUpload}
            className="h-6 text-[10px] px-2"
          >
            <Upload className="h-3 w-3 mr-1" /> 업로드
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDownload}
            disabled={!value}
            className="h-6 text-[10px] px-2"
          >
            <Download className="h-3 w-3 mr-1" /> 다운로드
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            disabled={!value}
            className="h-6 text-[10px] px-2"
          >
            {copied ? (
              <Check className="h-3 w-3 text-green-500" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
          {onValidate && (
            <Button
              size="sm"
              onClick={() => onValidate(value)}
              disabled={!value}
              className="h-6 text-[10px] px-2"
            >
              검증
            </Button>
          )}
        </div>
      </div>

      {/* ─── 에디터 / 미리보기 영역 ──────────────────── */}
      <div className="flex-1 min-h-0">
        {mode === 'edit' ? (
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            readOnly={readOnly}
            className="w-full h-full resize-none p-3 text-[11px] font-[IBM_Plex_Mono] leading-relaxed bg-[#1E1E1E] text-[#D4D4D4] focus:outline-none"
            placeholder="Mondrian XML을 입력하거나 파일을 업로드하세요..."
            spellCheck={false}
          />
        ) : (
          <pre className="w-full h-full overflow-auto p-3 text-[11px] font-[IBM_Plex_Mono] leading-relaxed bg-[#1E1E1E] text-[#D4D4D4]">
            {value || '내용이 없습니다'}
          </pre>
        )}
      </div>

      {/* ─── 상태 바 ──────────────────────────────────── */}
      <div className="flex items-center gap-4 px-3 py-1 bg-[#2D2D2D] text-[9px] text-[#888] font-[IBM_Plex_Mono] shrink-0">
        <span>{value.length.toLocaleString()} 문자</span>
        <span>{value.split('\n').length} 줄</span>
        <span>XML</span>
      </div>
    </div>
  );
}
