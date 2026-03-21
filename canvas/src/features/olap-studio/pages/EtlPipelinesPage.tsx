/**
 * EtlPipelinesPage -- ETL 파이프라인 관리.
 *
 * 파이프라인 목록, 생성, 실행, 실행 이력 조회를 제공한다.
 * 상태: DRAFT(회색) / READY(파랑) / DEPLOYED(초록) / ERROR(빨강)
 * 실행 상태: QUEUED(노랑) / RUNNING(파랑 스피너) / SUCCEEDED(초록) / FAILED(빨강)
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import {
  GitBranch,
  Plus,
  Play,
  ChevronDown,
  ChevronRight,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { etlPipelines, type ETLPipeline, type ETLRun } from '../api/olapStudioApi';

// ─── 상태 배지 색상 매핑 ─────────────────────────────────

/** 파이프라인 상태에 따른 배지 스타일 */
const PIPELINE_STATUS_STYLE: Record<string, string> = {
  DRAFT: 'bg-gray-100 text-gray-500',
  READY: 'bg-blue-50 text-blue-600',
  DEPLOYED: 'bg-green-50 text-green-600',
  ERROR: 'bg-red-50 text-red-500',
};

/** 실행 상태에 따른 배지 스타일 */
const RUN_STATUS_STYLE: Record<string, string> = {
  QUEUED: 'bg-yellow-50 text-yellow-600',
  RUNNING: 'bg-blue-50 text-blue-600',
  SUCCEEDED: 'bg-green-50 text-green-600',
  FAILED: 'bg-red-50 text-red-500',
};

// ─── 컴포넌트 ─────────────────────────────────────────────

