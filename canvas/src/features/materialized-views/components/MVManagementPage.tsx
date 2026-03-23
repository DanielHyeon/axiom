/**
 * MVManagementPage — Materialized View 관리 페이지
 *
 * 기능:
 * - MV 목록 테이블 (이름, 소스 테이블, 스키마, 생성일, 액션)
 * - "새 MV 생성" 모달 (이름, 소스 테이블, 스키마, 커스텀 SELECT)
 * - 행별 새로고침(Refresh) 버튼
 * - 삭제 확인 다이얼로그
 */
import { useState, useEffect, useCallback } from 'react';
import { toast } from 'sonner';
import {
  Plus,
  RefreshCw,
  Trash2,
  X,
  Loader2,
  Database,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';

import * as mvApi from '../api/mvApi';
import type { MaterializedView, MVCreatePayload } from '../api/mvApi';

// ─── 빈 폼 초기값 ───────────────────────────────────────────

const EMPTY_FORM: MVCreatePayload = {
  name: '',
  source_table: '',
  schema: 'public',
  query: '',
};

// ─── 메인 컴포넌트 ──────────────────────────────────────────

export function MVManagementPage() {
  // MV 목록 상태
  const [mvs, setMvs] = useState<MaterializedView[]>([]);
  const [loading, setLoading] = useState(true);

  // 생성 모달
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<MVCreatePayload>({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);

  // 삭제 확인 다이얼로그
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  // 새로고침 진행 중인 MV 이름
  const [refreshingName, setRefreshingName] = useState<string | null>(null);

  // ─── 데이터 로드 ───────────────────────────────────────────

  const fetchMVs = useCallback(async () => {
    setLoading(true);
    try {
      const data = await mvApi.listMVs();
      setMvs(data);
    } catch {
      toast.error('Materialized View 목록을 불러오지 못했습니다');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMVs();
  }, [fetchMVs]);

  // ─── 생성 ─────────────────────────────────────────────────

  const handleCreate = async () => {
    if (!form.name.trim()) {
      toast.error('MV 이름을 입력하세요');
      return;
    }
    if (!form.source_table.trim()) {
      toast.error('소스 테이블을 입력하세요');
      return;
    }

    setSaving(true);
    try {
      await mvApi.createMV(form);
      toast.success(`MV "${form.name}"이(가) 생성되었습니다`);
      setCreateOpen(false);
      setForm({ ...EMPTY_FORM });
      fetchMVs();
    } catch {
      toast.error('MV 생성에 실패했습니다');
    } finally {
      setSaving(false);
    }
  };

  // ─── 새로고침 ─────────────────────────────────────────────

  const handleRefresh = async (name: string) => {
    setRefreshingName(name);
    try {
      await mvApi.refreshMV(name);
      toast.success(`"${name}" 새로고침 완료`);
    } catch {
      toast.error(`"${name}" 새로고침에 실패했습니다`);
    } finally {
      setRefreshingName(null);
    }
  };

  // ─── 삭제 ─────────────────────────────────────────────────

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await mvApi.deleteMV(deleteTarget);
      toast.success(`"${deleteTarget}"이(가) 삭제되었습니다`);
      setDeleteTarget(null);
      fetchMVs();
    } catch {
      toast.error('MV 삭제에 실패했습니다');
    } finally {
      setDeleting(false);
    }
  };

  // ─── 렌더링 ───────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-6 p-6 max-w-[1200px] mx-auto">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Materialized View 관리</h1>
          <p className="text-sm text-foreground/50 mt-1">
            데이터 성능 최적화를 위한 구체화 뷰를 관리합니다
          </p>
        </div>
        <Button
          onClick={() => {
            setForm({ ...EMPTY_FORM });
            setCreateOpen(true);
          }}
          className="gap-1.5"
        >
          <Plus className="h-4 w-4" />
          새 MV 생성
        </Button>
      </div>

      {/* MV 테이블 */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
        </div>
      ) : mvs.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-foreground/40 gap-2">
          <Database className="h-8 w-8" />
          <p className="text-sm">등록된 Materialized View가 없습니다</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>이름</TableHead>
              <TableHead>소스 테이블</TableHead>
              <TableHead>스키마</TableHead>
              <TableHead>생성일</TableHead>
              <TableHead className="text-right">액션</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {mvs.map((mv) => (
              <TableRow key={mv.name}>
                {/* 이름 */}
                <TableCell className="font-medium font-mono text-sm">{mv.name}</TableCell>

                {/* 소스 테이블 */}
                <TableCell className="text-foreground/60 font-mono text-xs">
                  {mv.source_table}
                </TableCell>

                {/* 스키마 */}
                <TableCell className="text-foreground/60 text-xs">{mv.schema}</TableCell>

                {/* 생성일 */}
                <TableCell className="text-foreground/40 text-xs">
                  {mv.created_at
                    ? new Date(mv.created_at).toLocaleDateString('ko-KR')
                    : '-'}
                </TableCell>

                {/* 액션 */}
                <TableCell>
                  <div className="flex items-center justify-end gap-1">
                    {/* 새로고침 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0"
                      title="새로고침"
                      disabled={refreshingName === mv.name}
                      onClick={() => handleRefresh(mv.name)}
                    >
                      <RefreshCw
                        className={`h-3.5 w-3.5 ${refreshingName === mv.name ? 'animate-spin' : ''}`}
                      />
                    </Button>

                    {/* 삭제 */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 p-0 text-red-500 hover:text-red-600"
                      title="삭제"
                      onClick={() => setDeleteTarget(mv.name)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {/* ─── 생성 모달 ──────────────────────────────────────── */}
      {createOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => e.target === e.currentTarget && setCreateOpen(false)}
        >
          <div className="bg-card rounded-lg shadow-xl w-full max-w-lg mx-4">
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-border">
              <h2 className="text-base font-semibold">새 Materialized View 생성</h2>
              <button
                onClick={() => setCreateOpen(false)}
                className="text-foreground/40 hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* 폼 본문 */}
            <div className="flex flex-col gap-4 px-6 py-5">
              {/* MV 이름 */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">MV 이름</label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="예: mv_daily_sales_summary"
                  className="font-mono text-sm"
                />
              </div>

              {/* 소스 테이블 */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">소스 테이블</label>
                <Input
                  value={form.source_table}
                  onChange={(e) => setForm((f) => ({ ...f, source_table: e.target.value }))}
                  placeholder="예: sales_orders"
                  className="font-mono text-sm"
                />
              </div>

              {/* 스키마 */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">스키마</label>
                <Input
                  value={form.schema}
                  onChange={(e) => setForm((f) => ({ ...f, schema: e.target.value }))}
                  placeholder="public"
                  className="font-mono text-sm"
                />
              </div>

              {/* 커스텀 SELECT */}
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-foreground/70">
                  커스텀 SELECT 쿼리 (선택)
                </label>
                <Textarea
                  value={form.query ?? ''}
                  onChange={(e) => setForm((f) => ({ ...f, query: e.target.value }))}
                  placeholder="SELECT date, SUM(amount) as total FROM sales_orders GROUP BY date"
                  rows={4}
                  className="font-mono text-xs"
                />
                <p className="text-[11px] text-foreground/40">
                  비워두면 소스 테이블 전체를 복사합니다
                </p>
              </div>
            </div>

            {/* 푸터 */}
            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
              <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={saving}>
                취소
              </Button>
              <Button onClick={handleCreate} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin mr-1.5" />}
                생성
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ─── 삭제 확인 다이얼로그 ─────────────────────────── */}
      {deleteTarget && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => e.target === e.currentTarget && setDeleteTarget(null)}
        >
          <div className="bg-card rounded-lg shadow-xl w-full max-w-sm mx-4">
            <div className="px-6 py-5">
              <h3 className="text-base font-semibold text-foreground mb-2">MV 삭제 확인</h3>
              <p className="text-sm text-foreground/60">
                <span className="font-mono font-medium text-foreground">{deleteTarget}</span>
                을(를) 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border">
              <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={deleting}>
                취소
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleting}
              >
                {deleting && <Loader2 className="h-4 w-4 animate-spin mr-1.5" />}
                삭제
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
