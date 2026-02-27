import type { LucideIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface EmptyStateProps {
    icon: LucideIcon;
    title: string;
    description: string;
    actionLabel?: string;
    onAction?: () => void;
}

export function EmptyState({ icon: Icon, title, description, actionLabel, onAction }: EmptyStateProps) {
    return (
        <div className="flex flex-col items-center justify-center w-full h-full p-8 text-center border border-[#E5E5E5] border-dashed rounded-lg">
            <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-full bg-[#F5F5F5] border border-[#E5E5E5] text-[#999]">
                <Icon size={24} />
            </div>
            <h3 className="mb-2 text-lg font-semibold text-black font-[Sora]">{title}</h3>
            <p className="max-w-sm mb-6 text-sm text-[#999] font-[IBM_Plex_Mono]">
                {description}
            </p>
            {actionLabel && onAction && (
                <Button onClick={onAction} variant="outline" className="border-[#E5E5E5] text-[#5E5E5E] hover:text-black hover:bg-[#F5F5F5] font-[Sora]">
                    {actionLabel}
                </Button>
            )}
        </div>
    );
}
