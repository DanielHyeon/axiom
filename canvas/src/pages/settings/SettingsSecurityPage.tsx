/**
 * SettingsSecurityPage — 보안/감사 관리 페이지
 * 4개 탭: 사용자 | 역할 | 테이블 권한 | 감사 로그
 * /settings/security 라우트 (admin 전용)
 */

import React from 'react';
import { Shield, Users, ShieldCheck, Database, FileText } from 'lucide-react';
import { useSecurityStore } from '@/features/security/store/useSecurityStore';
import { UserManagementPanel } from '@/features/security/components/UserManagementPanel';
import { RoleManagementPanel } from '@/features/security/components/RoleManagementPanel';
import { TablePermissions } from '@/features/security/components/TablePermissions';
import { AuditLogViewer } from '@/features/security/components/AuditLogViewer';
import type { SecurityTab } from '@/features/security/types/security';

// ---------------------------------------------------------------------------
// 탭 정의
// ---------------------------------------------------------------------------

interface TabDef {
  id: SecurityTab;
  label: string;
  icon: React.ElementType;
}

const TABS: TabDef[] = [
  { id: 'users', label: '사용자', icon: Users },
  { id: 'roles', label: '역할', icon: ShieldCheck },
  { id: 'table-permissions', label: '테이블 권한', icon: Database },
  { id: 'audit-logs', label: '감사 로그', icon: FileText },
];

// ---------------------------------------------------------------------------
// SettingsSecurityPage 컴포넌트
// ---------------------------------------------------------------------------

export const SettingsSecurityPage: React.FC = () => {
  const activeTab = useSecurityStore((s) => s.activeTab);
  const setActiveTab = useSecurityStore((s) => s.setActiveTab);

  return (
    <div className="flex flex-col gap-6">
      {/* 페이지 헤더 */}
      <div className="flex items-center gap-4">
        <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-primary to-indigo-500 flex items-center justify-center shadow-md">
          <Shield className="h-6 w-6 text-white" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-foreground">보안 관리</h1>
          <p className="text-sm text-muted-foreground">
            RBAC 기반 접근 제어, 테이블 권한 및 감사 로그를 관리합니다
          </p>
        </div>
      </div>

      {/* 서브 탭 내비게이션 */}
      <nav
        className="flex gap-2 border-b border-border overflow-x-auto pb-px"
        role="tablist"
        aria-label="보안 관리 탭"
      >
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              className={[
                'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap',
                isActive
                  ? 'text-primary border-primary'
                  : 'text-muted-foreground border-transparent hover:text-foreground hover:border-border',
              ].join(' ')}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </nav>

      {/* 탭 콘텐츠 */}
      <div className="min-h-0 flex-1">
        {activeTab === 'users' && <UserManagementPanel />}
        {activeTab === 'roles' && <RoleManagementPanel />}
        {activeTab === 'table-permissions' && <TablePermissions />}
        {activeTab === 'audit-logs' && <AuditLogViewer />}
      </div>
    </div>
  );
};
