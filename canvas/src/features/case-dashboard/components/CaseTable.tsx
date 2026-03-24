import type { ColumnDef } from '@tanstack/react-table';
import { useNavigate } from 'react-router-dom';
import { Share2 } from 'lucide-react';
import { DataTable } from '@/components/shared/DataTable';
import { Badge } from '@/components/ui/badge';
import { ROUTES } from '@/lib/routes/routes';
import type { Case } from '../hooks/useCases';
import { useTranslation } from 'react-i18next';

interface CaseTableProps {
 data: Case[];
 onRowClick?: (c: Case) => void;
}

const statusConfig: Record<Case['status'], { label: string; className: string }> = {
 PENDING: { label: t('ontologyWizardExt.statusBadge.pending'), className: 'border border-amber-400/30 bg-warning/20 text-amber-300' },
 IN_PROGRESS: { label: t('ontologyWizardExt.statusBadge.in_progress'), className: 'border border-blue-400/30 bg-primary/20 text-primary/80' },
 COMPLETED: { label: t('ontologyWizardExt.statusBadge.complete'), className: 'border border-emerald-400/30 bg-success/20 text-emerald-300' },
 REJECTED: { label: t('caseDashboardExt.status.REJECTED'), className: 'border border-red-400/30 bg-destructive/20 text-red-300' },
};

const priorityVariant = (p: Case['priority']) =>
 p === 'CRITICAL' || p === 'HIGH' ? 'destructive' : 'secondary';

export function CaseTable({
  const { t } = useTranslation(); data, onRowClick }: CaseTableProps) {
 const navigate = useNavigate();

 const columns: ColumnDef<Case>[] = [
 {
 accessorKey: 'title',
 header: t('caseDashboardExt.caseTable.caseName'),
 cell: ({ row }) => (
 <span className="font-semibold text-sky-300 hover:text-sky-200">{row.original.title}</span>
 ),
 },
 {
 accessorKey: 'status',
 header: t('dataQualityExt.incidentCols.status'),
 cell: ({ row }) => {
 const cfg = statusConfig[row.original.status];
 return (
 <Badge variant="outline" className={cfg?.className}>
 {cfg?.label ?? row.original.status}
 </Badge>
 );
 },
 },
 {
 accessorKey: 'priority',
 header: t('caseDashboardExt.caseTable.priority'),
 cell: ({ row }) => (
 <Badge variant={priorityVariant(row.original.priority)}>
 {row.original.priority}
 </Badge>
 ),
 },
 {
 accessorKey: 'createdAt',
 header: t('mvExt.colCreatedAt'),
 cell: ({ row }) => (
 <span className="text-muted-foreground tabular-nums">
 {new Date(row.original.createdAt).toLocaleDateString('ko-KR')}
 </span>
 ),
 },
 {
 id: 'actions',
 header: '',
 cell: ({ row }) => (
 <button
 type="button"
 onClick={(e) => {
 e.stopPropagation();
 navigate(ROUTES.DATA.ONTOLOGY_CASE(row.original.id));
 }}
 className="p-1.5 rounded-md text-muted-foreground hover:text-primary hover:bg-muted transition-colors"
 title={t('ontologyWizardExt.viewOntology')}
 >
 <Share2 size={14} />
 </button>
 ),
 size: 48,
 },
 ];

 return (
 <DataTable columns={columns} data={data} onRowClick={onRowClick} />
 );
}
