/**
 * QueryToolbar — 쿼리 제어 툴바
 *
 * 스키마 트리 토글, 데이터소스 선택기, 모드 전환(ReAct/Ask),
 * 행 제한 셀렉터, 초기화 버튼을 한 줄에 배치한다.
 */
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { PanelLeftClose, PanelLeftOpen, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import { DatasourceSelector } from './DatasourceSelector';
import { ROW_LIMIT_OPTIONS } from '@/features/nl2sql/hooks/useNl2SqlChat';

interface QueryToolbarProps {
  /** 스키마 트리가 열려있는지 여부 */
  schemaTreeOpen: boolean;
  /** 스키마 트리 토글 함수 */
  onToggleSchemaTree: () => void;
  /** 선택된 데이터소스 ID */
  datasourceId: string;
  /** 데이터소스 변경 핸들러 */
  onDatasourceChange: (id: string) => void;
  /** 현재 쿼리 모드 */
  mode: 'react' | 'ask';
  /** 모드 변경 핸들러 */
  onModeChange: (mode: 'react' | 'ask') => void;
  /** 현재 행 제한 수 */
  rowLimit: number;
  /** 행 제한 변경 핸들러 */
  onRowLimitChange: (limit: number) => void;
  /** 채팅 메시지가 있는지 (초기화 버튼 표시 조건) */
  hasMessages: boolean;
  /** 초기화 핸들러 */
  onClear: () => void;
}

export function QueryToolbar({
  schemaTreeOpen,
  onToggleSchemaTree,
  datasourceId,
  onDatasourceChange,
  mode,
  onModeChange,
  rowLimit,
  onRowLimitChange,
  hasMessages,
  onClear,
}: QueryToolbarProps) {
  const { t } = useTranslation();

  return (
    <div className="flex items-center gap-3">
      {/* 스키마 트리 열기/닫기 버튼 */}
      <button
        type="button"
        onClick={onToggleSchemaTree}
        className={cn(
          'p-2 rounded transition-colors',
          schemaTreeOpen
            ? 'bg-blue-50 text-blue-600'
            : 'text-foreground/40 hover:text-foreground/60 hover:bg-[#F5F5F5]',
        )}
        title={schemaTreeOpen ? '스키마 트리 닫기' : '스키마 트리 열기'}
        aria-label={schemaTreeOpen ? '스키마 트리 닫기' : '스키마 트리 열기'}
      >
        {schemaTreeOpen ? (
          <PanelLeftClose className="h-4 w-4" />
        ) : (
          <PanelLeftOpen className="h-4 w-4" />
        )}
      </button>

      {/* 데이터소스 선택기 */}
      <DatasourceSelector value={datasourceId} onChange={onDatasourceChange} />

      {/* 모드 전환 버튼 (ReAct / Ask) */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onModeChange('react')}
          className={cn(
            'px-3 py-1 text-[11px] font-medium font-[IBM_Plex_Mono] rounded transition-colors',
            mode === 'react'
              ? 'bg-[#F5F5F5] text-black'
              : 'text-foreground/60 hover:text-muted-foreground',
          )}
        >
          ReAct
        </button>
        <button
          type="button"
          onClick={() => onModeChange('ask')}
          className={cn(
            'px-3 py-1 text-[11px] font-medium font-[IBM_Plex_Mono] rounded transition-colors',
            mode === 'ask'
              ? 'bg-[#F5F5F5] text-black'
              : 'text-foreground/60 hover:text-muted-foreground',
          )}
        >
          Ask
        </button>
      </div>

      {/* 행 제한 선택기 */}
      <Select value={String(rowLimit)} onValueChange={(v) => onRowLimitChange(Number(v))}>
        <SelectTrigger className="h-7 w-20 border-[#E5E5E5] bg-white text-xs text-[#5E5E5E]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {ROW_LIMIT_OPTIONS.map((n) => (
            <SelectItem key={n} value={String(n)}>
              {n.toLocaleString()}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {/* 초기화 버튼 — 메시지가 있을 때만 표시 */}
      {hasMessages && (
        <button
          type="button"
          onClick={onClear}
          className="flex items-center gap-1 text-xs text-foreground/60 hover:text-destructive transition-colors"
        >
          <Trash2 className="h-3 w-3" />
          {t('nl2sql.reset')}
        </button>
      )}
    </div>
  );
}
