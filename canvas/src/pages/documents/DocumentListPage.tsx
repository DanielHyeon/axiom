import { FileText } from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { DataTable } from '@/components/shared/DataTable';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ROUTES } from '@/lib/routes/routes';
import { LoadingSpinner } from '@/shared/components/LoadingSpinner';
import { EmptyState } from '@/shared/components/EmptyState';
import { AiGeneratedBadge } from '@/features/document-management/components/AiGeneratedBadge';
import { useDocumentList } from '@/features/document-management/hooks/useDocuments';
import type { Document, DocumentStatus } from '@/features/document-management/types/document';
import type { ColumnDef } from '@tanstack/react-table';

/** 상태 배지 렌더링 */
function StatusBadge({ status }: { status: DocumentStatus }) {
  const map: Record<DocumentStatus, { variant: 'secondary' | 'default' | 'destructive' | 'outline'; label: string }> = {
    draft: { variant: 'outline', label: '초안' },
    in_review: { variant: 'secondary', label: '검토중' },
    approved: { variant: 'default', label: '승인됨' },
    rejected: { variant: 'destructive', label: '반려됨' },
    changes_requested: { variant: 'destructive', label: '수정요청' },
  };
  const { variant, label } = map[status] ?? map.draft;
  return <Badge variant={variant}>{label}</Badge>;
}

export function DocumentListPage() {
  const navigate = useNavigate();
  const { caseId } = useParams<{ caseId: string }>();
  const { data, isLoading, error } = useDocumentList(caseId ?? '');

  const columns: ColumnDef<Document>[] = [
    {
      accessorKey: 'name',
      header: '문서명',
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <AiGeneratedBadge isAiGenerated={row.original.isAiGenerated} />
          <span className="font-medium">{row.getValue('name')}</span>
        </div>
      ),
    },
    { accessorKey: 'type', header: '유형' },
    {
      accessorKey: 'status',
      header: '상태',
      cell: ({ row }) => <StatusBadge status={row.getValue('status')} />,
    },
    { accessorKey: 'version', header: '버전' },
    {
      accessorKey: 'updatedAt',
      header: '최종 수정',
      cell: ({ row }) => (
        <span className="text-muted-foreground text-sm">{row.getValue('updatedAt')}</span>
      ),
    },
  ];

  if (isLoading) return <LoadingSpinner size="lg" label="문서 목록 로딩 중" />;
  if (error) return <EmptyState icon={FileText} title="문서를 불러올 수 없습니다" description={String(error)} />;

  const documents = data?.items ?? [];

  return (
    <div className="space-y-6 px-4 sm:px-8 lg:px-12 py-4 sm:py-8">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">문서 관리</h1>
          <p className="text-sm text-muted-foreground mt-1">HITL 워크플로로 AI 문서를 검토하고 승인합니다</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => navigate('/documents/new')}>새 문서</Button>
          <Button onClick={() => navigate('/documents/new-ai')}>AI 생성 요청</Button>
        </div>
      </div>

      {documents.length === 0 ? (
        <EmptyState icon={FileText} title="문서가 없습니다" description="새 문서를 만들거나 AI에게 초안 생성을 요청하세요" />
      ) : (
        <div className="bg-card border border-border rounded-lg p-4">
          <DataTable
            columns={columns}
            data={documents}
            onRowClick={(row) =>
              caseId
                ? navigate(ROUTES.CASES.DOCUMENT(caseId, row.id))
                : navigate(`/documents/${row.id}`)
            }
          />
        </div>
      )}
    </div>
  );
}
