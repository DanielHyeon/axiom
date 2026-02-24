import { useState, useMemo } from 'react';
import MonacoEditor from 'react-monaco-editor';
import { Button } from '@/components/ui/button';
import { Copy, Check, Play } from 'lucide-react';

interface SqlPreviewProps {
  sql: string;
  onRun?: (sql: string) => void;
}

export function SqlPreview({ sql, onRun }: SqlPreviewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const editorHeight = useMemo(() => {
    const lineCount = (sql.match(/\n/g) || []).length + 1;
    return Math.min(Math.max(lineCount * 19, 80), 300);
  }, [sql]);

  return (
    <div className="border border-neutral-800 rounded-md overflow-hidden bg-[#1e1e1e] my-3">
      <div className="flex items-center justify-between px-3 py-1.5 bg-neutral-900 border-b border-neutral-800">
        <span className="text-xs font-mono text-neutral-400">SQL</span>
        <div className="flex space-x-1">
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleCopy} title="복사">
            {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 text-neutral-400" />}
          </Button>
          {onRun && (
            <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => onRun(sql)} title="실행">
              <Play className="h-3 w-3 text-blue-400" />
            </Button>
          )}
        </div>
      </div>
      <MonacoEditor
        language="sql"
        theme="vs-dark"
        value={sql}
        width="100%"
        height={editorHeight}
        options={{
          readOnly: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          lineNumbers: 'on',
          fontSize: 13,
          wordWrap: 'on',
          folding: false,
          renderLineHighlight: 'none',
          overviewRulerLanes: 0,
          hideCursorInOverviewRuler: true,
          scrollbar: { vertical: 'hidden', horizontal: 'auto' },
          contextmenu: false,
        }}
      />
    </div>
  );
}
