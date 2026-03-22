/**
 * GlossaryPage — 비즈니스 글로서리 페이지
 * /data/glossary 라우트에 매핑
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import { GlossaryBrowser } from '@/features/glossary/components/GlossaryBrowser';

export const GlossaryPage: React.FC = () => {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col h-full">
      {/* 페이지 헤더 */}
      <header className="shrink-0 px-6 py-4 border-b bg-background">
        <h1 className="text-lg font-semibold">{t('glossary.title')}</h1>
        <p className="text-sm text-muted-foreground mt-0.5">{t('glossary.subtitle')}</p>
      </header>

      {/* 본문 — GlossaryBrowser가 전체 높이를 차지 */}
      <div className="flex-1 min-h-0">
        <GlossaryBrowser />
      </div>
    </div>
  );
};
