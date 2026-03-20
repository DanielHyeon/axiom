// @ts-nocheck
// features/process-designer/components/mining/ConformanceOverlay.tsx
// 캔버스 위 적합성/병목/이탈 경로 오버레이 렌더링 (설계 §5.1, §10.4 시각 대체)

import { Fragment } from 'react';
import { Rect, Text, Arrow } from 'react-konva';
import type { CanvasItem } from '../../types/processDesigner';
import type { BottleneckResult, ConformanceResult } from '../../api/processDesignerApi';
import { computeEdgePoints } from '../../utils/edgePoints';

interface ConformanceOverlayProps {
 items: CanvasItem[];
 bottlenecks: BottleneckResult | null;
 conformance: ConformanceResult | null;
 /** 현재 선택된 변형 인덱스 (null이면 전체 표시) */
 selectedVariant: number | null;
}

/** SLA 상태에 따른 색상 + 아이콘 (§10.4 시각 대체 — 색상에만 의존하지 않음) */
function severityColor(severity: 'low' | 'medium' | 'high'): string {
 if (severity === 'high') return '#ef4444';
 if (severity === 'medium') return '#f97316';
 return '#22c55e';
}

function severityIcon(severity: 'low' | 'medium' | 'high'): string {
 if (severity === 'high') return '✕';
 if (severity === 'medium') return '⚠';
 return '✓';
}

function severityLabel(severity: 'low' | 'medium' | 'high'): string {
 if (severity === 'high') return '병목(심각)';
 if (severity === 'medium') return '병목(주의)';
 return '정상';
}

/**
 * 활동명 → 캔버스 아이템 매칭 (label 기준).
 * 정확 매칭 없으면 부분 포함(includes) 시도.
 */
function findItemByActivity(items: CanvasItem[], activityName: string): CanvasItem | undefined {
 return (
 items.find((it) => it.label === activityName) ??
 items.find((it) => it.label.includes(activityName) || activityName.includes(it.label))
 );
}

export function ConformanceOverlay({
 items,
 bottlenecks,
 conformance,
 selectedVariant,
}: ConformanceOverlayProps) {
 return (
 <>
 {/* (a) 병목 하이라이트 */}
 {bottlenecks?.bottlenecks.map((bn) => {
 const node = findItemByActivity(items, bn.activityName);
 if (!node) return null;
 const color = severityColor(bn.severity);

 return (
 <Fragment key={`bn-${bn.activityName}`}>
 <Rect
 x={node.x - 4}
 y={node.y - 4}
 width={node.width + 8}
 height={node.height + 8}
 fill={`${color}15`}
 stroke={color}
 strokeWidth={2}
 cornerRadius={6}
 dash={bn.severity === 'high' ? undefined : [8, 4]}
 listening={false}
 />
 {/* 병목 레이블 — §10.4: 색상 + 아이콘 + 텍스트 병기 */}
 <Text
 x={node.x}
 y={node.y - 18}
 text={`${severityIcon(bn.severity)} ${severityLabel(bn.severity)} · ${bn.avgWaitTime.toFixed(0)}분 (${(bn.slaViolationRate * 100).toFixed(0)}% 위반)`}
 fontSize={10}
 fontFamily="system-ui, sans-serif"
 fill={color}
 listening={false}
 />
 </Fragment>
 );
 })}

 {/* (b) 이탈 경로 점선 */}
 {conformance?.deviations
 .filter((_, i) => selectedVariant === null || selectedVariant === i)
 .map((dev, i) => {
 // 경로의 연속 노드 쌍에 대해 화살표 렌더링
 const segments: JSX.Element[] = [];
 for (let j = 0; j < dev.path.length - 1; j++) {
 const srcNode = findItemByActivity(items, dev.path[j]);
 const tgtNode = findItemByActivity(items, dev.path[j + 1]);
 if (!srcNode || !tgtNode) continue;

 const [sx, sy, tx, ty] = computeEdgePoints(srcNode, tgtNode);
 const strokeW = Math.max(1.5, Math.min(dev.frequency * 0.3, 6));

 segments.push(
 <Arrow
 key={`dev-${i}-${j}`}
 points={[sx, sy, tx, ty]}
 stroke="#94a3b8"
 strokeWidth={strokeW}
 fill="#94a3b8"
 pointerLength={6}
 pointerWidth={6}
 dash={[10, 5]}
 opacity={0.6}
 listening={false}
 />,
 );
 }

 // 빈도 라벨 (첫 번째 세그먼트에)
 if (dev.path.length >= 2 && segments.length > 0) {
 const src = findItemByActivity(items, dev.path[0]);
 const tgt = findItemByActivity(items, dev.path[1]);
 if (src && tgt) {
 segments.push(
 <Text
 key={`dev-lbl-${i}`}
 x={(src.x + src.width / 2 + tgt.x + tgt.width / 2) / 2}
 y={(src.y + src.height / 2 + tgt.y + tgt.height / 2) / 2 - 12}
 text={`${dev.frequency}건 (${dev.percentage.toFixed(1)}%)`}
 fontSize={9}
 fontFamily="system-ui, sans-serif"
 fill="#94a3b8"
 listening={false}
 />,
 );
 }
 }

 return segments;
 })}

 {/* (c) SLA 상태 아이콘 — §10.4: 색상 + 아이콘 병기 (✓ ok, ⚠ warning, ✕ violation) */}
 {items
 .filter((it) => it.temporal?.status && it.temporal.status !== 'ok')
 .map((it) => {
 const status = it.temporal!.status!;
 const icon = status === 'violation' ? '✕' : '⚠';
 const color = status === 'violation' ? '#ef4444' : '#f97316';
 const label = status === 'violation' ? 'SLA 위반' : 'SLA 주의';

 return (
 <Text
 key={`sla-${it.id}`}
 x={it.x + it.width - 8}
 y={it.y + it.height + 3}
 text={`${icon} ${label}`}
 fontSize={9}
 fontFamily="system-ui, sans-serif"
 fill={color}
 listening={false}
 />
 );
 })}
 </>
 );
}
