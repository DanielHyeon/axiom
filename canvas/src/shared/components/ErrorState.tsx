import { AlertCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';

interface ErrorStateProps {
 message: string;
 onRetry?: () => void;
 retryLabel?: string;
}

export function ErrorState({ message, onRetry, retryLabel }: ErrorStateProps) {
 const { t } = useTranslation();
 const label = retryLabel ?? t('common.retry');
 return (
 <div className="flex flex-col items-center justify-center w-full min-h-[200px] p-8 text-center bg-card border border-border rounded-lg">
 <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-full bg-destructive/10 text-destructive">
 <AlertCircle size={24} aria-hidden />
 </div>
 <p className="mb-4 text-sm text-foreground">{message}</p>
 {onRetry && (
 <Button onClick={onRetry} variant="outline" size="sm">
 {label}
 </Button>
 )}
 </div>
 );
}
