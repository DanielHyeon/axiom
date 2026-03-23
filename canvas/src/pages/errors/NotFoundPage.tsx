import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';

export const NotFoundPage: React.FC = () => {
 const { t } = useTranslation();
 return (
 <div className="flex min-h-screen flex-col items-center justify-center gap-3 md:gap-4 p-4 md:p-8 text-center">
 <h1 className="text-xl md:text-2xl font-semibold">404</h1>
 <p className="text-muted-foreground">{t('errors.notFound')}</p>
 <Link
 to={ROUTES.DASHBOARD}
 className="rounded bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
 >
 {t('errors.goToDashboard')}
 </Link>
 </div>
 );
};
