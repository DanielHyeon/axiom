/**
 * 카탈로그 요약 카드 — 11탭 브라우저 상단 네비게이션
 *
 * CatalogSummary에 없는 탭은 extraCounts prop으로 별도 전달한다.
 * 모바일 4열 → 데스크톱 자동 맞춤 반응형 그리드 적용.
 */
import {
  BookOpen, Database, BarChart3, Layers, Link2, Grid3x3, GitBranch,
  GitFork, Scale, Tags, Puzzle,
} from 'lucide-react';
import type { CatalogSummary } from '../types/semantic';

interface Props {
  summary: CatalogSummary;
  activeTab: string;
  onTabChange: (tab: string) => void;
  /** CatalogSummary에 없는 탭의 카운트를 전달 (runtime, relations, rules, aliases, l2-extended) */
  extraCounts?: Record<string, number>;
}

const CARDS = [
  { key: 'concepts', label: '개념', icon: BookOpen, color: 'text-violet-600 bg-violet-50' },
  { key: 'entities', label: '엔티티', icon: Database, color: 'text-blue-600 bg-blue-50' },
  { key: 'measures', label: '지표', icon: BarChart3, color: 'text-emerald-600 bg-emerald-50' },
  { key: 'dimensions', label: '차원', icon: Layers, color: 'text-amber-600 bg-amber-50' },
  { key: 'joins', label: '조인', icon: Link2, color: 'text-rose-600 bg-rose-50' },
  { key: 'grains', label: '그레인', icon: Grid3x3, color: 'text-cyan-600 bg-cyan-50' },
  { key: 'runtime', label: '런타임', icon: GitBranch, color: 'text-indigo-600 bg-indigo-50' },
  { key: 'relations', label: '관계', icon: GitFork, color: 'text-purple-600 bg-purple-50' },
  { key: 'rules', label: '규칙/정책', icon: Scale, color: 'text-orange-600 bg-orange-50' },
  { key: 'aliases', label: '별칭', icon: Tags, color: 'text-teal-600 bg-teal-50' },
  { key: 'l2-extended', label: 'L2 확장', icon: Puzzle, color: 'text-pink-600 bg-pink-50' },
] as const;

export function CatalogSummaryCards({ summary, activeTab, onTabChange, extraCounts = {} }: Props) {
  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-11 gap-1.5 sm:gap-2">
      {CARDS.map(({ key, label, icon: Icon, color }) => {
        // CatalogSummary에 있는 키는 summary에서, 나머지는 extraCounts에서 조회
        const count = (key in summary)
          ? (summary[key as keyof CatalogSummary] ?? 0)
          : (extraCounts[key] ?? 0);
        const isActive = activeTab === key;
        return (
          <button
            key={key}
            onClick={() => onTabChange(key)}
            className={`
              flex flex-col items-center gap-1 rounded-lg border p-2 transition-all min-w-0
              ${isActive ? 'ring-2 ring-primary border-primary shadow-sm' : 'border-border hover:border-primary/40'}
            `}
          >
            <div className={`rounded-md p-1.5 ${color}`}>
              <Icon className="h-4 w-4" />
            </div>
            <span className="text-lg md:text-xl font-bold tabular-nums">{count}</span>
            <span className="text-[10px] md:text-[11px] text-muted-foreground truncate w-full text-center">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