export function EtlPipelinesPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formType, setFormType] = useState('FULL');
  // 행 확장 상태 — 실행 이력을 볼 파이프라인 ID
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // 목록 조회
  const { data: pipelines = [], isLoading } = useQuery({
    queryKey: ['olap', 'etl-pipelines'],
    queryFn: etlPipelines.list,
  });

  // 생성
  const createMut = useMutation({
    mutationFn: () =>
      etlPipelines.create({
        name: formName,
        description: formDesc,
        pipeline_type: formType,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['olap', 'etl-pipelines'] });
      setShowForm(false);
      setFormName('');
      setFormDesc('');
    },
  });

  // 수동 실행
  const runMut = useMutation({
    mutationFn: etlPipelines.run,
    onSuccess: (_data, pipelineId) => {
      // 실행 이력 갱신 + 확장 열기
      qc.invalidateQueries({ queryKey: ['olap', 'etl-runs', pipelineId] });
      setExpandedId(pipelineId);
    },
  });

  // 실행 이력 조회 — 확장된 파이프라인에 대해서만
  const { data: runs = [] } = useQuery({
    queryKey: ['olap', 'etl-runs', expandedId],
    queryFn: () => etlPipelines.listRuns(expandedId!),
    enabled: !!expandedId,
  });

  /** 행 토글 — 동일 ID면 접기, 다른 ID면 열기 */
  const handleToggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-6 h-12 border-b border-[#E5E5E5] bg-[#FAFAFA] shrink-0">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-purple-500" />
          <h1 className="text-[14px] font-semibold font-[Sora]">
            ETL 파이프라인
          </h1>
          <span className="text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
            {pipelines.length}개
          </span>
        </div>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="h-3 w-3 mr-1" /> 추가
        </Button>
      </div>

      {/* 생성 폼 */}
      {showForm && (
        <div className="px-6 py-4 bg-purple-50/30 border-b border-[#E5E5E5] space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px] font-[IBM_Plex_Mono]">이름</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="파이프라인 이름"
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
                <option value="FULL">전체 적재</option>
                <option value="INCREMENTAL">증분 적재</option>
                <option value="SNAPSHOT">스냅샷</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label className="text-[11px] font-[IBM_Plex_Mono]">설명</Label>
              <Input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder="설명 (선택)"
                className="text-[12px] font-[IBM_Plex_Mono]"
              />
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

      {/* 파이프라인 목록 */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
          </div>
        )}

        {!isLoading && pipelines.length === 0 && (
          <div className="text-center py-12">
            <GitBranch className="h-8 w-8 text-foreground/15 mx-auto mb-3" />
            <p className="text-[12px] text-foreground/40 font-[IBM_Plex_Mono]">
              등록된 파이프라인이 없습니다
            </p>
          </div>
        )}

        <div className="space-y-2">
          {pipelines.map((pl) => (
            <PipelineRow
              key={pl.id}
              pipeline={pl}
              isExpanded={expandedId === pl.id}
              onToggle={() => handleToggleExpand(pl.id)}
              onRun={() => runMut.mutate(pl.id)}
              isRunning={runMut.isPending}
              runs={expandedId === pl.id ? runs : []}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── 파이프라인 행 ────────────────────────────────────────

interface PipelineRowProps {
  pipeline: ETLPipeline;
  isExpanded: boolean;
  onToggle: () => void;
  onRun: () => void;
  isRunning: boolean;
  runs: ETLRun[];
}

function PipelineRow({
  pipeline,
  isExpanded,
  onToggle,
  onRun,
  isRunning,
  runs,
}: PipelineRowProps) {
  const statusStyle =
    PIPELINE_STATUS_STYLE[pipeline.status] ?? 'bg-gray-100 text-gray-500';

  return (
    <div className="border border-[#E5E5E5] rounded-lg bg-white">
      {/* 메인 행 */}
      <div className="flex items-center gap-3 px-4 py-3">
        {/* 확장 토글 */}
        <button
          onClick={onToggle}
          className="text-foreground/30 hover:text-foreground/60 transition-colors"
          aria-label={isExpanded ? '실행 이력 접기' : '실행 이력 펼치기'}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>

        {/* 파이프라인 정보 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-semibold font-[Sora] truncate">
              {pipeline.name}
            </span>
            <span
              className={cn(
                'text-[9px] px-1.5 py-0.5 rounded font-[IBM_Plex_Mono] shrink-0',
                statusStyle,
              )}
            >
              {pipeline.status}
            </span>
          </div>
          {pipeline.description && (
            <p className="text-[10px] text-foreground/40 font-[IBM_Plex_Mono] truncate mt-0.5">
              {pipeline.description}
            </p>
          )}
        </div>

        {/* 유형 */}
        <span className="text-[10px] text-foreground/40 font-[IBM_Plex_Mono] shrink-0">
          {pipeline.pipeline_type}
        </span>

        {/* 실행 버튼 */}
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => {
            e.stopPropagation();
            onRun();
          }}
          disabled={isRunning}
          className="shrink-0"
        >
          {isRunning ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <>
              <Play className="h-3 w-3 mr-1" /> 실행
            </>
          )}
        </Button>
      </div>

      {/* 확장: 실행 이력 */}
      {isExpanded && (
        <div className="border-t border-[#F0F0F0] px-4 py-3 bg-[#FAFAFA]/50">
          {runs.length === 0 ? (
            <p className="text-[10px] text-foreground/30 font-[IBM_Plex_Mono]">
              실행 이력 없음
            </p>
          ) : (
            <div className="space-y-1.5">
              <p className="text-[10px] text-foreground/40 font-[IBM_Plex_Mono] font-medium mb-2">
                최근 실행 이력
              </p>
              {runs.map((run) => (
                <RunItem key={run.id} run={run} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── 실행 이력 아이템 ─────────────────────────────────────

function RunItem({ run }: { run: ETLRun }) {
  const statusStyle =
    RUN_STATUS_STYLE[run.run_status] ?? 'bg-gray-100 text-gray-500';

  return (
    <div className="flex items-center gap-3 text-[10px] font-[IBM_Plex_Mono]">
      {/* 상태 배지 */}
      <span
        className={cn(
          'px-1.5 py-0.5 rounded shrink-0 inline-flex items-center gap-1',
          statusStyle,
        )}
      >
        {run.run_status === 'RUNNING' && (
          <Loader2 className="h-2.5 w-2.5 animate-spin" />
        )}
        {run.run_status}
      </span>

      {/* 트리거 유형 */}
      <span className="text-foreground/30">{run.trigger_type}</span>

      {/* 행 읽기/쓰기 */}
      <span className="text-foreground/40">
        {run.rows_read.toLocaleString()}R / {run.rows_written.toLocaleString()}W
      </span>

      {/* 시작 시각 */}
      {run.started_at && (
        <span className="text-foreground/30 ml-auto">
          {new Date(run.started_at).toLocaleString('ko-KR', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      )}

      {/* 에러 메시지 — 실패 시에만 */}
      {run.error_message && (
        <span className="text-red-400 truncate max-w-[200px]" title={run.error_message}>
          {run.error_message}
        </span>
      )}
    </div>
  );
}
