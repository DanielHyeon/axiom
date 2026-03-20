/**
 * 도메인 그래프 데이터 훅
 *
 * ObjectType 목록에서 Cytoscape 렌더링용 노드/엣지를 계산한다.
 */

import { useMemo } from 'react';
import type { ObjectType, DomainGraphData, DomainGraphNode, DomainGraphEdge } from '../types/domain';

/**
 * ObjectType 배열을 Cytoscape 호환 그래프 데이터로 변환
 */
export function useDomainGraph(objectTypes: ObjectType[]): DomainGraphData {
  return useMemo(() => {
    // 노드: ObjectType 하나당 하나
    const nodes: DomainGraphNode[] = objectTypes.map((ot) => ({
      id: ot.id,
      label: ot.displayName || ot.name,
      status: ot.status,
      fieldCount: ot.fields.length,
      behaviorCount: ot.behaviors.length,
    }));

    // 엣지: 모든 ObjectType의 relations를 flat하게 풀어놓음
    const edgeSet = new Set<string>(); // 중복 방지
    const edges: DomainGraphEdge[] = [];

    for (const ot of objectTypes) {
      for (const rel of ot.relations) {
        const edgeKey = `${ot.id}→${rel.targetObjectTypeId}→${rel.name}`;
        if (!edgeSet.has(edgeKey)) {
          edgeSet.add(edgeKey);
          edges.push({
            source: ot.id,
            target: rel.targetObjectTypeId,
            label: rel.name,
            type: rel.type,
          });
        }
      }
    }

    return { nodes, edges };
  }, [objectTypes]);
}
