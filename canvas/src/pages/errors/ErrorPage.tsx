import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';

interface ErrorPageProps {
 error?: Error;
}

export const ErrorPage: React.FC<ErrorPageProps> = ({ error }) => {
 const { t } = useTranslation();
 const message = error?.message ?? t('errors.unknownError');

 return (
 <div className="flex min-h-screen flex-col items-center justify-center gap-3 md:gap-4 p-4 md:p-8 text-center">
 <h1 className="text-lg md:text-xl font-semibold">{t('errors.somethingWentWrong')}</h1>
 <p className="max-w-sm md:max-w-md text-center text-xs md:text-sm text-muted-foreground">{message}</p>
 <Link
 to={ROUTES.DASHBOARD}
 className="rounded bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90"
 >
 {t('errors.goToDashboard')}
 </Link>
 </div>
 );
};
