/**
 * 상태 배지 — draft/review/approved/deprecated 시각화
 */
import type { ConceptStatus } from '../types/semantic';

const STATUS_CONFIG: Record<ConceptStatus, { label: string; className: string }> = {
  draft: { label: 'Draft', className: 'bg-slate-100 text-slate-700' },
  review: { label: 'Review', className: 'bg-yellow-100 text-yellow-800' },
  approved: { label: 'Approved', className: 'bg-green-100 text-green-800' },
  deprecated: { label: 'Deprecated', className: 'bg-red-100 text-red-800' },
};

interface Props {
  status: ConceptStatus;
}

export function StatusBadge({ status }: Props) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.draft;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${config.className}`}>
      {config.label}
    </span>
  );
}
