/**
 * DataSourcesPage -- OLAP 데이터소스 관리.
 *
 * 데이터소스 목록, 생성, 연결 테스트를 제공한다.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import {
  Database,
  Plus,
  Trash2,
  Zap,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { dataSources, type DataSource } from '../api/olapStudioApi';

export function DataSourcesPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState('POSTGRES');

  // ─── 목록 조회 ──────────────────────────────────────────
  const { data: sources = [], isLoading } = useQuery({
    queryKey: ['olap', 'data-sources'],
    queryFn: dataSources.list,
  });

  // ─── 생성 ───────────────────────────────────────────────
  const createMut = useMutation({
    mutationFn: () =>
      dataSources.create({
        name: formName,
        source_type: formType,
        connection_config: {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['olap', 'data-sources'] });
      setShowForm(false);
      setFormName('');
    },
  });

  // ─── 삭제 ───────────────────────────────────────────────
  const deleteMut = useMutation({
    mutationFn: dataSources.delete,
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['olap', 'data-sources'] }),
  });

  // ─── 연결 테스트 ────────────────────────────────────────
  const [testResult, setTestResult] = useState<
    Record<string, { status: string; message: string }>
  >({});
  const testMut = useMutation({
    mutationFn: dataSources.test,
    onSuccess: (data, dsId) => {
      setTestResult((prev) => ({ ...prev, [dsId]: data }));
    },
  });

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-6 h-12 border-b border-[#E5E5E5] bg-[#FAFAFA] shrink-0">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-blue-500" />
          <h1 className="text-[14px] font-semibold font-[Sora]">
            데이터 소스
          </h1>
          <span className="text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
            {sources.length}개
          </span>
        </div>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="h-3 w-3 mr-1" /> 추가
        </Button>
      </div>

      {/* 생성 폼 */}
      {showForm && (
        <div className="px-6 py-4 bg-blue-50/50 border-b border-[#E5E5E5] space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px] font-[IBM_Plex_Mono]">이름</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="데이터소스 이름"
                className="text-[12px] font-[IBM_Plex_Mono]"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px] font-[IBM_Plex_Mono]">유형</Label>
              <select
                value={formType}
                onChange={(e) => setFormType(e.target.value)}
                className="w-full rounded border border-[#E5E5E5] bg-white px-2 py-1.5 text-[12px] font-[IBM_Plex_Mono]"
              >
                <option value="POSTGRES">PostgreSQL</option>
                <option value="MYSQL">MySQL</option>
                <option value="ORACLE">Oracle</option>
                <option value="CSV">CSV</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowForm(false)}
            >
              취소
            </Button>
            <Button
              size="sm"
              onClick={() => createMut.mutate()}
              disabled={!formName.trim()}
            >
              {createMut.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                '생성'
              )}
            </Button>
          </div>
        </div>
      )}

      {/* 목록 */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
          </div>
        )}

        {!isLoading && sources.length === 0 && (
          <div className="text-center py-12">
            <Database className="h-8 w-8 text-foreground/15 mx-auto mb-3" />
            <p className="text-[12px] text-foreground/40 font-[IBM_Plex_Mono]">
              등록된 데이터소스가 없습니다
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sources.map((ds) => (
            <div
              key={ds.id}
              className="border border-[#E5E5E5] rounded-lg p-4 bg-white hover:shadow-sm transition-shadow"
            >
              {/* 카드 헤더: 이름 + 상태 */}
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-blue-400" />
                  <span className="text-[13px] font-semibold font-[Sora]">
                    {ds.name}
                  </span>
                </div>
                <span
                  className={cn(
                    'text-[9px] px-1.5 py-0.5 rounded font-[IBM_Plex_Mono]',
                    ds.is_active
                      ? 'bg-green-50 text-green-600'
                      : 'bg-red-50 text-red-500',
                  )}
                >
                  {ds.is_active ? '활성' : '비활성'}
                </span>
              </div>

              {/* 유형 표시 */}
              <div className="text-[10px] text-foreground/50 font-[IBM_Plex_Mono] mb-3">
                {ds.source_type}
              </div>

              {/* 연결 테스트 결과 */}
              {testResult[ds.id] && (
                <div
                  className={cn(
                    'flex items-center gap-1 text-[10px] font-[IBM_Plex_Mono] mb-2',
                    testResult[ds.id].status === 'OK'
                      ? 'text-green-600'
                      : 'text-red-500',
                  )}
                >
                  {testResult[ds.id].status === 'OK' ? (
                    <CheckCircle className="h-3 w-3" />
                  ) : (
                    <XCircle className="h-3 w-3" />
                  )}
                  {testResult[ds.id].message}
                </div>
              )}

              {/* 액션 버튼 */}
              <div className="flex items-center gap-2 pt-2 border-t border-[#F0F0F0]">
                <button
                  onClick={() => testMut.mutate(ds.id)}
                  className="flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-600 font-[IBM_Plex_Mono]"
                  disabled={testMut.isPending}
                >
                  <Zap className="h-3 w-3" /> 연결 테스트
                </button>
                <button
                  onClick={() => deleteMut.mutate(ds.id)}
                  className="flex items-center gap-1 text-[10px] text-red-400 hover:text-red-500 font-[IBM_Plex_Mono] ml-auto"
                >
                  <Trash2 className="h-3 w-3" /> 삭제
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
