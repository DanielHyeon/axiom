import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation();
  const map: Record<DocumentStatus, { variant: 'secondary' | 'default' | 'destructive' | 'outline'; labelKey: string }> = {
    draft: { variant: 'outline', labelKey: 'documents.status.draft' },
    in_review: { variant: 'secondary', labelKey: 'documents.status.in_review' },
    approved: { variant: 'default', labelKey: 'documents.status.approved' },
    rejected: { variant: 'destructive', labelKey: 'documents.status.rejected' },
    changes_requested: { variant: 'destructive', labelKey: 'documents.status.changes_requested' },
  };
  const { variant, labelKey } = map[status] ?? map.draft;
  return <Badge variant={variant}>{t(labelKey)}</Badge>;
}

export function DocumentListPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { caseId } = useParams<{ caseId: string }>();
  const { data, isLoading, error } = useDocumentList(caseId ?? '');

  const columns: ColumnDef<Document>[] = [
    {
      accessorKey: 'name',
      header: t('documents.columns.name'),
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <AiGeneratedBadge isAiGenerated={row.original.isAiGenerated} />
          <span className="font-medium">{row.getValue('name')}</span>
        </div>
      ),
    },
    { accessorKey: 'type', header: t('documents.columns.type') },
    {
      accessorKey: 'status',
      header: t('documents.columns.status'),
      cell: ({ row }) => <StatusBadge status={row.getValue('status')} />,
    },
    { accessorKey: 'version', header: t('documents.columns.version') },
    {
      accessorKey: 'updatedAt',
      header: t('documents.columns.updatedAt'),
      cell: ({ row }) => (
        <span className="text-muted-foreground text-sm">{row.getValue('updatedAt')}</span>
      ),
    },
  ];

  if (isLoading) return <LoadingSpinner size="lg" label={t('documents.loadingDocuments')} />;
  if (error) return <EmptyState title={t('documents.errorLoadDocuments')} message={String(error)} />;

  const documents = data?.items ?? [];

  return (
    <div className="space-y-6 px-4 sm:px-8 lg:px-12 py-4 sm:py-8">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
        <div>
          <h1 className="text-xl md:text-2xl font-semibold tracking-tight">{t('documents.title')}</h1>
          <p className="text-xs md:text-sm text-muted-foreground mt-1">{t('documents.subtitle')}</p>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" size="sm" onClick={() => navigate('/documents/new')}>{t('documents.newDocument')}</Button>
          <Button size="sm" onClick={() => navigate('/documents/new-ai')}>{t('documents.aiGenerateRequest')}</Button>
        </div>
      </div>

      {documents.length === 0 ? (
        <EmptyState title={t('documents.noDocuments')} message={t('documents.noDocumentsDesc')} />
      ) : (
        <div className="bg-card border border-border rounded-lg p-2 md:p-4 overflow-x-auto">
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
