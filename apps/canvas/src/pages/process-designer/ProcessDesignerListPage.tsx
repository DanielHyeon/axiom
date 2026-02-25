import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';
import {
  listProcessDefinitions,
  createProcessDefinition,
  type ProcessDefinitionListItem,
} from '@/lib/api/processApi';

/** 프로세스 디자이너 보드 목록. Core process definitions 연동. 온톨로지 연동: ?fromOntology=nodeId */
export const ProcessDesignerListPage: React.FC = () => {
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
      setError(e instanceof Error ? e.message : '보드 목록을 불러오지 못했습니다.');
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
      setError(e instanceof Error ? e.message : '보드 생성에 실패했습니다.');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold text-foreground">프로세스 디자이너</h1>
      {fromOntology && (
        <p className="text-sm text-blue-400 bg-blue-950/30 border border-blue-800 rounded px-3 py-2">
          온톨로지에서 이동됨: <code className="font-mono">{fromOntology}</code>
        </p>
      )}
      {error && (
        <p className="text-sm text-red-400 bg-red-950/30 border border-red-800 rounded px-3 py-2">
          {error}
        </p>
      )}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={handleCreateBoard}
          disabled={creating}
          className="rounded bg-blue-600 text-white px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {creating ? '생성 중…' : '새 보드'}
        </button>
        <button
          type="button"
          onClick={() => loadBoards()}
          disabled={loading}
          className="rounded border border-neutral-600 text-neutral-200 px-4 py-2 text-sm disabled:opacity-50 hover:bg-neutral-800"
        >
          새로고침
        </button>
      </div>
      {loading ? (
        <p className="text-sm text-neutral-400">보드 목록 로딩 중…</p>
      ) : boards.length === 0 ? (
        <p className="text-sm text-neutral-400">보드가 없습니다. 새 보드를 만들어 보세요.</p>
      ) : (
        <ul className="divide-y divide-neutral-700 border border-neutral-700 rounded">
          {boards.map((b) => (
            <li key={b.proc_def_id}>
              <Link
                to={ROUTES.PROCESS_DESIGNER.BOARD(b.proc_def_id)}
                className="block px-4 py-3 hover:bg-neutral-800 text-neutral-100"
              >
                <span className="font-medium">{b.name}</span>
                <span className="text-neutral-400 text-sm ml-2">
                  v{b.version} · {b.source}
                  {b.created_at != null && ` · ${b.created_at.slice(0, 10)}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link to={ROUTES.DASHBOARD} className="text-primary hover:underline text-sm">
        대시보드로
      </Link>
    </div>
  );
};
