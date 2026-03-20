import { useTranslation } from 'react-i18next';
import type { Locale } from '@/lib/i18n';

export function LocaleToggle() {
 const { i18n } = useTranslation();
 const current = (i18n.language?.slice(0, 2) || 'ko') as Locale;
 const next: Locale = current === 'ko' ? 'en' : 'ko';
 return (
 <button
 type="button"
 onClick={() => i18n.changeLanguage(next)}
 className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
 aria-label={next === 'ko' ? '한국어로 전환' : 'Switch to English'}
 title={current === 'ko' ? 'KO' : 'EN'}
 >
 {current === 'ko' ? 'KO' : 'EN'}
 </button>
 );
}
