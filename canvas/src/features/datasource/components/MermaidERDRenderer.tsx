/**
 * Mermaid.js ERD 렌더링 컴포넌트.
 * mermaid.render()로 SVG 생성 후 DOM에 삽입.
 * 줌/팬: CSS transform 기반 마우스 휠 + 드래그.
 */

import { useRef, useEffect, useState, useCallback } from 'react';
import mermaid from 'mermaid';

interface MermaidERDRendererProps {
  /** Mermaid erDiagram 코드 */
  mermaidCode: string;
  /** 렌더링 상태 알림 */
  onRendered?: (hasDiagram: boolean) => void;
}

// Mermaid 초기화 (전역 1회)
let mermaidInitialized = false;
function ensureMermaidInit() {
  if (mermaidInitialized) return;
  mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    er: { layoutDirection: 'TB' },
    securityLevel: 'strict',
    // 라이트 테마 색상
    themeVariables: {
      primaryColor: '#F5F5F5',
      primaryTextColor: '#333333',
      primaryBorderColor: '#E5E5E5',
      lineColor: '#999999',
      secondaryColor: '#FFFFFF',
      tertiaryColor: '#FAFAFA',
    },
  });
  mermaidInitialized = true;
}

export function MermaidERDRenderer({ mermaidCode, onRendered }: MermaidERDRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgContainerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);

  // 줌/팬 상태
  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });

  // Mermaid 렌더링
  useEffect(() => {
    if (!mermaidCode || !svgContainerRef.current) {
      if (svgContainerRef.current) svgContainerRef.current.innerHTML = '';
      onRendered?.(false);
      return;
    }

    ensureMermaidInit();
    setIsRendering(true);
    setError(null);

    const renderAsync = async () => {
      try {
        // 고유 ID 생성 (Mermaid render 요구사항)
        const id = `erd-${Date.now()}`;
        const { svg } = await mermaid.render(id, mermaidCode);
        if (svgContainerRef.current) {
          svgContainerRef.current.innerHTML = svg;
          onRendered?.(true);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(msg);
        onRendered?.(false);
      } finally {
        setIsRendering(false);
      }
    };

    renderAsync();
  }, [mermaidCode, onRendered]);

  // 줌: 마우스 휠
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setScale((prev) => Math.min(Math.max(prev + delta, 0.2), 4));
  }, []);

  // 팬: 마우스 드래그
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = true;
    dragStart.current = { x: e.clientX - translate.x, y: e.clientY - translate.y };
  }, [translate]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current) return;
    setTranslate({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  }, []);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
  }, []);

  // 줌 리셋
  const handleResetZoom = useCallback(() => {
    setScale(1);
    setTranslate({ x: 0, y: 0 });
  }, []);

  // 빈 코드 처리
  if (!mermaidCode) {
    return (
      <div className="flex-1 flex items-center justify-center text-foreground/60 text-sm">
        데이터소스를 선택하면 ERD 다이어그램이 표시됩니다.
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative flex-1 overflow-hidden bg-white"
      onWheel={handleWheel}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      style={{ cursor: isDragging.current ? 'grabbing' : 'grab' }}
    >
      {/* 렌더링 상태 표시 */}
      {isRendering && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 z-10">
          <div className="flex items-center gap-2 text-sm text-foreground/60">
            <div className="h-4 w-4 border-2 border-foreground/30 border-t-foreground/60 rounded-full animate-spin" />
            ERD 렌더링 중...
          </div>
        </div>
      )}

      {/* 에러 표시 */}
      {error && (
        <div className="absolute top-4 left-4 right-4 p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700 z-10">
          <strong>렌더링 오류:</strong> {error}
        </div>
      )}

      {/* SVG 컨테이너 (줌/팬 적용) */}
      <div
        ref={svgContainerRef}
        className="w-full h-full"
        style={{
          transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
          transformOrigin: '0 0',
        }}
      />

      {/* 줌 컨트롤 */}
      <div className="absolute bottom-4 right-4 flex items-center gap-1 bg-white border border-[#E5E5E5] rounded shadow-sm z-10">
        <button
          type="button"
          onClick={() => setScale((s) => Math.min(s + 0.2, 4))}
          className="px-2 py-1 text-xs text-foreground/60 hover:text-black transition-colors"
          title="확대"
        >
          +
        </button>
        <span className="px-2 py-1 text-[10px] text-foreground/60 font-[IBM_Plex_Mono] min-w-[40px] text-center">
          {Math.round(scale * 100)}%
        </span>
        <button
          type="button"
          onClick={() => setScale((s) => Math.max(s - 0.2, 0.2))}
          className="px-2 py-1 text-xs text-foreground/60 hover:text-black transition-colors"
          title="축소"
        >
          -
        </button>
        <button
          type="button"
          onClick={handleResetZoom}
          className="px-2 py-1 text-[10px] text-foreground/60 hover:text-black transition-colors border-l border-[#E5E5E5]"
          title="줌 초기화"
        >
          Reset
        </button>
      </div>
    </div>
  );
}
