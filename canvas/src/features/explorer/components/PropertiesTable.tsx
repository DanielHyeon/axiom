/**
 * PropertiesTable — 오브젝트 속성 키-값 테이블
 *
 * 선택된 오브젝트의 properties를 키-값 쌍으로 표시한다.
 * 속성이 많을 경우 스크롤 가능.
 */

import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table';

// ──────────────────────────────────────
// Props
// ──────────────────────────────────────

interface PropertiesTableProps {
  /** 속성 객체 (키 → 값) */
  properties: Record<string, unknown>;
}

// ──────────────────────────────────────
// 값 포매팅 헬퍼
// ──────────────────────────────────────

/** 값을 사람이 읽을 수 있는 문자열로 변환 */
function formatValue(value: unknown): string {
  if (value == null) return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
}

// ──────────────────────────────────────
// 컴포넌트
// ──────────────────────────────────────

export const PropertiesTable: React.FC<PropertiesTableProps> = ({ properties }) => {
  const { t } = useTranslation();
  const entries = Object.entries(properties);

  // 빈 속성 처리
  if (entries.length === 0) {
    return (
      <div className="text-xs text-muted-foreground text-center py-6">
        속성이 없습니다
      </div>
    );
  }

  return (
    <div className="max-h-[400px] overflow-y-auto border border-border rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs w-[140px]">{t('explorerExt.properties')}</TableHead>
            <TableHead className="text-xs">{t('explorerExt.value')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map(([key, value]) => (
            <TableRow key={key}>
              {/* 속성 키 */}
              <TableCell className="text-xs font-medium text-muted-foreground align-top">
                {key}
              </TableCell>
              {/* 속성 값 */}
              <TableCell className="text-xs font-mono text-foreground break-all whitespace-pre-wrap">
                {formatValue(value)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
};
