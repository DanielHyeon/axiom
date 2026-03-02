// @deprecated — 레거시 호환용 re-export.
// 새 코드에서는 아래를 직접 import하세요:
//   UI state  → features/process-designer/store/useProcessDesignerStore
//   Data      → features/process-designer/store/canvasDataStore
//   Types     → features/process-designer/types/processDesigner

export { useProcessDesignerUIStore as useProcessDesignerStore } from '@/features/process-designer/store/useProcessDesignerStore';
export { useCanvasDataStore } from '@/features/process-designer/store/canvasDataStore';

// 레거시 타입 re-export (기존 import 유지를 위해)
export type { CanvasItem as CanvasNode, CanvasItemType } from '@/features/process-designer/types/processDesigner';
export type { StageViewState } from '@/features/process-designer/types/processDesigner';
