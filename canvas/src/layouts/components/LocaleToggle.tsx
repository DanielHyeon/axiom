import { useTranslation } from 'react-i18next';
import type { Locale } from '@/lib/i18n';

/** 언어 전환 버튼 — aria-label도 i18n 키로 번역 */
export function LocaleToggle() {
 const { t, i18n } = useTranslation();
 const current = (i18n.language?.slice(0, 2) || 'ko') as Locale;
 const next: Locale = current === 'ko' ? 'en' : 'ko';
 return (
 <button
 type="button"
 onClick={() => i18n.changeLanguage(next)}
 className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
 aria-label={next === 'ko' ? t('locale.switchToKo') : t('locale.switchToEn')}
 title={current === 'ko' ? 'KO' : 'EN'}
 >
 {current === 'ko' ? 'KO' : 'EN'}
 </button>
 );
}
