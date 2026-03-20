import { describe, it, expect } from 'vitest';
import {
  formatScore,
  formatScoreRaw,
  scoreColor,
  scoreBgColor,
  scoreHexColor,
  formatBreakdownValue,
  deriveDriverRankings,
} from './scoreCalculator';
import type { GraphData, GraphMeta } from '../types/insight';

// ---------------------------------------------------------------------------
// 헬퍼
// ---------------------------------------------------------------------------

const baseMeta: GraphMeta = {
  schema_version: '1.0',
  analysis_version: '1.0',
  generated_at: '2026-03-20T00:00:00Z',
  time_range: { from: '2026-03-01', to: '2026-03-20' },
  datasource: 'test',
  cache_hit: false,
  limits: { max_nodes: 100, max_edges: 200, depth: 3 },
  truncated: false,
};

// ---------------------------------------------------------------------------
// formatScore (0~1 범위)
// ---------------------------------------------------------------------------

describe('formatScore', () => {
  it('0.81 → "81%"', () => {
    expect(formatScore(0.81)).toBe('81%');
  });

  it('0 → "0%"', () => {
    expect(formatScore(0)).toBe('0%');
  });

  it('1 → "100%"', () => {
    expect(formatScore(1)).toBe('100%');
  });

  it('0.005 → "1%" (반올림)', () => {
    expect(formatScore(0.005)).toBe('1%');
  });

  it('음수 -0.5 → "-50%"', () => {
    expect(formatScore(-0.5)).toBe('-50%');
  });
});

// ---------------------------------------------------------------------------
// formatScoreRaw (0~100 또는 0~1 범위 자동 판별)
// ---------------------------------------------------------------------------

describe('formatScoreRaw', () => {
  it('81 → "81%" (0~100 범위)', () => {
    expect(formatScoreRaw(81)).toBe('81%');
  });

  it('0.81 → "81%" (0~1 범위 자동 감지)', () => {
    expect(formatScoreRaw(0.81)).toBe('81%');
  });

  it('1 이하 값은 0~1로 취급: 1 → "100%"', () => {
    expect(formatScoreRaw(1)).toBe('100%');
  });

  it('0 → "0%"', () => {
    expect(formatScoreRaw(0)).toBe('0%');
  });
});

// ---------------------------------------------------------------------------
// scoreColor (Tailwind 텍스트 색상 클래스)
// ---------------------------------------------------------------------------

describe('scoreColor', () => {
  it('0.7 이상 → emerald (녹색)', () => {
    expect(scoreColor(0.7)).toBe('text-emerald-400');
    expect(scoreColor(0.9)).toBe('text-emerald-400');
    expect(scoreColor(1.0)).toBe('text-emerald-400');
  });

  it('0.4~0.7 미만 → yellow (노란색)', () => {
    expect(scoreColor(0.4)).toBe('text-yellow-400');
    expect(scoreColor(0.69)).toBe('text-yellow-400');
  });

  it('0.4 미만 → red (빨간색)', () => {
    expect(scoreColor(0.39)).toBe('text-red-400');
    expect(scoreColor(0)).toBe('text-red-400');
  });

  it('1 초과 값 → 0~100 범위로 정규화: 70 → emerald', () => {
    expect(scoreColor(70)).toBe('text-emerald-400');
    expect(scoreColor(40)).toBe('text-yellow-400');
    expect(scoreColor(10)).toBe('text-red-400');
  });
});

// ---------------------------------------------------------------------------
// scoreBgColor (Tailwind 배경 색상 클래스)
// ---------------------------------------------------------------------------

describe('scoreBgColor', () => {
  it('0.7 이상 → emerald 배경', () => {
    expect(scoreBgColor(0.8)).toBe('bg-emerald-400/20');
  });

  it('0.4~0.7 미만 → yellow 배경', () => {
    expect(scoreBgColor(0.5)).toBe('bg-yellow-400/20');
  });

  it('0.4 미만 → red 배경', () => {
    expect(scoreBgColor(0.1)).toBe('bg-red-400/20');
  });
});

