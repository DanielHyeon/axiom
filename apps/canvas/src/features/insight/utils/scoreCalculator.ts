// features/insight/utils/scoreCalculator.ts
// Driver importance score formatting, color utilities, and graph-derived calculations

import type { GraphData, DriverRankItem } from '../types/insight';

/**
 * Format a score (0-1 range) as a percentage string.
 * Example: 0.81 -> "81%"
 */
export function formatScore(score: number): string {
  return `${Math.round(score * 100)}%`;
}

/**
 * Format a score (0-100 range) as a percentage string.
 * Example: 81 -> "81%"
 */
export function formatScoreRaw(score: number): string {
  if (score <= 1) {
    return `${Math.round(score * 100)}%`;
  }
  return `${Math.round(score)}%`;
}

/**
 * Return a Tailwind text color class based on score (0-1 range).
 * Green >= 0.7, Yellow >= 0.4, Red < 0.4
 */
export function scoreColor(score: number): string {
  const normalized = score > 1 ? score / 100 : score;
  if (normalized >= 0.7) return 'text-emerald-400';
  if (normalized >= 0.4) return 'text-yellow-400';
  return 'text-red-400';
}

/**
 * Return a Tailwind background color class based on score (0-1 range).
 */
export function scoreBgColor(score: number): string {
  const normalized = score > 1 ? score / 100 : score;
  if (normalized >= 0.7) return 'bg-emerald-400/20';
  if (normalized >= 0.4) return 'bg-yellow-400/20';
  return 'bg-red-400/20';
}

/**
 * Return a hex color for score (for chart / graph usage).
 */
export function scoreHexColor(score: number): string {
  const normalized = score > 1 ? score / 100 : score;
  if (normalized >= 0.7) return '#34d399';
  if (normalized >= 0.4) return '#fbbf24';
  return '#f87171';
}

/**
 * Format a breakdown factor value for display.
 * Positive values get a "+" prefix, negative as-is.
 */
export function formatBreakdownValue(value: number): string {
  const pct = (value * 100).toFixed(1);
  return value >= 0 ? `+${pct}` : pct;
}

// ---------------------------------------------------------------------------
// Graph-derived utilities
// ---------------------------------------------------------------------------

/**
 * Derive a sorted DriverRankItem list from impact graph data.
 * Includes DRIVER and DIMENSION nodes, sorted by score descending.
 * Evidence count is estimated from KPI→node INFLUENCES edge presence.
 */
export function deriveDriverRankings(
  graph: GraphData,
  impactEvidence: Record<string, unknown[]> | null,
): DriverRankItem[] {
  const nodes = (graph.nodes ?? []).filter(
    (n) => n.type === 'DRIVER' || n.type === 'DIMENSION',
  );

  return nodes
    .map((n) => ({
      node_id: n.id,
      label: n.label,
      type: n.type,
      score: n.score ?? 0,
      evidence_count: impactEvidence?.[n.id]?.length ?? 0,
    }))
    .sort((a, b) => b.score - a.score);
}
