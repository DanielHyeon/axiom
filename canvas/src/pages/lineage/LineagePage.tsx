/**
 * LineagePage — /data/lineage 라우트의 페이지 컴포넌트
 * LineageDashboard 를 단순히 마운트하는 래퍼.
 */

import { LineageDashboard } from '@/features/lineage/components/LineageDashboard';

export function LineagePage() {
  return <LineageDashboard />;
}
