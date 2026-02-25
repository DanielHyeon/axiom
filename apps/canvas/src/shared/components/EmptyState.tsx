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
        <div className="flex flex-col items-center justify-center w-full h-full p-8 text-center bg-[#111111] border border-neutral-800 border-dashed rounded-lg">
            <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-full bg-neutral-900 border border-neutral-800 text-neutral-400">
                <Icon size={24} />
            </div>
            <h3 className="mb-2 text-lg font-semibold text-neutral-200">{title}</h3>
            <p className="max-w-sm mb-6 text-sm text-neutral-400">
                {description}
            </p>
            {actionLabel && onAction && (
                <Button onClick={onAction} variant="outline" className="border-neutral-700 text-neutral-300 hover:text-white hover:bg-neutral-800">
                    {actionLabel}
                </Button>
            )}
        </div>
    );
}
