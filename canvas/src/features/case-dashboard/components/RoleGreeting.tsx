import type { UserRole } from '@/types/auth.types';
import { useTranslation } from 'react-i18next';

const ROLE_LABEL: Record<UserRole, string> = {
 admin: t('caseDashboardExt.role.admin'),
 manager: t('caseDashboardExt.role.manager'),
 attorney: t('dataQualityExt.incidentCols.assignee'),
 analyst: t('caseDashboardExt.role.analyst'),
 engineer: t('caseDashboardExt.role.engineer'),
 staff: t('caseDashboardExt.role.staff'),
 viewer: t('caseDashboardExt.role.viewer'),
};

interface RoleGreetingProps {
 userName?: string | null;
 role?: UserRole | null;
 workCount?: number;
}

export function RoleGreeting({
  userName, role, workCount = 0 }: RoleGreetingProps) {
 const name = userName ?? t('caseDashboardExt.defaultUser');
 const roleText = role ? ROLE_LABEL[role] : '';
 return (
 <div className="mb-4 md:mb-6">
 <h1 className="text-xl md:text-2xl font-bold tracking-tight text-foreground">
 {t('caseDashboardF.greeting', { name })}
 </h1>
 {roleText && (
 <p className="mt-1 text-sm text-muted-foreground">
 {t('caseDashboardF.roleWorkCount', { role: roleText, count: workCount })}
 </p>
 )}
 </div>
 );
}
