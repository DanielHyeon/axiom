/**
 * RoleManagementPanel — 역할 관리 패널
 * KAIR RoleManagement.vue에서 이식
 * - 역할 카드 그리드 + 소속 사용자 수
 * - 권한 매트릭스 (리소스 x 액션 체크박스)
 */

import React, { useState } from 'react';
import {
import { useTranslation } from 'react-i18next';
  RefreshCw,
  ShieldCheck,
  Users,
  Loader2,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { useRoles } from '../hooks/useSecurity';
import type { Permission, PermissionAction } from '../types/security';

// ---------------------------------------------------------------------------
// 리소스 그룹 라벨 (한글)
// ---------------------------------------------------------------------------

const RESOURCE_LABEL: Record<string, string> = {
  users: t('caseDashboardExt.defaultUser'),
  roles: t('securityExt.roleCol'),
  cases: t('securityExt.resource.cases'),
  documents: t('securityExt.resource.documents'),
  ontology: t('domainExt.ontologyTab'),
  datasources: t('securityExt.resource.datasources'),
  queries: t('securityExt.resource.queries'),
  settings: t('securityExt.resource.settings'),
  audit: t('securityExt.resource.audit'),
  processes: t('securityExt.resource.processes'),
};

const ACTION_LABEL: Record<PermissionAction, string> = {
  read: t('securityExt.permission.read'),
  write: t('securityExt.permission.write'),
  delete: t('ingestionExt.delete'),
  admin: t('securityExt.permission.admin'),
};

const ALL_ACTIONS: PermissionAction[] = ['read', 'write', 'delete', 'admin'];

// ---------------------------------------------------------------------------
// RoleManagementPanel 컴포넌트
// ---------------------------------------------------------------------------

export const RoleManagementPanel: React.FC = () => {
  const { t } = useTranslation();
  const { data: roles = [], isLoading, isError, error, refetch } = useRoles();
  const [expandedRole, setExpandedRole] = useState<string | null>(null);

  // 역할 카드 토글
  const toggleExpand = (roleId: string) => {
    setExpandedRole((prev) => (prev === roleId ? null : roleId));
  };

  // 권한을 리소스별로 그룹핑
  const groupPermissions = (permissions: Permission[]): Record<string, PermissionAction[]> => {
    const grouped: Record<string, PermissionAction[]> = {};
    for (const p of permissions) {
      grouped[p.resource] = p.actions;
    }
    return grouped;
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 툴바 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">{t('securityExt.roleManagement')}</h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('securityF.md8a146a8')}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isLoading}
        >
          <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
          {t('datasourceExt.refreshBtn')}
        </Button>
      </div>

      {/* 에러 */}
      {isError && (
        <div className="flex items-center gap-2 p-4 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{t('securityF.msge7644db6')}</span>
        </div>
      )}

      {/* 로딩 */}
      {isLoading && !isError && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-sm">{t('securityExt.loadingRoles')}</span>
        </div>
      )}

      {/* 빈 상태 */}
      {!isLoading && !isError && roles.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
          <ShieldCheck className="h-10 w-10" />
          <p className="font-medium">{t('securityExt.noRoles')}</p>
        </div>
      )}

      {/* 역할 카드 그리드 */}
      {!isLoading && !isError && roles.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-5">
          {roles.map((role) => {
            const isExpanded = expandedRole === role.id;
            const grouped = groupPermissions(role.permissions);

            return (
              <div
                key={role.id}
                className="border border-border rounded-xl bg-card overflow-hidden transition-all hover:border-primary/40 hover:shadow-sm"
              >
                {/* 카드 헤더 */}
                <button
                  className="w-full flex items-center justify-between p-5 text-left"
                  onClick={() => toggleExpand(role.id)}
                  aria-expanded={isExpanded}
                >
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <ShieldCheck className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-foreground">{role.name}</h3>
                        {role.is_system && (
                          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                            {t('settingsSystem.title')}
                          </Badge>
                        )}
                      </div>
                      {role.description && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {role.description}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {/* 사용자 수 */}
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Users className="h-3.5 w-3.5" />
                      <span>{role.user_count}</span>
                    </div>
                    {/* 권한 수 */}
                    <Badge variant="outline" className="text-[10px]">
                      {t('securityF.permissionCount', { count: role.permissions.length })}
                    </Badge>
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </button>

                {/* 확장 — 권한 매트릭스 */}
                {isExpanded && (
                  <div className="border-t border-border px-5 py-4 bg-muted/20">
                    <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                      {t('securityF.m651813e0')}
                    </h4>
                    {/* 매트릭스 테이블 */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left py-2 pr-4 text-xs font-medium text-muted-foreground">
                              {t('securityExt.resourceCol')}
                            </th>
                            {ALL_ACTIONS.map((action) => (
                              <th
                                key={action}
                                className="text-center py-2 px-3 text-xs font-medium text-muted-foreground"
                              >
                                {ACTION_LABEL[action]}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(grouped).map(([resource, actions]) => (
                            <tr key={resource} className="border-b border-border/50 last:border-0">
                              <td className="py-2 pr-4 text-foreground font-medium">
                                {RESOURCE_LABEL[resource] || resource}
                              </td>
                              {ALL_ACTIONS.map((action) => (
                                <td key={action} className="text-center py-2 px-3">
                                  <Checkbox
                                    checked={actions.includes(action)}
                                    disabled
                                    aria-label={`${RESOURCE_LABEL[resource] || resource} ${ACTION_LABEL[action]}`}
                                  />
                                </td>
                              ))}
                            </tr>
                          ))}
                          {Object.keys(grouped).length === 0 && (
                            <tr>
                              <td
                                colSpan={ALL_ACTIONS.length + 1}
                                className="py-4 text-center text-muted-foreground text-xs"
                              >
                                {t('securityF.mc7f1a5b9')}
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
