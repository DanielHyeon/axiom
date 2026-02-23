import type { CanvasNode } from '@/stores/processDesignerStore';
import type { StageViewState } from '@/stores/processDesignerStore';

const PADDING = 40;
const MINIMAP_WIDTH = 180;
const MINIMAP_HEIGHT = 120;
const NODE_WIDTH = 140;
const NODE_HEIGHT = 80;

interface MinimapProps {
  nodes: CanvasNode[];
  stageSize: { width: number; height: number };
  stageView: StageViewState;
  onViewportClick: (virtualX: number, virtualY: number) => void;
}

function getContentRect(nodes: CanvasNode[]) {
  if (nodes.length === 0) return { minX: 0, minY: 0, width: 400, height: 300 };
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs) - PADDING;
  const minY = Math.min(...ys) - PADDING;
  const maxX = Math.max(...xs) + NODE_WIDTH + PADDING;
  const maxY = Math.max(...ys) + NODE_HEIGHT + PADDING;
  return {
    minX,
    minY,
    width: maxX - minX,
    height: maxY - minY,
  };
}

export function Minimap({ nodes, stageSize, stageView, onViewportClick }: MinimapProps) {
  const content = getContentRect(nodes);
  const scale = Math.min(
    MINIMAP_WIDTH / content.width,
    MINIMAP_HEIGHT / content.height,
    1
  );

  const toMinimapX = (vx: number) => (vx - content.minX) * scale;
  const toMinimapY = (vy: number) => (vy - content.minY) * scale;

  const viewportLeft = -stageView.x;
  const viewportTop = -stageView.y;
  const viewportW = stageSize.width / stageView.scale;
  const viewportH = stageSize.height / stageView.scale;

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const vx = content.minX + mx / scale;
    const vy = content.minY + my / scale;
    onViewportClick(vx, vy);
  };

  return (
    <div
      className="absolute bottom-4 left-4 rounded border border-neutral-700 bg-neutral-900/90 overflow-hidden cursor-pointer"
      style={{ width: MINIMAP_WIDTH, height: MINIMAP_HEIGHT }}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && (e.currentTarget as HTMLDivElement).click()}
      aria-label="미니맵: 클릭하면 해당 위치로 뷰 이동"
    >
      {nodes.map((node) => (
        <div
          key={node.id}
          className="absolute rounded border border-neutral-600"
          style={{
            left: toMinimapX(node.x),
            top: toMinimapY(node.y),
            width: Math.max(4, NODE_WIDTH * scale),
            height: Math.max(3, NODE_HEIGHT * scale),
            backgroundColor: node.color,
          }}
        />
      ))}
      <div
        className="absolute border-2 border-white/70 pointer-events-none"
        style={{
          left: toMinimapX(viewportLeft),
          top: toMinimapY(viewportTop),
          width: Math.max(2, viewportW * scale),
          height: Math.max(2, viewportH * scale),
        }}
      />
    </div>
  );
}
