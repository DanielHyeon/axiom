import { Loader2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export function ThinkingIndicator({
  const { t } = useTranslation(); text, isExecuting }: { text: string, isExecuting?: boolean }) {
 return (
 <div className="flex items-center space-x-3 text-sm text-foreground/60 p-2 font-mono">
 <Loader2 className="w-4 h-4 animate-spin text-destructive" />
 <span>{t('nl2sqlPage.msg8fa9751e')}</span>
 </div>
 );
}