// ---------------------------------------------------------------------------
// scoreHexColor (차트용 hex 색상)
// ---------------------------------------------------------------------------

describe('scoreHexColor', () => {
  it('0.7 이상 → #34d399 (emerald)', () => {
    expect(scoreHexColor(0.75)).toBe('#34d399');
  });

  it('0.4~0.7 미만 → #fbbf24 (yellow)', () => {
    expect(scoreHexColor(0.5)).toBe('#fbbf24');
  });

  it('0.4 미만 → #f87171 (red)', () => {
    expect(scoreHexColor(0.2)).toBe('#f87171');
  });
});

// ---------------------------------------------------------------------------
// formatBreakdownValue
// ---------------------------------------------------------------------------

describe('formatBreakdownValue', () => {
  it('양수 → "+" 접두사: 0.15 → "+15.0"', () => {
    expect(formatBreakdownValue(0.15)).toBe('+15.0');
  });

  it('0 → "+0.0"', () => {
    expect(formatBreakdownValue(0)).toBe('+0.0');
  });

  it('음수 → "-" 접두사 그대로: -0.08 → "-8.0"', () => {
    expect(formatBreakdownValue(-0.08)).toBe('-8.0');
  });
});

// ---------------------------------------------------------------------------
// deriveDriverRankings
// ---------------------------------------------------------------------------

describe('deriveDriverRankings', () => {
  it('DRIVER와 DIMENSION 노드만 추출하여 score 내림차순 정렬', () => {
    const graph: GraphData = {
      meta: baseMeta,
      nodes: [
        { id: 'kpi-1', label: 'OEE', type: 'KPI', score: 0.95 },
        { id: 'd-1', label: 'Throughput', type: 'DRIVER', score: 0.8 },
        { id: 'd-2', label: 'Quality', type: 'DRIVER', score: 0.9 },
        { id: 'dim-1', label: 'Region', type: 'DIMENSION', score: 0.5 },
        { id: 't-1', label: 'orders', type: 'TABLE' },
      ],
      edges: [],
    };

    const result = deriveDriverRankings(graph, null);

    expect(result).toHaveLength(3); // KPI와 TABLE 제외
    expect(result[0].node_id).toBe('d-2'); // score 0.9 → 1위
    expect(result[1].node_id).toBe('d-1'); // score 0.8 → 2위
    expect(result[2].node_id).toBe('dim-1'); // score 0.5 → 3위
  });

  it('score가 없는 노드 → 0으로 처리', () => {
    const graph: GraphData = {
      meta: baseMeta,
      nodes: [
        { id: 'd-1', label: 'NoScore', type: 'DRIVER' },
      ],
      edges: [],
    };

    const result = deriveDriverRankings(graph, null);
    expect(result[0].score).toBe(0);
  });

  it('impactEvidence가 있으면 evidence_count 반영', () => {
    const graph: GraphData = {
      meta: baseMeta,
      nodes: [
        { id: 'd-1', label: 'Driver', type: 'DRIVER', score: 0.7 },
      ],
      edges: [],
    };

    const evidence = {
      'd-1': [{}, {}, {}], // 3건의 증거
    };

    const result = deriveDriverRankings(graph, evidence);
    expect(result[0].evidence_count).toBe(3);
  });

  it('impactEvidence가 null이면 evidence_count 0', () => {
    const graph: GraphData = {
      meta: baseMeta,
      nodes: [
        { id: 'd-1', label: 'Driver', type: 'DRIVER', score: 0.7 },
      ],
      edges: [],
    };

    const result = deriveDriverRankings(graph, null);
    expect(result[0].evidence_count).toBe(0);
  });

  it('빈 그래프 → 빈 배열', () => {
    const graph: GraphData = { meta: baseMeta, nodes: [], edges: [] };
    const result = deriveDriverRankings(graph, null);
    expect(result).toEqual([]);
  });
});
