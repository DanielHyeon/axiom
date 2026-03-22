/**
 * 카탈로그 요약 카드 — 개념/엔티티/지표/차원/조인/그레인 수를 보여주는 대시보드 상단
 */
import { BookOpen, Database, BarChart3, Layers, Link2, Grid3x3 } from 'lucide-react';
import type { CatalogSummary } from '../types/semantic';

interface Props {
  summary: CatalogSummary;
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const CARDS = [
  { key: 'concepts', label: '개념', icon: BookOpen, color: 'text-violet-600 bg-violet-50' },
  { key: 'entities', label: '엔티티', icon: Database, color: 'text-blue-600 bg-blue-50' },
  { key: 'measures', label: '지표', icon: BarChart3, color: 'text-emerald-600 bg-emerald-50' },
  { key: 'dimensions', label: '차원', icon: Layers, color: 'text-amber-600 bg-amber-50' },
  { key: 'joins', label: '조인', icon: Link2, color: 'text-rose-600 bg-rose-50' },
  { key: 'grains', label: '그레인', icon: Grid3x3, color: 'text-cyan-600 bg-cyan-50' },
] as const;

export function CatalogSummaryCards({ summary, activeTab, onTabChange }: Props) {
  return (
    <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
      {CARDS.map(({ key, label, icon: Icon, color }) => {
        const count = summary[key as keyof CatalogSummary] ?? 0;
        const isActive = activeTab === key;
        return (
          <button
            key={key}
            onClick={() => onTabChange(key)}
            className={`
              flex flex-col items-center gap-1 rounded-lg border p-3 transition-all
              ${isActive ? 'ring-2 ring-primary border-primary shadow-sm' : 'border-border hover:border-primary/40'}
            `}
          >
            <div className={`rounded-md p-1.5 ${color}`}>
              <Icon className="h-4 w-4" />
            </div>
            <span className="text-2xl font-bold tabular-nums">{count}</span>
            <span className="text-xs text-muted-foreground">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
