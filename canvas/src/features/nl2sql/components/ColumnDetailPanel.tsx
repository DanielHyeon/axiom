/**
 * ColumnDetailPanel — 개별 컬럼 상세 정보 패널.
 *
 * 선택된 컬럼의 타입, nullable, PK/FK 여부, 설명 등을 표시.
 * KAIR ColumnDetailPanel.vue를 React+Tailwind 패턴으로 이식.
 */

import { useTranslation } from 'react-i18next';
import {
  X,
  Key,
  Link,
  Columns3,
  Hash,
  Type,
  ToggleLeft,
  FileText,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { ColumnMeta } from '../types/nl2sql';

// ─── Props ────────────────────────────────────────────────

interface ColumnDetailPanelProps {
  /** 테이블명 */
  tableName: string;
  /** 컬럼 메타데이터 */
  column: ColumnMeta;
  /** 닫기 핸들러 */
  onClose?: () => void;
}

// ─── 컴포넌트 ─────────────────────────────────────────────

export function ColumnDetailPanel({
  tableName,
  column,
  onClose,
}: ColumnDetailPanelProps) {
  const { t } = useTranslation();
  // FK 추론: _id 접미사
  const isInferredFk = column.name.endsWith('_id') && !column.is_primary_key;

  return (
    <div className="flex flex-col h-full bg-card border-l border-border">
      {/* 헤더 */}
      <div className="flex items-center justify-between px-4 h-10 border-b border-border shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <Columns3 className="h-3.5 w-3.5 text-foreground/40 shrink-0" />
          <span className="text-[12px] font-semibold text-foreground font-heading truncate">
            {column.name}
          </span>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded hover:bg-muted transition-colors"
            aria-label={t('common.close')}
          >
            <X className="h-3.5 w-3.5 text-foreground/40" />
          </button>
        )}
      </div>

      {/* 테이블 컨텍스트 */}
      <div className="px-4 py-2 bg-muted/50 border-b border-border">
        <span className="text-[10px] text-foreground/40 font-mono">
          {tableName}.{column.name}
        </span>
      </div>

      {/* 속성 목록 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* 데이터 타입 */}
        <PropertyRow
          icon={<Type className="h-3.5 w-3.5 text-purple-400" />}
          label={t('columnDetail.dataType')}
          value={column.data_type}
        />

        {/* FQN */}
        {column.fqn && (
          <PropertyRow
            icon={<Hash className="h-3.5 w-3.5 text-foreground/30" />}
            label={t('columnDetail.fqn')}
            value={column.fqn}
          />
        )}

        {/* PK 여부 */}
        {column.is_primary_key && (
          <PropertyRow
            icon={<Key className="h-3.5 w-3.5 text-amber-400" />}
            label={t('columnDetail.primaryKey')}
          >
            <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-600 bg-amber-50">
              PRIMARY KEY
            </Badge>
          </PropertyRow>
        )}

        {/* FK 추론 */}
        {isInferredFk && (
          <PropertyRow
            icon={<Link className="h-3.5 w-3.5 text-blue-400" />}
            label={t('columnDetail.foreignKeyInferred')}
          >
            <Badge variant="outline" className="text-[10px] border-blue-300 text-blue-600 bg-blue-50">
              FOREIGN KEY (추론)
            </Badge>
          </PropertyRow>
        )}

        {/* Nullable */}
        <PropertyRow
          icon={<ToggleLeft className="h-3.5 w-3.5 text-foreground/30" />}
          label="Nullable"
          value={column.nullable ? 'YES' : 'NO'}
        />

        {/* 벡터 여부 */}
        {column.has_vector && (
          <PropertyRow
            icon={<Hash className="h-3.5 w-3.5 text-green-400" />}
            label={t('columnDetail.vectorIndex')}
            value={t('columnDetail.vectorEnabled')}
          />
        )}

        {/* 설명 */}
        <PropertyRow
          icon={<FileText className="h-3.5 w-3.5 text-foreground/30" />}
          label={t('columnDetail.description')}
          value={column.description || t('columnDetail.noDescription')}
        />
      </div>
    </div>
  );
}

// ─── 내부 컴포넌트 ────────────────────────────────────────

interface PropertyRowProps {
  icon: React.ReactNode;
  label: string;
  value?: string;
  children?: React.ReactNode;
}

function PropertyRow({ icon, label, value, children }: PropertyRowProps) {
  return (
    <div className="flex items-start gap-3">
      <div className="mt-0.5 shrink-0">{icon}</div>
      <div className="flex-1 min-w-0">
        <span className="text-[10px] text-foreground/40 font-mono uppercase tracking-[0.5px]">
          {label}
        </span>
        {value && (
          <p className="text-[12px] text-foreground font-mono mt-0.5 break-all">
            {value}
          </p>
        )}
        {children && <div className="mt-1">{children}</div>}
      </div>
    </div>
  );
}
