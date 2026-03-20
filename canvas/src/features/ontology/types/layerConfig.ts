import type { OntologyLayer } from './ontology';

/**
 * 5계층 온톨로지 레이어별 시각화 설정.
 * 순서: KPI > Driver > Measure > Process > Resource (상위 → 하위)
 */
export const LAYER_CONFIG: Record<
  OntologyLayer,
  { label: string; color: string; bgClass: string; icon: string; shape: string }
> = {
  kpi: {
    label: 'KPI',
    color: '#EF4444',       // red-500
    bgClass: 'bg-destructive',
    icon: 'BarChart3',
    shape: 'ellipse',
  },
  driver: {
    label: 'Driver',
    color: '#F59E0B',       // amber-500
    bgClass: 'bg-amber-500',
    icon: 'TrendingUp',
    shape: 'hexagon',       // Driver 전용 육각형
  },
  measure: {
    label: 'Measure',
    color: '#F97316',       // orange-500
    bgClass: 'bg-warning',
    icon: 'Calculator',
    shape: 'diamond',
  },
  process: {
    label: 'Process',
    color: '#3B82F6',       // blue-500
    bgClass: 'bg-primary',
    icon: 'Cog',
    shape: 'round-rectangle',
  },
  resource: {
    label: 'Resource',
    color: '#10B981',       // emerald-500
    bgClass: 'bg-success',
    icon: 'Server',
    shape: 'rectangle',
  },
};

/** 레이어 순서 배열 (상위 → 하위) */
export const LAYER_ORDER: OntologyLayer[] = ['kpi', 'driver', 'measure', 'process', 'resource'];

/** 관계 타입 한글 ↔ 영문 매핑 */
export const RELATION_MAP: Record<string, string> = {
  ACHIEVES: '달성',
  MEASURES: '측정',
  PARTICIPATES: '참여',
  MAPS_TO: '매핑',
  CAUSES: '인과',
  INFLUENCES: '영향',
  PRODUCES: '생산',
  USED_WHEN: '사용',
  RELATED_TO: '관련',
};
