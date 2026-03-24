import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Workflow } from 'lucide-react';
import { ROUTES } from '@/lib/routes/routes';
import { usePermission } from '@/shared/hooks/usePermission';
import {
import { useTranslation } from 'react-i18next';
 listProcessDefinitions,
 createProcessDefinition,
 type ProcessDefinitionListItem,
} from '@/lib/api/processApi';
import { EmptyState } from '@/shared/components/EmptyState';
import { ErrorState } from '@/shared/components/ErrorState';
import { ListSkeleton } from '@/shared/components/ListSkeleton';

export const ProcessDesignerListPage: React.FC = () => {
  const { t } = useTranslation();
 const canEdit = usePermission('process:initiate');
 const [searchParams] = useSearchParams();
 const fromOntology = searchParams.get('fromOntology');
 const navigate = useNavigate();
 const [boards, setBoards] = useState<ProcessDefinitionListItem[]>([]);
 const [loading, setLoading] = useState(true);
 const [error, setError] = useState<string | null>(null);
 const [creating, setCreating] = useState(false);

 const loadBoards = useCallback(async () => {
 setLoading(true);
 setError(null);
 try {
 const res = await listProcessDefinitions({ limit: 50 });
 setBoards(res.data ?? []);
 } catch (e) {
 setError(e instanceof Error ? e.message : t('processDesignerPage2.m4d421089'));
 } finally {
 setLoading(false);
 }
 }, []);

 useEffect(() => {
 loadBoards();
 }, [loadBoards]);

 const handleCreateBoard = async () => {
 setCreating(true);
 setError(null);
 try {
 const name = `Board ${new Date().toISOString().slice(0, 19).replace('T', ' ')}`;
 const res = await createProcessDefinition({
 name,
 source: 'bpmn_upload',
 bpmn_xml: '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"/>',
 });
 navigate(ROUTES.PROCESS_DESIGNER.BOARD(res.proc_def_id));
 } catch (e) {
 setError(e instanceof Error ? e.message : t('processDesignerPage2.mef0d9a16'));
 } finally {
 setCreating(false);
 }
 };

 return (
 <div className="space-y-4">
 <h1 className="text-xl font-semibold text-foreground">{t('processDesignerExt.canvas.roleDescription')}</h1>

 {fromOntology && (
 <p className="text-sm text-primary bg-blue-950/30 border border-blue-800 rounded px-3 py-2">
 {t('processDesignerPage2.fromOntology')} <code className="font-mono">{fromOntology}</code>
 </p>
 )}

 <div className="flex items-center gap-4">
 {canEdit && (
 <button
 type="button"
 onClick={handleCreateBoard}
 disabled={creating}
 className="rounded bg-primary text-primary-foreground px-4 py-2 text-sm font-medium disabled:opacity-50"
 >
 {creating ? t('dataQualityExt.creating') : t('processDesignerPage2.m0ebd2fec')}
 </button>
 )}
 <button
 type="button"
 onClick={() => loadBoards()}
 disabled={loading}
 className="rounded border border-border text-foreground px-4 py-2 text-sm disabled:opacity-50 hover:bg-muted"
 >
 {t('datasourceExt.refreshBtn')}
 </button>
 </div>

 {/* Error state */}
 {error && !loading && (
 <ErrorState message={error} onRetry={loadBoards} />
 )}

 {/* Loading state */}
 {loading && <ListSkeleton rows={4} />}

 {/* Empty state */}
 {!loading && !error && boards.length === 0 && (
 <EmptyState
 icon={Workflow}
 title={t('processDesignerPage2.msg6a50e378')}
 description={canEdit ? t('processDesignerPage2.mc4488938') : t('processDesignerPage2.m2fd4382a')}
 actionLabel={canEdit ? t('processDesignerPage2.m6f4c613b') : undefined}
 onAction={canEdit ? handleCreateBoard : undefined}
 />
 )}

 {/* Board list */}
 {!loading && !error && boards.length > 0 && (
 <ul className="divide-y divide-border border border-border rounded">
 {boards.map((b) => (
 <li key={b.proc_def_id}>
 <Link
 to={ROUTES.PROCESS_DESIGNER.BOARD(b.proc_def_id)}
 className="block px-4 py-3 hover:bg-muted text-foreground"
 >
 <span className="font-medium">{b.name}</span>
 <span className="text-muted-foreground text-sm ml-2">
 v{b.version} · {b.source}
 {b.created_at != null && ` · ${b.created_at.slice(0, 10)}`}
 </span>
 </Link>
 </li>
 ))}
 </ul>
 )}

 <Link to={ROUTES.DASHBOARD} className="text-primary hover:underline text-sm">
 {t('processDesignerPage2.mbbcea42e')}
 </Link>
 </div>
 );
};
