import type { ColumnDef } from '@tanstack/react-table';
import { useNavigate } from 'react-router-dom';
import { Share2 } from 'lucide-react';
import { DataTable } from '@/components/shared/DataTable';
import { Badge } from '@/components/ui/badge';
import { ROUTES } from '@/lib/routes/routes';
import type { Case } from '../hooks/useCases';

interface CaseTableProps {
  data: Case[];
  onRowClick?: (c: Case) => void;
}

const statusConfig: Record<Case['status'], { label: string; className: string }> = {
  PENDING: { label: '대기', className: 'border border-amber-400/30 bg-amber-500/20 text-amber-300' },
  IN_PROGRESS: { label: '진행 중', className: 'border border-blue-400/30 bg-blue-500/20 text-blue-300' },
  COMPLETED: { label: '완료', className: 'border border-emerald-400/30 bg-emerald-500/20 text-emerald-300' },
  REJECTED: { label: '반려', className: 'border border-red-400/30 bg-red-500/20 text-red-300' },
};

const priorityVariant = (p: Case['priority']) =>
  p === 'CRITICAL' || p === 'HIGH' ? 'destructive' : 'secondary';

export function CaseTable({ data, onRowClick }: CaseTableProps) {
  const navigate = useNavigate();

  const columns: ColumnDef<Case>[] = [
    {
      accessorKey: 'title',
      header: '케이스명',
      cell: ({ row }) => (
        <span className="font-semibold text-sky-300 hover:text-sky-200">{row.original.title}</span>
      ),
    },
    {
      accessorKey: 'status',
      header: '상태',
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
      header: '우선순위',
      cell: ({ row }) => (
        <Badge variant={priorityVariant(row.original.priority)}>
          {row.original.priority}
        </Badge>
      ),
    },
    {
      accessorKey: 'createdAt',
      header: '생성일',
      cell: ({ row }) => (
        <span className="text-neutral-400 tabular-nums">
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
          className="p-1.5 rounded-md text-neutral-400 hover:text-blue-400 hover:bg-neutral-800 transition-colors"
          title="온톨로지 보기"
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
