import { useMemo } from 'react';
import type { UserRole } from '@/types/auth.types';

export type DashboardPanelId = 'myWorkitems' | 'approvalQueue' | 'analyticsQuick' | 'dataPipeline' | 'systemHealth';

/** 역할별로 표시할 대시보드 패널 ID 목록 */
export function useDashboardConfig(role: UserRole | undefined): DashboardPanelId[] {
  return useMemo(() => {
    switch (role) {
      case 'admin':
        return ['myWorkitems', 'approvalQueue', 'systemHealth'];
      case 'manager':
        return ['myWorkitems', 'approvalQueue'];
      case 'attorney':
      case 'staff':
        return ['myWorkitems'];
      case 'analyst':
        return ['myWorkitems', 'analyticsQuick'];
      case 'engineer':
        return ['dataPipeline', 'systemHealth'];
      default:
        return ['myWorkitems'];
    }
  }, [role]);
}
