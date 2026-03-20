// features/process-designer/utils/connectionRules.ts
// 소스/타겟 노드 타입에 따른 연결선 타입 자동 결정 (설계 §3.1)

import type { CanvasItemType, ConnectionType } from '../types/processDesigner';

/**
 * 소스/타겟 노드 타입에 따라 연결선 타입을 자동 결정한다.
 *
 * | 소스                | 타겟              | 결과          |
 * |---------------------|-------------------|---------------|
 * | businessAction      | businessEvent     | triggers      |
 * | businessRule        | businessEvent     | reacts_to     |
 * | businessEvent       | businessEntity    | produces      |
 * | eventLogBinding     | businessEvent     | binds_to      |
 * | 그 외                | 그 외             | triggers      |
 */
export function inferConnectionType(
  sourceType: CanvasItemType,
  targetType: CanvasItemType,
): ConnectionType {
  if (sourceType === 'businessAction' && targetType === 'businessEvent') return 'triggers';
  if (sourceType === 'businessRule' && targetType === 'businessEvent') return 'reacts_to';
  if (sourceType === 'businessEvent' && targetType === 'businessEntity') return 'produces';
  if (sourceType === 'eventLogBinding' && targetType === 'businessEvent') return 'binds_to';
  return 'triggers';
}
