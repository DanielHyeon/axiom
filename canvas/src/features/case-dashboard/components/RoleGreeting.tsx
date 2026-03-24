import type { UserRole } from '@/types/auth.types';
import { useTranslation } from 'react-i18next';

const ROLE_KEY: Record<UserRole, string> = {
 admin: 'caseDashboardExt.role.admin',
 manager: 'caseDashboardExt.role.manager',
 attorney: 'caseDashboardExt.role.attorney',
 analyst: 'caseDashboardExt.role.analyst',
 engineer: 'caseDashboardExt.role.engineer',
 staff: 'caseDashboardExt.role.staff',
 viewer: 'caseDashboardExt.role.viewer',
};

interface RoleGreetingProps {
 userName?: string | null;
 role?: UserRole | null;
 workCount?: number;
}

export function RoleGreeting({ userName, role, workCount = 0 }: RoleGreetingProps) {
 const { t } = useTranslation();
 const name = userName ?? t('caseDashboardExt.defaultUser');
 const roleText = role ? t(ROLE_KEY[role]) : '';
 return (
 <div className="mb-6">
 <h1 className="text-2xl font-bold tracking-tight text-foreground">
 {t('caseDashboardExt.greeting', { name })}
 </h1>
 {roleText && (
 <p className="mt-1 text-sm text-muted-foreground">
 {t('caseDashboardExt.roleWorkCount', { role: roleText, count: workCount })}
 </p>
 )}
 </div>
 );
}
