// features/process-designer/utils/autoLayout.ts
// pm4py 발견 결과 → 캔버스 노드/연결선 자동 배치 (설계 §7.2)

import type { CanvasItem, Connection } from '../types/processDesigner';
import type { DiscoveredProcess } from '../api/processDesignerApi';
import { NODE_CONFIGS, CONNECTION_CONFIGS } from './nodeConfig';

const H_GAP = 200;
const V_GAP = 120;
const NODE_W = NODE_CONFIGS.businessEvent.defaultWidth;
const NODE_H = NODE_CONFIGS.businessEvent.defaultHeight;
const BASE_COLOR = NODE_CONFIGS.businessEvent.color;

/**
 * 발견된 프로세스 모델을 캔버스 노드 + 연결선으로 변환하고 자동 배치.
 * - 활동 → businessEvent 노드
 * - Start 활동 → 녹색 보더, End 활동 → 빨간 보더
 * - 전이 → triggers 연결선 (빈도 비례 선 두께)
 * - 좌→우 방향 토폴로지 정렬
 */
export function layoutDiscoveredProcess(
  discovered: DiscoveredProcess,
): { items: Omit<CanvasItem, 'id'>[]; connections: Omit<Connection, 'id'>[] } {
  const { activities, transitions } = discovered;
  if (activities.length === 0) return { items: [], connections: [] };

  // 1. 토폴로지 정렬 (BFS 레벨)
  const nameToIdx = new Map(activities.map((a, i) => [a.name, i]));
  const adj = new Map<string, string[]>();
  for (const t of transitions) {
    if (!adj.has(t.source)) adj.set(t.source, []);
    adj.get(t.source)!.push(t.target);
  }

  const levels = new Map<string, number>();
  const starts = activities.filter((a) => a.isStart).map((a) => a.name);
  if (starts.length === 0 && activities.length > 0) {
    starts.push(activities[0].name);
  }

  // BFS
  const queue = starts.map((s) => ({ name: s, level: 0 }));
  for (const s of starts) levels.set(s, 0);
  while (queue.length > 0) {
    const { name, level } = queue.shift()!;
    for (const next of adj.get(name) ?? []) {
      if (!levels.has(next) || levels.get(next)! < level + 1) {
        levels.set(next, level + 1);
        queue.push({ name: next, level: level + 1 });
      }
    }
  }

  // 미방문 노드에 마지막 레벨+1 할당
  let maxLevel = 0;
  for (const l of levels.values()) if (l > maxLevel) maxLevel = l;
  for (const a of activities) {
    if (!levels.has(a.name)) levels.set(a.name, ++maxLevel);
  }

  // 2. 레벨별 그룹핑
  const byLevel = new Map<number, typeof activities>();
  for (const a of activities) {
    const lv = levels.get(a.name) ?? 0;
    if (!byLevel.has(lv)) byLevel.set(lv, []);
    byLevel.get(lv)!.push(a);
  }

  // 3. 노드 생성 (좌→우 배치)
  const items: Omit<CanvasItem, 'id'>[] = [];
  const nameToLabel = new Map<string, string>(); // 이름 기반 임시 연결용

  const sortedLevels = [...byLevel.keys()].sort((a, b) => a - b);
  for (const lv of sortedLevels) {
    const group = byLevel.get(lv)!;
    const startY = -(group.length - 1) * (NODE_H + V_GAP) / 2;

    for (let i = 0; i < group.length; i++) {
      const act = group[i];
      const label = act.name;
      nameToLabel.set(act.name, label);

      let color = BASE_COLOR;
      if (act.isStart) color = '#22c55e'; // 녹색
      if (act.isEnd) color = '#ef4444';   // 빨간

      items.push({
        type: 'businessEvent',
        x: lv * (NODE_W + H_GAP) + 100,
        y: startY + i * (NODE_H + V_GAP) + 200,
        width: NODE_W,
        height: NODE_H,
        label,
        color,
      });
    }
  }

  // 4. 연결선 생성
  const maxFreq = Math.max(...transitions.map((t) => t.frequency), 1);
  const connections: Omit<Connection, 'id'>[] = transitions.map((t) => {
    const srcIdx = nameToIdx.get(t.source);
    const tgtIdx = nameToIdx.get(t.target);
    if (srcIdx === undefined || tgtIdx === undefined) {
      return null as unknown as Omit<Connection, 'id'>;
    }

    const strokeW = Math.max(1.5, (t.frequency / maxFreq) * 5);
    return {
      type: 'triggers' as const,
      sourceId: `__placeholder_${srcIdx}`,
      targetId: `__placeholder_${tgtIdx}`,
      label: `${t.frequency}건`,
      style: {
        stroke: CONNECTION_CONFIGS.triggers.stroke,
        strokeWidth: strokeW,
        dashArray: CONNECTION_CONFIGS.triggers.dashArray,
        arrowSize: 8,
      },
    };
  }).filter(Boolean);

  return { items, connections };
}
