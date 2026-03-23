import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuthStore } from '@/stores/authStore';
import { getCurrentUser } from '@/lib/api/usersApi';

/** 설정 > 사용자. GET /api/v1/users/me로 서버와 동기화 후 표시. 사용자 목록은 백엔드 API 연동 후 확장. */
export const SettingsUsersPage: React.FC = () => {
 const { t } = useTranslation();
 const user = useAuthStore((s) => s.user);
 const setUser = useAuthStore((s) => s.setUser);

 useEffect(() => {
 getCurrentUser().then(setUser).catch(() => {});
 }, [setUser]);

 if (!user) {
 return (
 <div className="space-y-4">
 <h2 className="text-lg font-semibold text-foreground">{t('settingsUsers.title')}</h2>
 <p className="text-sm text-muted-foreground">{t('settingsUsers.noUser')}</p>
 </div>
 );
 }

 return (
 <div className="space-y-4">
 <h2 className="text-lg font-semibold text-foreground">{t('settingsUsers.title')}</h2>
 <div className="space-y-3">
 <h3 className="text-sm font-medium text-foreground/80">{t('settingsUsers.currentUser')}</h3>
 <ul className="border border-border rounded divide-y divide-border">
 <li className="px-3 md:px-4 py-2 flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-2">
 <span className="text-muted-foreground text-sm">ID</span>
 <span className="font-mono text-xs sm:text-sm text-foreground break-all">{user.id}</span>
 </li>
 <li className="px-3 md:px-4 py-2 flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-2">
 <span className="text-muted-foreground text-sm">{t('common.email')}</span>
 <span className="text-foreground text-sm break-all">{user.email}</span>
 </li>
 <li className="px-3 md:px-4 py-2 flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-2">
 <span className="text-muted-foreground text-sm">{t('common.role')}</span>
 <span className="text-foreground text-sm">{user.role}</span>
 </li>
 <li className="px-3 md:px-4 py-2 flex flex-col sm:flex-row sm:justify-between gap-0.5 sm:gap-2">
 <span className="text-muted-foreground text-sm">{t('common.tenant')}</span>
 <span className="font-mono text-xs sm:text-sm text-foreground break-all">{user.tenantId}</span>
 </li>
 {user.permissions?.length > 0 && (
 <li className="px-3 md:px-4 py-2 flex flex-col sm:flex-row sm:justify-between gap-1 sm:gap-4">
 <span className="text-muted-foreground shrink-0 text-sm">{t('common.permissions')}</span>
 <span className="text-xs sm:text-sm text-right break-all text-foreground">
 {user.permissions.join(', ')}
 </span>
 </li>
 )}
 {user.caseRoles && Object.keys(user.caseRoles).length > 0 && (
 <li className="px-3 md:px-4 py-2 flex flex-col sm:flex-row sm:justify-between gap-1 sm:gap-4">
 <span className="text-muted-foreground shrink-0 text-sm">{t('common.caseRoles')}</span>
 <span className="text-sm text-right text-foreground">
 {Object.entries(user.caseRoles)
 .map(([k, v]) => `${k}: ${v}`)
 .join(', ')}
 </span>
 </li>
 )}
 </ul>
 </div>
 <p className="text-sm text-muted-foreground">
 {t('settingsUsers.userListPlaceholder')}
 </p>
 </div>
 );
};
