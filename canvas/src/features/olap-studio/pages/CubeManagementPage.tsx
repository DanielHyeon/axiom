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
import { useTranslation } from 'react-i18next';

// ─── 상태 배지 스타일 ─────────────────────────────────────

const CUBE_STATUS_STYLE: Record<string, string> = {
  DRAFT: 'bg-gray-100 text-gray-500',
  VALIDATED: 'bg-blue-50 text-blue-600',
  PUBLISHED: 'bg-green-50 text-green-600',
};

// ─── 컴포넌트 ─────────────────────────────────────────────

export function CubeManagementPage() {
  const { t } = useTranslation();
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
      <div className="flex items-center justify-between px-6 h-12 border-b border-border bg-muted/50 shrink-0">
        <div className="flex items-center gap-2">
          <Box className="h-4 w-4 text-amber-500" />
          <h1 className="text-[14px] font-semibold font-heading">{t('olapStudio.cubes.title')}</h1>
          <span className="text-[11px] text-foreground/40 font-mono">
            {t('olapStudioF.cubeListCount', { count: cubeList.length })}
          </span>
        </div>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="h-3 w-3 mr-1" /> {t('common.add')}
        </Button>
      </div>

      {/* 생성 폼 */}
      {showForm && (
        <div className="px-6 py-4 bg-amber-50/30 border-b border-border space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label className="text-[11px] font-mono">{t('mvExt.colName')}</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder={t('olapStudioExt.cubeName')}
                className="text-[12px] font-mono"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px] font-mono">{t('objectExplorerExt.descLabel')}</Label>
              <Input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder={t('olapStudioExt.descriptionOpt')}
                className="text-[12px] font-mono"
              />
            </div>
            <div className="flex items-end gap-2 pb-0.5">
              <label className="flex items-center gap-1.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formAi}
                  onChange={(e) => setFormAi(e.target.checked)}
                  className="rounded border-border"
                />
                <span className="text-[11px] font-mono text-foreground/60">
                  {t('olapStudioF.mdbed573d')}
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
              {t('common.cancel')}
            </Button>
            <Button
              size="sm"
              onClick={() => createMut.mutate()}
              disabled={!formName.trim()}
            >
              {createMut.isPending ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                {t('olapStudioF.m1bfb7f83')}
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
            <p className="text-[12px] text-foreground/40 font-mono">
              {t('olapStudio.cubes.noCubes')}
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
      className="border border-border rounded-lg p-4 bg-card hover:shadow-sm transition-shadow cursor-pointer"
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onSelect()}
      aria-label={t('olapStudioF.cubeDetailLabel', { name: cube.name })}
    >
      {/* 헤더: 이름 + 상태 */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <Box className="h-4 w-4 text-amber-400" />
          <span className="text-[13px] font-semibold font-heading">
            {cube.name}
          </span>
        </div>
        <span
          className={cn(
            'text-[9px] px-1.5 py-0.5 rounded font-mono shrink-0',
            statusStyle,
          )}
        >
          {cube.cube_status}
        </span>
      </div>

      {/* 설명 */}
      {cube.description && (
        <p className="text-[10px] text-foreground/40 font-mono mb-2 line-clamp-2">
          {cube.description}
        </p>
      )}

      {/* AI 생성 표시 */}
      {cube.ai_generated && (
        <div className="flex items-center gap-1 text-[9px] text-purple-500 font-mono mb-2">
          <Sparkles className="h-2.5 w-2.5" /> {t('olapStudioF.aiAutoGenerate')}
        </div>
      )}

      {/* 검증 에러 표시 */}
      {validationErrors && validationErrors.length > 0 && (
        <div className="flex items-start gap-1 text-[9px] text-red-400 font-mono mb-2">
          <AlertTriangle className="h-2.5 w-2.5 mt-0.5 shrink-0" />
          <span>{t('olapStudioF.msg9d3d9396')}</span>
        </div>
      )}

      {/* 메타 정보 */}
      <div className="text-[9px] text-foreground/30 font-mono mb-3">
        v{cube.version_no} | {new Date(cube.created_at).toLocaleDateString('ko-KR')}
      </div>

      {/* 액션 버튼 */}
      <div
        className="flex items-center gap-2 pt-2 border-t border-border"
        onClick={(e) => e.stopPropagation()}
      >
        {/* 검증 버튼 — DRAFT 상태에서 활성 */}
        <button
          onClick={onValidate}
          disabled={isValidating || cube.cube_status === 'PUBLISHED'}
          className={cn(
            'flex items-center gap-1 text-[10px] font-mono transition-colors',
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
          {t('olapStudioExt.validate')}
        </button>

        {/* 게시 버튼 — VALIDATED 상태에서만 활성 */}
        <button
          onClick={onPublish}
          disabled={isPublishing || cube.cube_status !== 'VALIDATED'}
          className={cn(
            'flex items-center gap-1 text-[10px] font-mono ml-auto transition-colors',
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
          {t('olapStudio.cubes.publish')}
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
      <div className="flex items-center gap-3 px-6 h-12 border-b border-border bg-muted/50 shrink-0">
        <button
          onClick={onBack}
          className="text-foreground/40 hover:text-foreground/70 transition-colors"
          aria-label={t('olapStudioExt.backToList')}
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <Box className="h-4 w-4 text-amber-500" />
        <h1 className="text-[14px] font-semibold font-heading">{cube.name}</h1>
        <span className={cn('text-[9px] px-1.5 py-0.5 rounded font-mono', statusStyle)}>
          {cube.cube_status}
        </span>
        {cube.ai_generated && (
          <span className="text-[9px] text-purple-500 font-mono flex items-center gap-1">
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
            {t('olapStudioExt.validate')}
          </Button>
          <Button
            size="sm"
            onClick={onPublish}
            disabled={isPublishing || cube.cube_status !== 'VALIDATED'}
          >
            {isPublishing ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Upload className="h-3 w-3 mr-1" />}
            {t('olapStudio.cubes.publish')}
          </Button>
        </div>
      </div>

      {/* 본문 */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {/* 설명 */}
        {cube.description && (
          <p className="text-[12px] text-foreground/60 font-mono">
            {cube.description}
          </p>
        )}

        {/* 검증 에러 */}
        {validationErrors.length > 0 && (
          <div className="border border-red-200 rounded-lg p-3 bg-red-50/50 space-y-1">
            <p className="text-[11px] font-semibold text-red-600 font-heading flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> {t('olapStudioF.validationErrors')}
            </p>
            {validationErrors.map((err, i) => (
              <p key={i} className="text-[10px] text-red-500 font-mono">
                - {err}
              </p>
            ))}
          </div>
        )}

        {/* 차원 목록 */}
        <section>
          <h2 className="text-[12px] font-semibold font-heading mb-2 text-foreground/70">
            {t('olapStudioF.dimensionsCount', { count: cube.dimensions.length })}
          </h2>
          {cube.dimensions.length === 0 ? (
            <p className="text-[10px] text-foreground/30 font-mono">
              {t('olapStudioF.m0cc96919')}
            </p>
          ) : (
            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-[11px] font-mono">
                <thead>
                  <tr className="bg-muted/50 text-foreground/50">
                    <th className="text-left px-3 py-1.5 font-medium">{t('mvExt.colName')}</th>
                    <th className="text-left px-3 py-1.5 font-medium">{t('domainExt.fieldEditor.sourceColumn')}</th>
                    <th className="text-left px-3 py-1.5 font-medium">{t('olapStudioExt.hierarchy')}</th>
                  </tr>
                </thead>
                <tbody>
                  {cube.dimensions.map((dim) => (
                    <tr key={dim.id} className="border-t border-border">
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
          <h2 className="text-[12px] font-semibold font-heading mb-2 text-foreground/70">
            {t('olapStudioF.measuresCount', { count: cube.measures.length })}
          </h2>
          {cube.measures.length === 0 ? (
            <p className="text-[10px] text-foreground/30 font-mono">
              {t('olapStudioF.mc0563a27')}
            </p>
          ) : (
            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-[11px] font-mono">
                <thead>
                  <tr className="bg-muted/50 text-foreground/50">
                    <th className="text-left px-3 py-1.5 font-medium">{t('mvExt.colName')}</th>
                    <th className="text-left px-3 py-1.5 font-medium">{t('dataQualityExt.detailLabels.expression')}</th>
                    <th className="text-left px-3 py-1.5 font-medium">{t('olapStudioExt.aggregation')}</th>
                  </tr>
                </thead>
                <tbody>
                  {cube.measures.map((m) => (
                    <tr key={m.id} className="border-t border-border">
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
