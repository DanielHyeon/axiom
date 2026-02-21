import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Copy, Check, Play } from 'lucide-react';

interface SqlPreviewProps {
    sql: string;
}

export function SqlPreview({ sql }: SqlPreviewProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(sql);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="border border-neutral-800 rounded-md overflow-hidden bg-[#1e1e1e] my-3">
            <div className="flex items-center justify-between px-3 py-1.5 bg-neutral-900 border-b border-neutral-800">
                <span className="text-xs font-mono text-neutral-400">SQL Generated</span>
                <div className="flex space-x-2">
                    <Button variant="ghost" size="icon" className="h-6 w-6" onClick={handleCopy} title="복사">
                        {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 text-neutral-400" />}
                    </Button>
                    <Button variant="ghost" size="icon" className="h-6 w-6" title="수정 후 실행">
                        <Play className="h-3 w-3 text-blue-400" />
                    </Button>
                </div>
            </div>
            <div className="p-3 overflow-x-auto text-sm font-mono text-blue-300">
                <pre>{sql}</pre>
            </div>
        </div>
    );
}
