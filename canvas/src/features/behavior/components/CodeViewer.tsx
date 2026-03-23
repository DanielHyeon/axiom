/**
 * CodeViewer — 코드 표시 컴포넌트
 *
 * 생성된 코드를 모노스페이스 폰트로 보여주고,
 * 클립보드 복사 버튼과 언어 배지를 제공한다.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface CodeViewerProps {
  /** 표시할 코드 문자열 */
  code: string;
  /** 코드 언어 */
  language?: string;
  /** 추가 CSS 클래스 */
  className?: string;
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export function CodeViewer({ code, language = 'python', className }: CodeViewerProps) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // 언마운트 시 타이머 정리 — 메모리 누수 방지
  useEffect(() => () => clearTimeout(timerRef.current), []);

  /** 코드를 클립보드에 복사한다 */
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      toast.success(t('behaviorExt.clipboardCopied'));
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error(t('behaviorExt.copyFailed'));
    }
  }, [code]);

  return (
    <div className={`relative rounded-lg border border-border bg-muted/50 ${className ?? ''}`}>
      {/* 상단 바: 언어 배지 + 복사 버튼 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <Badge variant="outline" className="text-xs font-mono">
          {language}
        </Badge>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          onClick={handleCopy}
          title={t('behaviorExt.copyToClipboard')}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-emerald-400" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>

      {/* 코드 본문 */}
      <pre className="p-4 overflow-x-auto text-sm leading-relaxed">
        <code className="font-mono text-foreground whitespace-pre">{code}</code>
      </pre>
    </div>
  );
}
