/**
 * SchemaEmptyState -- 스키마 캔버스 빈 상태 UI.
 *
 * 현재 모드(robo / text2sql / none)에 따라 안내 메시지와
 * 데이터소스 연결 또는 모드 전환 액션을 표시한다.
 */

import { Code2, Database, Table2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTranslation } from 'react-i18next';

// ─── Props ────────────────────────────────────────────────

interface SchemaEmptyStateProps {
  /** 현재 모드 또는 'none' (둘 다 없음) */
  mode: 'robo' | 'text2sql' | 'none';
  /** 가용성 데이터 */
  availability: {
    robo: { table_count: number };
    text2sql: { table_count: number };
  } | null;
  /** 데이터소스 연결 탭으로 이동 */
  onNavigateDatasource?: () => void;
  /** text2sql 모드로 전환 */
  onSwitchToText2sql?: () => void;
  /** robo 모드로 전환 */
  onSwitchToRobo?: () => void;
}

// ─── 모드별 설정 ──────────────────────────────────────────

/** 각 모드에 대응하는 아이콘, 제목, 설명 */
const MODE_ICON = {
  robo: Code2,
  text2sql: Database,
  none: Table2,
} as const;

// ─── 컴포넌트 ─────────────────────────────────────────────

export function SchemaEmptyState({
  mode,
  availability,
  onNavigateDatasource,
  onSwitchToText2sql,
  onSwitchToRobo,
}: SchemaEmptyStateProps) {
  const { t } = useTranslation();
  const Icon = MODE_ICON[mode];
  const titleKey = mode === 'robo' ? 'schemaEmpty.roboTitle' : mode === 'text2sql' ? 'schemaEmpty.text2sqlTitle' : 'schemaEmpty.noneTitle';
  const descKey = mode === 'robo' ? 'schemaEmpty.roboDesc' : mode === 'text2sql' ? 'schemaEmpty.text2sqlDesc' : 'schemaEmpty.noneDesc';

  /** text2sql 쪽에 데이터가 있는지 여부 */
  const hasText2sqlData = (availability?.text2sql.table_count ?? 0) > 0;
  /** robo 쪽에 데이터가 있는지 여부 */
  const hasRoboData = (availability?.robo.table_count ?? 0) > 0;

  /** 데이터소스 연결 CTA 표시 조건: text2sql 또는 none 모드일 때 */
  const showDatasourceCta = mode === 'text2sql' || mode === 'none';

  return (
    <div className="flex h-full w-full items-center justify-center">
      <div className="flex flex-col items-center text-center">
        {/* 아이콘 */}
        <Icon className="mb-4 h-10 w-10 text-foreground/15" />

        {/* 제목 */}
        <p className="font-heading text-[14px] font-medium text-foreground/60">
          {t(titleKey)}
        </p>

        {/* 설명 */}
        <p className="mt-1.5 font-mono text-[11px] text-foreground/30">
          {t(descKey)}
        </p>

        {/* 데이터소스 연결 버튼 */}
        {showDatasourceCta && onNavigateDatasource && (
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={onNavigateDatasource}
          >
            {t('schemaEmpty.connectDatasource')}
          </Button>
        )}

        {/* robo 모드에서 text2sql 데이터가 있을 때 전환 링크 */}
        {mode === 'robo' && hasText2sqlData && onSwitchToText2sql && (
          <button
            type="button"
            className="mt-2 cursor-pointer text-[11px] text-blue-500 hover:text-blue-600"
            onClick={onSwitchToText2sql}
          >
            {t('schemaEmpty.viewDatasource')}
          </button>
        )}

        {/* text2sql 모드에서 robo 데이터가 있을 때 전환 링크 */}
        {mode === 'text2sql' && hasRoboData && onSwitchToRobo && (
          <button
            type="button"
            className="mt-2 cursor-pointer text-[11px] text-blue-500 hover:text-blue-600"
            onClick={onSwitchToRobo}
          >
            {t('schemaEmpty.viewCode')}
          </button>
        )}
      </div>
    </div>
  );
}
