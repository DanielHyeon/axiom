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
 <div className="flex flex-col items-center justify-center w-full h-full p-8 text-center border border-border border-dashed rounded-lg">
 <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-full bg-muted border border-border text-foreground/60">
 <Icon size={24} />
 </div>
 <h3 className="mb-2 text-lg font-semibold text-foreground font-heading">{title}</h3>
 <p className="max-w-sm mb-6 text-sm text-foreground/60 font-mono">
 {description}
 </p>
 {actionLabel && onAction && (
 <Button onClick={onAction} variant="outline" className="border-border text-muted-foreground hover:text-foreground hover:bg-muted font-heading">
 {actionLabel}
 </Button>
 )}
 </div>
 );
}
