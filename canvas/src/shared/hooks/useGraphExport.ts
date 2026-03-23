/**
 * 그래프 내보내기 공용 훅 — PNG/SVG/JSON 다중 포맷.
 * KG-9: Cytoscape/Mermaid/Konva 캔버스에서 사용 가능.
 */

import { useCallback } from 'react';
import { toast } from 'sonner';

type ExportFormat = 'png' | 'svg' | 'json';

interface ExportOptions {
  filename?: string;
  /** Cytoscape 인스턴스 (cy.png(), cy.svg()) */
  cytoscape?: { png: (opts?: object) => string; svg: (opts?: object) => string };
  /** JSON 직렬화할 데이터 */
  jsonData?: unknown;
  /** SVG 엘리먼트 (Mermaid 등) */
  svgElement?: SVGSVGElement | null;
}

/** 파일 다운로드 헬퍼 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function useGraphExport(options: ExportOptions) {
  const { filename = 'graph-export', cytoscape, jsonData, svgElement } = options;

  const exportGraph = useCallback((format: ExportFormat) => {
    try {
      switch (format) {
        case 'png': {
          if (cytoscape) {
            const dataUrl = cytoscape.png({ full: true, scale: 2, bg: 'white' });
            const a = document.createElement('a');
            a.href = dataUrl;
            a.download = `${filename}.png`;
            a.click();
          } else {
            toast.error('PNG 내보내기를 지원하지 않는 그래프입니다');
            return;
          }
          break;
        }
        case 'svg': {
          let svgStr = '';
          if (cytoscape) {
            svgStr = cytoscape.svg({ full: true });
          } else if (svgElement) {
            svgStr = new XMLSerializer().serializeToString(svgElement);
          } else {
            toast.error('SVG 내보내기를 지원하지 않는 그래프입니다');
            return;
          }
          const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
          downloadBlob(blob, `${filename}.svg`);
          break;
        }
        case 'json': {
          const data = jsonData ?? (cytoscape ? { nodes: [], edges: [] } : null);
          if (!data) {
            toast.error('JSON 내보내기 데이터가 없습니다');
            return;
          }
          const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
          downloadBlob(blob, `${filename}.json`);
          break;
        }
      }
      toast.success(`${format.toUpperCase()} 파일이 다운로드되었습니다`);
    } catch (err) {
      toast.error(`내보내기 실패: ${err instanceof Error ? err.message : '알 수 없는 오류'}`);
    }
  }, [cytoscape, jsonData, svgElement, filename]);

  return { exportGraph };
}
