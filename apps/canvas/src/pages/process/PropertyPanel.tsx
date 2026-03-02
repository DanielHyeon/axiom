import type { CanvasItem } from '@/features/process-designer/types/processDesigner';
import { NODE_CONFIGS } from '@/features/process-designer/utils/nodeConfig';

interface PropertyPanelProps {
 selectedNode: CanvasItem | null;
 onUpdateLabel: (id: string, label: string) => void;
}

export function PropertyPanel({ selectedNode, onUpdateLabel }: PropertyPanelProps) {
 return (
 <div className="w-80 border-l border-border bg-card flex flex-col">
 <div className="p-4 border-b border-border font-bold text-sm text-foreground/80">
 속성 패널 (Property Panel)
 </div>
 <div className="p-4 flex-1 overflow-auto">
 {selectedNode ? (
 <div className="space-y-4">
 <section>
 <h3 className="text-xs text-foreground0 uppercase tracking-wider mb-2">기본 속성</h3>
 <div className="space-y-3">
 <div>
 <label className="text-xs text-foreground0 uppercase tracking-wider block mb-1">ID</label>
 <div className="text-sm font-mono bg-background px-2 py-1 rounded text-muted-foreground truncate">
 {selectedNode.id}
 </div>
 </div>
 <div>
 <label className="text-xs text-foreground0 uppercase tracking-wider block mb-1">Type</label>
 <div className="text-sm px-2 py-1 rounded bg-background text-foreground/80">
 {NODE_CONFIGS[selectedNode.type]?.label ?? selectedNode.type}
 </div>
 </div>
 <div>
 <label htmlFor="property-panel-label" className="text-xs text-foreground0 uppercase tracking-wider block mb-1">Label</label>
 <input
 id="property-panel-label"
 type="text"
 value={selectedNode.label}
 onChange={(e) => onUpdateLabel(selectedNode.id, e.target.value)}
 className="w-full bg-muted border border-border rounded px-2 py-1.5 text-sm text-white"
 aria-label="노드 라벨"
 />
 </div>
 <div className="grid grid-cols-2 gap-2">
 <div>
 <label className="text-xs text-foreground0 uppercase tracking-wider block mb-1">X</label>
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">{Math.round(selectedNode.x)}</div>
 </div>
 <div>
 <label className="text-xs text-foreground0 uppercase tracking-wider block mb-1">Y</label>
 <div className="text-sm px-2 py-1 bg-background rounded text-muted-foreground">{Math.round(selectedNode.y)}</div>
 </div>
 </div>
 </div>
 </section>
 <section>
 <h3 className="text-xs text-foreground0 uppercase tracking-wider mb-2">시간축 속성</h3>
 <p className="text-xs text-foreground0">예상 소요·SLA·실제 평균 (연동 예정)</p>
 </section>
 <section>
 <h3 className="text-xs text-foreground0 uppercase tracking-wider mb-2">이벤트 로그 바인딩</h3>
 <p className="text-xs text-foreground0">소스 테이블·타임스탬프·케이스 ID (연동 예정)</p>
 </section>
 <section>
 <h3 className="text-xs text-foreground0 uppercase tracking-wider mb-2">측정값 바인딩</h3>
 <p className="text-xs text-foreground0">연결된 KPI (연동 예정)</p>
 </section>
 </div>
 ) : (
 <div className="h-full flex items-center justify-center text-sm text-foreground0 text-center">
 캔버스에서 노드를 선택하여<br />속성을 확인하세요.
 </div>
 )}
 </div>
 </div>
 );
}
