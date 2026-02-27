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
        <div className={cn("flex w-full py-6", isAi ? "bg-[#F5F5F5]" : "")}>
            <div className="container mx-auto max-w-4xl flex gap-6 px-4">

                {/* Avatar */}
                <div className={cn(
                    "w-8 h-8 rounded-sm mx-0 flex items-center justify-center shrink-0",
                    isAi ? "bg-red-50 text-red-600 border border-red-200" : "bg-[#E5E5E5] text-[#5E5E5E]"
                )}>
                    {isAi ? <Sparkles size={16} /> : <User size={16} />}
                </div>

                {/* Content */}
                <div className="flex-1 w-full overflow-hidden text-sm md:text-base text-[#5E5E5E] leading-relaxed font-sans mt-1">
                    {children}
                </div>

            </div>
        </div>
    );
}
