import { Loader2 } from 'lucide-react';

export function ThinkingIndicator({ text, isExecuting }: { text: string, isExecuting?: boolean }) {
    return (
        <div className="flex items-center space-x-3 text-sm text-neutral-400 p-2">
            <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
            <span>{isExecuting ? '쿼리 실행 중...' : text}</span>
        </div>
    );
}
