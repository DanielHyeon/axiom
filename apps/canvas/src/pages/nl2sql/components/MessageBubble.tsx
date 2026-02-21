import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { User, Sparkles } from 'lucide-react';

interface MessageBubbleProps {
    role: 'user' | 'ai';
    children: ReactNode;
}

export function MessageBubble({ role, children }: MessageBubbleProps) {
    const isAi = role === 'ai';

    return (
        <div className={cn("flex w-full py-6", isAi ? "bg-neutral-900/40" : "")}>
            <div className="container mx-auto max-w-4xl flex gap-6 px-4">

                {/* Avatar */}
                <div className={cn(
                    "w-8 h-8 rounded-sm mx-0 flex items-center justify-center shrink-0",
                    isAi ? "bg-indigo-600/20 text-indigo-400 border border-indigo-500/30" : "bg-neutral-800 text-neutral-300"
                )}>
                    {isAi ? <Sparkles size={16} /> : <User size={16} />}
                </div>

                {/* Content */}
                <div className="flex-1 w-full overflow-hidden text-sm md:text-base text-neutral-200 leading-relaxed font-sans mt-1">
                    {children}
                </div>

            </div>
        </div>
    );
}
