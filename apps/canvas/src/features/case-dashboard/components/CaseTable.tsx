import type { ColumnDef } from '@tanstack/react-table';
import { DataTable } from '@/components/shared/DataTable';
import { Badge } from '@/components/ui/badge';
import type { Case } from '../hooks/useCases';

interface CaseTableProps {
  data: Case[];
  onRowClick?: (c: Case) => void;
}

const statusLabel: Record<Case['status'], string> = {
  PENDING: '대기',
  IN_PROGRESS: '진행 중',
  COMPLETED: '완료',
  REJECTED: '반려',
};

const priorityVariant = (p: Case['priority']) =>
  p === 'CRITICAL' || p === 'HIGH' ? 'destructive' : 'secondary';

export function CaseTable({ data, onRowClick }: CaseTableProps) {
  const columns: ColumnDef<Case>[] = [
    {
      accessorKey: 'title',
      header: '케이스명',
      cell: ({ row }) => (
        <span className="font-medium text-white">{row.original.title}</span>
      ),
    },
    {
      accessorKey: 'status',
      header: '상태',
      cell: ({ row }) => (
        <Badge variant="outline" className="capitalize">
          {statusLabel[row.original.status]}
        </Badge>
      ),
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
      cell: ({ row }) =>
        new Date(row.original.createdAt).toLocaleDateString('ko-KR'),
    },
  ];

  return (
    <DataTable columns={columns} data={data} onRowClick={onRowClick} />
  );
}
