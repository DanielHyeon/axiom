import React from 'react';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

/** OAuth 콜백 처리. 현재는 대시보드로 리다이렉트. */
export const CallbackPage: React.FC = () => {
 const { t } = useTranslation();
 const navigate = useNavigate();
 useEffect(() => {
 navigate(ROUTES.DASHBOARD, { replace: true });
 }, [navigate]);
 return <div className="p-8">{t('auth.loggingIn')}</div>;
};
