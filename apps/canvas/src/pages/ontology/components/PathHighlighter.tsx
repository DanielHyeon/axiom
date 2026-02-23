import { Map } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface PathHighlighterProps {
  /** 경로에 포함된 노드 ID 목록 (순서대로) */
  pathNodeIds: string[];
  /** 출발 노드 선택 대기 중이면 설정됨 */
  pathModeSource: string | null;
  onClear: () => void;
}

/** 2노드 선택 시 최단 경로 하이라이트 배너. 경로 탐색 모드 안내 및 결과 요약. */
export function PathHighlighter({ pathNodeIds, pathModeSource, onClear }: PathHighlighterProps) {
  if (pathNodeIds.length === 0) return null;

  return (
    <div className="bg-blue-900/20 border-b border-blue-900/50 px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-2 text-blue-200">
        <Map size={16} />
        {pathModeSource
          ? '경로의 도착 노드를 선택하세요.'
          : `최단 경로 탐색 결과 (${pathNodeIds.length}단계)`}
      </div>
      <Button
        variant="ghost"
        size="sm"
        onClick={onClear}
        className="h-7 text-blue-400 hover:text-blue-300"
      >
        탐색 종료
      </Button>
    </div>
  );
}
