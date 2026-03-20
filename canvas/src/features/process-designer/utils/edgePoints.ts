// features/process-designer/utils/edgePoints.ts
// 두 노드 사이의 연결선 시작/끝 좌표를 계산 (K-AIR getEdgePoint 알고리즘 이식)

/**
 * 두 사각형 노드 간 엣지 포인트를 계산한다.
 * 노드 중심 간 각도로 상/하/좌/우 가장자리를 결정.
 *
 * @returns [sourceX, sourceY, targetX, targetY]
 */
export function computeEdgePoints(
  source: { x: number; y: number; width: number; height: number },
  target: { x: number; y: number; width: number; height: number },
): [number, number, number, number] {
  const sCx = source.x + source.width / 2;
  const sCy = source.y + source.height / 2;
  const tCx = target.x + target.width / 2;
  const tCy = target.y + target.height / 2;

  const getEdgePoint = (
    cx: number, cy: number,
    w: number, h: number, x: number, y: number,
    targetCx: number, targetCy: number,
  ) => {
    const dx = targetCx - cx;
    const dy = targetCy - cy;
    const angle = Math.atan2(dy, dx);

    if (angle > -Math.PI / 4 && angle <= Math.PI / 4)
      return { x: x + w, y: cy };                   // right
    if (angle > Math.PI / 4 && angle <= (3 * Math.PI) / 4)
      return { x: cx, y: y + h };                   // bottom
    if (angle > (3 * Math.PI) / 4 || angle <= -(3 * Math.PI) / 4)
      return { x, y: cy };                           // left
    return { x: cx, y };                             // top
  };

  const sp = getEdgePoint(sCx, sCy, source.width, source.height, source.x, source.y, tCx, tCy);
  const tp = getEdgePoint(tCx, tCy, target.width, target.height, target.x, target.y, sCx, sCy);

  return [sp.x, sp.y, tp.x, tp.y];
}
