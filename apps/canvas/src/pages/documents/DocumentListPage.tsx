import { useNavigate } from 'react-router-dom';
import { DataTable } from '@/components/shared/DataTable';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { ColumnDef } from '@tanstack/react-table';

type Document = {
    id: string;
    name: string;
    type: string;
    status: 'draft' | 'in_review' | 'approved' | 'changes_requested';
    version: string;
    isAiGenerated: boolean;
    lastModified: string;
};

const mockDocuments: Document[] = [
    { id: 'doc-1', name: '이해관계자목록v3', type: '참여자목록', status: 'in_review', version: 'v3', isAiGenerated: true, lastModified: '2시간 전' },
    { id: 'doc-2', name: '실행 계획서', type: '실행계획', status: 'changes_requested', version: 'v5', isAiGenerated: false, lastModified: '1일 전' },
    { id: 'doc-3', name: '자산 보고서', type: '자산보고', status: 'approved', version: 'v2', isAiGenerated: true, lastModified: '3일 전' },
    { id: 'doc-4', name: '1차 회의록', type: '회의록', status: 'draft', version: 'v1', isAiGenerated: false, lastModified: '방금' },
];

export function DocumentListPage() {
    const navigate = useNavigate();

    const columns: ColumnDef<Document>[] = [
        {
            accessorKey: 'name',
            header: '문서명',
            cell: ({ row }) => {
                return (
                    <div className="flex items-center space-x-2">
                        {row.original.isAiGenerated && <span title="AI 생성">🤖</span>}
                        {!row.original.isAiGenerated && <span title="수동 작성">📝</span>}
                        <span className="font-medium">{row.getValue('name')}</span>
                    </div>
                );
            },
        },
        {
            accessorKey: 'type',
            header: '유형',
        },
        {
            accessorKey: 'status',
            header: '상태',
            cell: ({ row }) => {
                const val = row.getValue('status') as string;
                if (val === 'in_review') return <Badge variant="secondary">● 검토중</Badge>;
                if (val === 'approved') return <Badge variant="default">✓ 승인됨</Badge>;
                if (val === 'changes_requested') return <Badge variant="destructive">◐ 수정요청</Badge>;
                return <Badge variant="outline">○ 초안</Badge>;
            },
        },
        {
            accessorKey: 'version',
            header: '버전',
        },
        {
            accessorKey: 'lastModified',
            header: '최종 수정',
            cell: ({ row }) => <span className="text-neutral-400">{row.getValue('lastModified')}</span>
        },
    ];

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold mb-1">Documents</h1>
                    <p className="text-sm text-neutral-400">📁 케이스: 물류최적화 프로젝트 (2024-PRJ-100123) &gt; 문서</p>
                </div>
                <div className="space-x-2">
                    <Button variant="outline" onClick={() => navigate('/documents/new')}>+ 새 문서</Button>
                    <Button variant="default" onClick={() => navigate('/documents/new-ai')} className="bg-indigo-600 hover:bg-indigo-700">AI 생성 요청</Button>
                </div>
            </div>

            <div className="bg-neutral-900 border border-neutral-800 rounded p-4">
                <DataTable
                    columns={columns}
                    data={mockDocuments}
                    onRowClick={(row) => navigate(`/documents/${row.id}`)}
                />
            </div>
        </div>
    );
}
