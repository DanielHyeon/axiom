import { useNavigate, useParams } from 'react-router-dom';
import { DataTable } from '@/components/shared/DataTable';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ROUTES } from '@/lib/routes/routes';
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

const MOCK_DOC_IDS = [
 'd4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a',
 'e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b',
 'f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c',
 'a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d',
];

const mockDocuments: Document[] = [
 { id: MOCK_DOC_IDS[0], name: '이해관계자목록v3', type: '참여자목록', status: 'in_review', version: 'v3', isAiGenerated: true, lastModified: '2시간 전' },
 { id: MOCK_DOC_IDS[1], name: '실행 계획서', type: '실행계획', status: 'changes_requested', version: 'v5', isAiGenerated: false, lastModified: '1일 전' },
 { id: MOCK_DOC_IDS[2], name: '자산 보고서', type: '자산보고', status: 'approved', version: 'v2', isAiGenerated: true, lastModified: '3일 전' },
 { id: MOCK_DOC_IDS[3], name: '1차 회의록', type: '회의록', status: 'draft', version: 'v1', isAiGenerated: false, lastModified: '방금' },
];

export function DocumentListPage() {
 const navigate = useNavigate();
 const { caseId } = useParams<{ caseId?: string }>();

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
 cell: ({ row }) => <span className="text-muted-foreground">{row.getValue('lastModified')}</span>
 },
 ];

 return (
 <div className="space-y-6">
 <div className="flex justify-between items-center">
 <div>
 <h1 className="text-2xl font-bold mb-1">Documents</h1>
 <p className="text-sm text-muted-foreground">📁 케이스: 물류최적화 프로젝트 (2024-PRJ-100123) &gt; 문서</p>
 </div>
 <div className="space-x-2">
 <Button variant="outline" onClick={() => navigate('/documents/new')}>+ 새 문서</Button>
 <Button variant="default" onClick={() => navigate('/documents/new-ai')} className="bg-primary hover:bg-primary/90">AI 생성 요청</Button>
 </div>
 </div>

 <div className="bg-card border border-border rounded p-4">
 <DataTable
 columns={columns}
 data={mockDocuments}
 onRowClick={(row) =>
 caseId
 ? navigate(ROUTES.CASES.DOCUMENT(caseId, row.id))
 : navigate(`/documents/${row.id}`)
 }
 />
 </div>
 </div>
 );
}
