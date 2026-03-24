import { useTranslation } from 'react-i18next';
/**
 * 프로세스 변형 목록 패널 (Phase C4 스텁).
 * Synapse API 연동 후 변형 목록 표시.
 */
export function VariantList() {
  const { t } = useTranslation();
 return (
 <div className="rounded-lg border border-border bg-card/50 p-4">
 <h3 className="mb-2 text-sm font-semibold text-primary-foreground">{t('processPage.msgd25195aa')}</h3>
 <p className="text-xs text-foreground0">{t('processPage.msg0ba2cb53')}</p>
 </div>
 );
}
