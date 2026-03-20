/**
 * ModelDagViewer — 학습된 모델 DAG 시각화 (Cytoscape)
 *
 * 모델 스펙에서 입력 변수 → 모델 → 출력 변수 형태의
 * DAG 그래프를 Cytoscape.js로 렌더링한다.
 *
 * KAIR StepSimulation.vue의 VueFlow DAG를 Cytoscape로 재구현.
 */
import { useEffect, useRef, useCallback, useMemo } from 'react';
import cytoscape from 'cytoscape';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GitBranch } from 'lucide-react';
import type { ModelSpec, SimulationTrace } from '../types/wizard';

interface ModelDagViewerProps {
  /** 모델 스펙 목록 (학습 전/후 모두 사용) */
  modelSpecs: ModelSpec[];
  /** 시뮬레이션 트레이스 (있으면 색상으로 변화량 표시) */
  traces?: SimulationTrace[];
}

export function ModelDagViewer({ modelSpecs, traces }: ModelDagViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  // 트레이스에서 delta 맵 구성 (useMemo로 무한 루프 방지)
  const deltaMap = useMemo(() => {
    const map = new Map<string, number>();
    if (traces) {
      for (const t of traces) {
        map.set(t.outputField, t.delta);
      }
    }
    return map;
  }, [traces]);

  const buildGraph = useCallback(() => {
    if (!containerRef.current || modelSpecs.length === 0) return;

    // 기존 인스턴스 제거
    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const elements: cytoscape.ElementDefinition[] = [];
    const addedNodes = new Set<string>();

    for (const spec of modelSpecs) {
      // 입력 변수 노드
      for (const feat of spec.features) {
        const inputId = `${feat.nodeId}::${feat.field}`;
        if (!addedNodes.has(inputId)) {
          addedNodes.add(inputId);
          elements.push({
            data: {
              id: inputId,
              label: feat.field,
              type: 'input',
            },
          });
        }

        // 입력 → 모델 엣지
        elements.push({
          data: {
            id: `${inputId}->${spec.modelId}`,
            source: inputId,
            target: spec.modelId,
            label: `lag=${feat.lag}`,
          },
        });
      }

      // 모델 노드
      if (!addedNodes.has(spec.modelId)) {
        addedNodes.add(spec.modelId);
        elements.push({
          data: {
            id: spec.modelId,
            label: spec.name,
            type: 'model',
          },
        });
      }

      // 출력 변수 노드
      const outputId = `${spec.targetNodeId}::${spec.targetField}`;
      if (!addedNodes.has(outputId)) {
        addedNodes.add(outputId);
        const delta = deltaMap.get(outputId) ?? 0;
        elements.push({
          data: {
            id: outputId,
            label: spec.targetField,
            type: 'output',
            delta,
          },
        });
      }

      // 모델 → 출력 엣지
      elements.push({
        data: {
          id: `${spec.modelId}->${outputId}`,
          source: spec.modelId,
          target: outputId,
        },
      });
    }

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        // 입력 변수 노드
        {
          selector: 'node[type="input"]',
          style: {
            'background-color': '#f59e0b',
            label: 'data(label)',
            'font-size': 10,
            color: '#fff',
            'text-valign': 'center',
            'text-halign': 'center',
            width: 80,
            height: 36,
            shape: 'round-rectangle',
            'border-width': 0,
            'text-max-width': '70px',
            'text-wrap': 'ellipsis',
          },
        },
        // 모델 노드
        {
          selector: 'node[type="model"]',
          style: {
            'background-color': '#6366f1',
            label: 'data(label)',
            'font-size': 10,
            color: '#fff',
            'text-valign': 'center',
            'text-halign': 'center',
            width: 100,
            height: 40,
            shape: 'round-rectangle',
            'border-width': 2,
            'border-color': '#4f46e5',
            'text-max-width': '90px',
            'text-wrap': 'ellipsis',
          },
        },
        // 출력 변수 노드 (기본)
        {
          selector: 'node[type="output"]',
          style: {
            'background-color': '#22c55e',
            label: 'data(label)',
            'font-size': 10,
            color: '#fff',
            'text-valign': 'center',
            'text-halign': 'center',
            width: 80,
            height: 36,
            shape: 'round-rectangle',
            'border-width': 2,
            'border-color': '#16a34a',
            'text-max-width': '70px',
            'text-wrap': 'ellipsis',
          },
        },
        // 출력 변수 (감소)
        {
          selector: 'node[type="output"][delta < 0]',
          style: {
            'background-color': '#ef4444',
            'border-color': '#dc2626',
          },
        },
        // 엣지
        {
          selector: 'edge',
          style: {
            'curve-style': 'bezier',
            'target-arrow-shape': 'triangle',
            'target-arrow-color': '#6366f1',
            'line-color': '#6366f1',
            width: 2,
            opacity: 0.6,
            label: 'data(label)',
            'font-size': 8,
            color: '#9ca3af',
            'text-background-opacity': 1,
            'text-background-color': 'hsl(var(--card))',
            'text-background-padding': '2px',
          },
        },
      ],
      layout: {
        name: 'breadthfirst',
        directed: true,
        spacingFactor: 1.5,
        padding: 30,
      },
      minZoom: 0.3,
      maxZoom: 2,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    });
  }, [modelSpecs, deltaMap]);

  useEffect(() => {
    buildGraph();

    return () => {
      if (cyRef.current) {
        cyRef.current.destroy();
        cyRef.current = null;
      }
    };
  }, [buildGraph]);

  if (modelSpecs.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm flex items-center gap-2">
          <GitBranch className="w-4 h-4" />
          모델 DAG 시각화
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          ref={containerRef}
          className="w-full h-[350px] rounded-lg border border-border bg-muted/20"
        />
        {/* 범례 */}
        <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-amber-500" />
            입력 변수
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-500" />
            예측 모델
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-emerald-500" />
            출력 변수
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
