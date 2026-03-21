/**
 * CubeManagementPage -- OLAP 큐브 관리.
 *
 * 큐브 목록, 생성, 상세(차원+측정값), 검증/게시 워크플로를 제공한다.
 * 상태 워크플로: DRAFT -> VALIDATED -> PUBLISHED
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import {
  Box,
  Plus,
  CheckCircle,
  Upload,
  Sparkles,
  AlertTriangle,
  ArrowLeft,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cubes, type Cube, type CubeDetail } from '../api/olapStudioApi';

// ─── 상태 배지 스타일 ─────────────────────────────────────

const CUBE_STATUS_STYLE: Record<string, string> = {
  DRAFT: 'bg-gray-100 text-gray-500',
  VALIDATED: 'bg-blue-50 text-blue-600',
  PUBLISHED: 'bg-green-50 text-green-600',
};

// ─── 컴포넌트 ─────────────────────────────────────────────

export function CubeManagementPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formAi, setFormAi] = useState(false);
  // 상세 보기 대상 큐브 ID
  const [selectedId, setSelectedId] = useState<string | null>(null);
  // 검증 에러 목록 (큐브 ID -> 에러 배열)
  const [validationErrors, setValidationErrors] = useState<Record<string, string[]>>({});

  // 큐브 목록 조회
  const { data: cubeList = [], isLoading } = useQuery({
    queryKey: ['olap', 'cubes'],
    queryFn: cubes.list,
  });

  // 큐브 상세 조회 — 선택 시에만 활성화
  const { data: cubeDetail } = useQuery({
    queryKey: ['olap', 'cube-detail', selectedId],
    queryFn: () => cubes.get(selectedId!),
    enabled: !!selectedId,
  });

  // 생성
  const createMut = useMutation({
    mutationFn: () =>
      cubes.create({
        name: formName,
        description: formDesc,
        ai_generated: formAi,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['olap', 'cubes'] });
      setShowForm(false);
      setFormName('');
      setFormDesc('');
      setFormAi(false);
    },
  });

  // 검증
  const validateMut = useMutation({
    mutationFn: cubes.validate,
    onSuccess: (data, cubeId) => {
      setValidationErrors((prev) => ({ ...prev, [cubeId]: data.errors }));
      // 검증 성공 시 목록 갱신 (상태가 VALIDATED로 변경됨)
      if (data.errors.length === 0) {
        qc.invalidateQueries({ queryKey: ['olap', 'cubes'] });
        qc.invalidateQueries({ queryKey: ['olap', 'cube-detail', cubeId] });
      }
    },
  });

  // 게시
  const publishMut = useMutation({
    mutationFn: cubes.publish,
    onSuccess: (_data, cubeId) => {
      qc.invalidateQueries({ queryKey: ['olap', 'cubes'] });
      qc.invalidateQueries({ queryKey: ['olap', 'cube-detail', cubeId] });
    },
  });

  // ─── 상세 뷰 ───────────────────────────────────────────
  if (selectedId && cubeDetail) {
    return (
      <CubeDetailView
        cube={cubeDetail}
        validationErrors={validationErrors[selectedId] ?? []}
        onBack={() => setSelectedId(null)}
        onValidate={() => validateMut.mutate(selectedId)}
        onPublish={() => publishMut.mutate(selectedId)}
        isValidating={validateMut.isPending}
        isPublishing={publishMut.isPending}
      />
    );
  }

  // ─── 목록 뷰 ───────────────────────────────────────────
  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-6 h-12 border-b border-[#E5E5E5] bg-[#FAFAFA] shrink-0">
        <div className="flex items-center gap-2">
          <Box className="h-4 w-4 text-amber-500" />
          <h1 className="text-[14px] font-semibold font-[Sora]">큐브 관리</h1>
          <span className="text-[11px] text-foreground/40 font-[IBM_Plex_Mono]">
            {cubeList.length}개
          </span>
        </div>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="h-3 w-3 mr-1" /> 추가
        </Button>
      </div>

      {/* 생성 폼 */}
      {showForm && (
        <div className="px-6 py-4 bg-amber-50/30 border-b border-[#E5E5E5] space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px] font-[IBM_Plex_Mono]">이름</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="큐브 이름"
                className="text-[12px] font-[IBM_Plex_Mono]"
              />
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
            <div className="flex items-end gap-2 pb-0.5">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formAi}
                  onChange={(e) => setFormAi(e.target.checked)}
                  className="rounded border-[#E5E5E5]"
                />
                <span className="text-[11px] font-[IBM_Plex_Mono] text-foreground/60">
                  AI 자동생성
                </span>
              </label>
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

      {/* 큐브 목록 */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-foreground/30" />
          </div>
        )}

        {!isLoading && cubeList.length === 0 && (
          <div className="text-center py-12">
            <Box className="h-8 w-8 text-foreground/15 mx-auto mb-3" />
            <p className="text-[12px] text-foreground/40 font-[IBM_Plex_Mono]">
              등록된 큐브가 없습니다
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cubeList.map((cube) => (
            <CubeCard
              key={cube.id}
              cube={cube}
              validationErrors={validationErrors[cube.id]}
              onSelect={() => setSelectedId(cube.id)}
              onValidate={() => validateMut.mutate(cube.id)}
              onPublish={() => publishMut.mutate(cube.id)}
              isValidating={validateMut.isPending}
              isPublishing={publishMut.isPending}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── 큐브 카드 ────────────────────────────────────────────

interface CubeCardProps {
  cube: Cube;
  validationErrors?: string[];
  onSelect: () => void;
  onValidate: () => void;
  onPublish: () => void;
  isValidating: boolean;
  isPublishing: boolean;
}

function CubeCard({
  cube,
  validationErrors,
  onSelect,
  onValidate,
  onPublish,
  isValidating,
  isPublishing,
}: CubeCardProps) {
  const statusStyle =
    CUBE_STATUS_STYLE[cube.cube_status] ?? 'bg-gray-100 text-gray-500';

  return (
    <div
      className="border border-[#E5E5E5] rounded-lg p-4 bg-white hover:shadow-sm transition-shadow cursor-pointer"
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
      aria-label={`큐브 ${cube.name} 상세 보기`}
    >
      {/* 헤더: 이름 + 상태 */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Box className="h-4 w-4 text-amber-400" />
          <span className="text-[13px] font-semibold font-[Sora]">
            {cube.name}
          </span>
        </div>
        <span
          className={cn(
            'text-[9px] px-1.5 py-0.5 rounded font-[IBM_Plex_Mono] shrink-0',
            statusStyle,
          )}
        >
          {cube.cube_status}
        </span>
      </div>

      {/* 설명 */}
      {cube.description && (
        <p className="text-[10px] text-foreground/40 font-[IBM_Plex_Mono] mb-2 line-clamp-2">
          {cube.description}
        </p>
      )}

      {/* AI 생성 표시 */}
      {cube.ai_generated && (
        <div className="flex items-center gap-1 text-[9px] text-purple-500 font-[IBM_Plex_Mono] mb-2">
          <Sparkles className="h-2.5 w-2.5" /> AI 자동생성
        </div>
      )}

      {/* 검증 에러 표시 */}
      {validationErrors && validationErrors.length > 0 && (
        <div className="flex items-start gap-1 text-[9px] text-red-400 font-[IBM_Plex_Mono] mb-2">
          <AlertTriangle className="h-2.5 w-2.5 mt-0.5 shrink-0" />
          <span>{validationErrors.length}개 검증 오류</span>
        </div>
      )}

      {/* 메타 정보 */}
      <div className="text-[9px] text-foreground/30 font-[IBM_Plex_Mono] mb-3">
        v{cube.version_no} | {new Date(cube.created_at).toLocaleDateString('ko-KR')}
      </div>

      {/* 액션 버튼 */}
      <div
        className="flex items-center gap-2 pt-2 border-t border-[#F0F0F0]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 검증 버튼 — DRAFT 상태에서 활성 */}
        <button
          onClick={onValidate}
          disabled={isValidating || cube.cube_status === 'PUBLISHED'}
          className={cn(
            'flex items-center gap-1 text-[10px] font-[IBM_Plex_Mono] transition-colors',
            cube.cube_status === 'PUBLISHED'
              ? 'text-foreground/20 cursor-not-allowed'
              : 'text-blue-500 hover:text-blue-600',
          )}
        >
          {isValidating ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <CheckCircle className="h-3 w-3" />
          )}
          검증
        </button>

        {/* 게시 버튼 — VALIDATED 상태에서만 활성 */}
        <button
          onClick={onPublish}
          disabled={isPublishing || cube.cube_status !== 'VALIDATED'}
          className={cn(
            'flex items-center gap-1 text-[10px] font-[IBM_Plex_Mono] ml-auto transition-colors',
            cube.cube_status === 'VALIDATED'
              ? 'text-green-500 hover:text-green-600'
              : 'text-foreground/20 cursor-not-allowed',
          )}
        >
          {isPublishing ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Upload className="h-3 w-3" />
          )}
          게시
        </button>
      </div>
    </div>
  );
}

// ─── 큐브 상세 뷰 ─────────────────────────────────────────

interface CubeDetailViewProps {
  cube: CubeDetail;
  validationErrors: string[];
  onBack: () => void;
  onValidate: () => void;
  onPublish: () => void;
  isValidating: boolean;
  isPublishing: boolean;
}

function CubeDetailView({
  cube,
  validationErrors,
  onBack,
  onValidate,
  onPublish,
  isValidating,
  isPublishing,
}: CubeDetailViewProps) {
  const statusStyle =
    CUBE_STATUS_STYLE[cube.cube_status] ?? 'bg-gray-100 text-gray-500';

  return (
    <div className="flex flex-col h-full">
      {/* 헤더 */}
      <div className="flex items-center gap-3 px-6 h-12 border-b border-[#E5E5E5] bg-[#FAFAFA] shrink-0">
        <button
          onClick={onBack}
          className="text-foreground/40 hover:text-foreground/70 transition-colors"
          aria-label="목록으로 돌아가기"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <Box className="h-4 w-4 text-amber-500" />
        <h1 className="text-[14px] font-semibold font-[Sora]">{cube.name}</h1>
        <span className={cn('text-[9px] px-1.5 py-0.5 rounded font-[IBM_Plex_Mono]', statusStyle)}>
          {cube.cube_status}
        </span>
        {cube.ai_generated && (
          <span className="text-[9px] text-purple-500 font-[IBM_Plex_Mono] flex items-center gap-1">
            <Sparkles className="h-2.5 w-2.5" /> AI
          </span>
        )}

        {/* 우측 액션 */}
        <div className="flex items-center gap-2 ml-auto">
          <Button
            size="sm"
            variant="outline"
            onClick={onValidate}
            disabled={isValidating || cube.cube_status === 'PUBLISHED'}
          >
            {isValidating ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <CheckCircle className="h-3 w-3 mr-1" />}
            검증
          </Button>
          <Button
            size="sm"
            onClick={onPublish}
            disabled={isPublishing || cube.cube_status !== 'VALIDATED'}
          >
            {isPublishing ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Upload className="h-3 w-3 mr-1" />}
            게시
          </Button>
        </div>
      </div>

      {/* 본문 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* 설명 */}
        {cube.description && (
          <p className="text-[12px] text-foreground/60 font-[IBM_Plex_Mono]">
            {cube.description}
          </p>
        )}

        {/* 검증 에러 */}
        {validationErrors.length > 0 && (
          <div className="border border-red-200 rounded-lg p-3 bg-red-50/50 space-y-1">
            <p className="text-[11px] font-semibold text-red-600 font-[Sora] flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> 검증 오류
            </p>
            {validationErrors.map((err, i) => (
              <p key={i} className="text-[10px] text-red-500 font-[IBM_Plex_Mono]">
                - {err}
              </p>
            ))}
          </div>
        )}

        {/* 차원 목록 */}
        <section>
          <h2 className="text-[12px] font-semibold font-[Sora] mb-2 text-foreground/70">
            차원 ({cube.dimensions.length})
          </h2>
          {cube.dimensions.length === 0 ? (
            <p className="text-[10px] text-foreground/30 font-[IBM_Plex_Mono]">
              정의된 차원이 없습니다
            </p>
          ) : (
            <div className="border border-[#E5E5E5] rounded-lg overflow-hidden">
              <table className="w-full text-[11px] font-[IBM_Plex_Mono]">
                <thead>
                  <tr className="bg-[#FAFAFA] text-foreground/50">
                    <th className="text-left px-3 py-1.5 font-medium">이름</th>
                    <th className="text-left px-3 py-1.5 font-medium">소스 컬럼</th>
                    <th className="text-left px-3 py-1.5 font-medium">계층</th>
                  </tr>
                </thead>
                <tbody>
                  {cube.dimensions.map((dim) => (
                    <tr key={dim.id} className="border-t border-[#F0F0F0]">
                      <td className="px-3 py-1.5 text-foreground/70">{dim.name}</td>
                      <td className="px-3 py-1.5 text-foreground/40">{dim.source_column}</td>
                      <td className="px-3 py-1.5 text-foreground/40">Lv.{dim.hierarchy_level}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* 측정값 목록 */}
        <section>
          <h2 className="text-[12px] font-semibold font-[Sora] mb-2 text-foreground/70">
            측정값 ({cube.measures.length})
          </h2>
          {cube.measures.length === 0 ? (
            <p className="text-[10px] text-foreground/30 font-[IBM_Plex_Mono]">
              정의된 측정값이 없습니다
            </p>
          ) : (
            <div className="border border-[#E5E5E5] rounded-lg overflow-hidden">
              <table className="w-full text-[11px] font-[IBM_Plex_Mono]">
                <thead>
                  <tr className="bg-[#FAFAFA] text-foreground/50">
                    <th className="text-left px-3 py-1.5 font-medium">이름</th>
                    <th className="text-left px-3 py-1.5 font-medium">표현식</th>
                    <th className="text-left px-3 py-1.5 font-medium">집계</th>
                  </tr>
                </thead>
                <tbody>
                  {cube.measures.map((m) => (
                    <tr key={m.id} className="border-t border-[#F0F0F0]">
                      <td className="px-3 py-1.5 text-foreground/70">{m.name}</td>
                      <td className="px-3 py-1.5 text-foreground/40 font-mono text-[10px]">{m.expression}</td>
                      <td className="px-3 py-1.5 text-foreground/40">{m.aggregation_type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
