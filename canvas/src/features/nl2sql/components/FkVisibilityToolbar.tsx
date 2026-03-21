/**
 * FkVisibilityToolbar -- FK 관계선 소스별 가시성 토글 버튼 모음.
 *
 * DDL(초록), User(주황), Fabric(파랑) 3가지 소스별로
 * 관계선 표시/숨김을 토글하는 칩 버튼을 렌더링한다.
 */
import { cn } from '@/lib/utils';
import { Eye, EyeOff } from 'lucide-react';
import type { FkSource, FkVisibilityState } from '../hooks/useFkVisibility';
import { FK_SOURCE_STYLES } from '../hooks/useFkVisibility';

interface FkVisibilityToolbarProps {
  visibility: FkVisibilityState;
  onToggle: (source: FkSource) => void;
}

const SOURCES: FkSource[] = ['ddl', 'user', 'fabric'];

export function FkVisibilityToolbar({ visibility, onToggle }: FkVisibilityToolbarProps) {
  return (
    <div className="flex items-center gap-1 shrink-0">
      {SOURCES.map((source) => {
        const style = FK_SOURCE_STYLES[source];
        const active = visibility[source];
        return (
          <button
            key={source}
            type="button"
            onClick={() => onToggle(source)}
            className={cn(
              'flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-[IBM_Plex_Mono] transition-all',
              active
                ? 'opacity-100'
                : 'opacity-30 line-through'
            )}
            title={`${style.label} FK ${active ? '숨기기' : '표시'}`}
          >
            {/* 색상 인디케이터 도트 */}
            <span
              className="inline-block w-2 h-2 rounded-full shrink-0"
              style={{ backgroundColor: style.color }}
            />
            {active ? (
              <Eye className="h-2.5 w-2.5 text-foreground/50" />
            ) : (
              <EyeOff className="h-2.5 w-2.5 text-foreground/30" />
            )}
            <span className={cn(active ? 'text-foreground/60' : 'text-foreground/25')}>
              {style.label}
            </span>
          </button>
        );
      })}
    </div>
  );
}
