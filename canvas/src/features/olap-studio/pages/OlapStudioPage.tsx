/**
 * OlapStudioPage — OLAP Studio 피벗 분석 페이지 (리디자인)
 *
 * .pen 디자인 사양:
 * - 레이아웃: 수직
 * - Body 내 탭 바: Models | Cubes | Pivot | NL2SQL
 *   - 활성 탭: 하단 border 2px primary, Geist 13px semibold
 * - Body: 24px 패딩, 48px 좌우, 16px gap
 * - Model Cards: 가로 행, 동일 너비, 16px gap
 *   - 흰색 카드, 12px radius, 20px padding, 12px gap
 *   - 이름: Sora 14px semibold, 설명: Geist 12px secondary, 상태 배지
 *
 * 백엔드 API 연동:
 * - GET /api/gateway/olap/cubes — 큐브 목록
 * - GET /api/gateway/olap/data-sources — 모델(데이터소스) 목록
 */
import { useState, lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { cubes as cubesApi, dataSources } from '../api/olapStudioApi';

// 하위 탭 페이지 (지연 로딩 대신 직접 import — 같은 feature 안이므로)
import { CubeManagementPage } from './CubeManagementPage';

/** 내부 피벗 탭 — 기존 OlapStudioPage 피벗 UI를 재사용 */
const PivotTab = lazy(() =>
  import('./OlapStudioPivotTab').then((m) => ({ default: m.OlapStudioPivotTab })),
);

// ── 탭 정의 ──
type TabId = 'models' | 'cubes' | 'pivot' | 'nl2sql';

interface TabDef {
  id: TabId;
  label: string;
}

const TABS: TabDef[] = [
  { id: 'models', label: 'Models' },
  { id: 'cubes', label: 'Cubes' },
  { id: 'pivot', label: 'Pivot' },
  { id: 'nl2sql', label: 'NL2SQL' },
];

// ── 상태 배지 색상 ──
function StatusBadge({ status }: { status: string }) {
  const lower = status.toLowerCase();
  const isPublished = lower === 'published' || lower === 'active';
  const isDraft = lower === 'draft';

  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold',
        isPublished && 'bg-status-success text-status-success-foreground',
        isDraft && 'bg-status-warning text-status-warning-foreground',
        !isPublished && !isDraft && 'bg-gray-100 text-gray-600',
      )}
    >
      {status}
    </span>
  );
}

export function OlapStudioPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabId>('models');

  // 데이터소스(= 모델) 목록 조회
  const modelsQuery = useQuery({
    queryKey: ['olap-studio', 'models'],
    queryFn: dataSources.list,
    staleTime: 60_000,
  });

  // 큐브 목록 조회
  const cubesQuery = useQuery({
    queryKey: ['olap-studio', 'cubes'],
    queryFn: cubesApi.list,
    staleTime: 60_000,
  });

  return (
    <div className="flex flex-col h-full bg-background">
      {/* 탭 바 — Body 영역 상단 */}
      <div className="flex items-center gap-0 px-12 border-b border-border bg-card shrink-0">
        {TABS.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'px-4 py-3 text-[13px] transition-colors relative',
                isActive
                  ? 'font-semibold text-black'
                  : 'font-normal text-text-placeholder hover:text-text-tertiary',
              )}
            >
              {tab.label}
              {/* 활성 탭 하단 2px 인디케이터 */}
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
              )}
            </button>
          );
        })}
      </div>

      {/* Body — 24px 상하 패딩, 48px 좌우 패딩, 16px gap */}
      <div className="flex-1 overflow-y-auto px-12 py-6">
        {/* Models 탭 */}
        {activeTab === 'models' && (
          <ModelsTabContent
            models={modelsQuery.data ?? []}
            isLoading={modelsQuery.isLoading}
          />
        )}

        {/* Cubes 탭 */}
        {activeTab === 'cubes' && <CubeManagementPage />}

        {/* Pivot 탭 */}
        {activeTab === 'pivot' && (
          <Suspense fallback={<LoadingFallback />}>
            <PivotTab />
          </Suspense>
        )}

        {/* NL2SQL 탭 — 추후 구현 */}
        {activeTab === 'nl2sql' && (
          <div className="flex items-center justify-center h-64 text-text-placeholder text-sm">
            NL2SQL 탐색형 질의 (준비 중)
          </div>
        )}
      </div>
    </div>
  );
}

// ── Models 탭 콘텐츠 ──

interface ModelCardData {
  id: string;
  name: string;
  source_type: string;
  is_active: boolean;
  last_health_status: string | null;
}

function ModelsTabContent({
  models,
  isLoading,
}: {
  models: ModelCardData[];
  isLoading: boolean;
}) {
  if (isLoading) return <LoadingFallback />;

  if (models.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-text-placeholder text-sm">
        등록된 모델(데이터소스)이 없습니다.
      </div>
    );
  }

  return (
    <div className="flex gap-4 flex-wrap">
      {models.map((m) => (
        <div
          key={m.id}
          className={cn(
            'flex-1 min-w-[280px] max-w-[50%]',
            // 카드: 흰색, 12px radius, 20px padding, 12px gap, 1px border
            'bg-card rounded-xl p-5 border border-border',
            'flex flex-col gap-3',
          )}
        >
          {/* 모델 이름: Sora 14px semibold */}
          <h3 className="font-heading text-sm font-semibold text-foreground">
            {m.name}
          </h3>
          {/* 설명: Geist 12px secondary */}
          <p className="text-xs text-text-secondary">
            {m.source_type}
          </p>
          {/* 상태 배지 */}
          <StatusBadge status={m.is_active ? 'Published' : 'Draft'} />
        </div>
      ))}
    </div>
  );
}

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-32">
      <Loader2 className="animate-spin text-text-placeholder" size={20} />
    </div>
  );
}
