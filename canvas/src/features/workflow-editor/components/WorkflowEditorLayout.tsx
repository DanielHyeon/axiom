/**
 * WorkflowEditorLayout — 워크플로 에디터 2패널 레이아웃
 *
 * 좌측 70%: 워크플로 캔버스 (Cytoscape)
 * 우측 30%: 속성 편집 패널
 * 상단: 노드 추가 도구 모음
 */

import { WorkflowToolbar } from './WorkflowToolbar';
import { WorkflowCanvas } from './WorkflowCanvas';
import { WorkflowPropertyPanel } from './WorkflowPropertyPanel';

export function WorkflowEditorLayout() {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* 상단 도구 모음 */}
      <WorkflowToolbar />

      {/* 메인 2패널 영역 */}
      <div className="flex flex-1 min-h-0">
        {/* 좌측: 캔버스 (70%) */}
        <div className="flex-[7] min-w-0">
          <WorkflowCanvas />
        </div>

        {/* 우측: 속성 패널 (30%) */}
        <div className="flex-[3] min-w-0 border-l border-border bg-card">
          <WorkflowPropertyPanel />
        </div>
      </div>
    </div>
  );
}
