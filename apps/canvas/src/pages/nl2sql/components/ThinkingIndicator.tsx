import { Loader2 } from 'lucide-react';

export function ThinkingIndicator({ text, isExecuting }: { text: string, isExecuting?: boolean }) {
 return (
 <div className="flex items-center space-x-3 text-sm text-foreground/60 p-2 font-[IBM_Plex_Mono]">
 <Loader2 className="w-4 h-4 animate-spin text-destructive" />
 <span>{isExecuting ? '쿼리 실행 중...' : text}</span>
 </div>
 );
}
