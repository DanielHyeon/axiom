/**
 * SchemaEmptyState -- 스키마 캔버스 빈 상태 UI.
 *
 * 현재 모드(robo / text2sql / none)에 따라 안내 메시지와
 * 데이터소스 연결 또는 모드 전환 액션을 표시한다.
 */

import { Code2, Database, Table2 } from 'lucide-react';
import { Button } from '@/components/ui/button';

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
const MODE_CONFIG = {
  robo: {
    icon: Code2,
    title: '분석된 코드 객체가 아직 없습니다',
    description: '소스 코드를 분석하면 테이블 구조를 자동으로 추출합니다',
  },
  text2sql: {
    icon: Database,
    title: '연결된 데이터소스 스키마가 없습니다',
    description: '데이터소스를 연결하면 테이블과 관계가 자동으로 표시됩니다',
  },
  none: {
    icon: Table2,
    title: '아직 탐색할 스키마가 없습니다',
    description: '데이터소스를 연결하거나 소스 코드를 분석하여 시작하세요',
  },
} as const;

// ─── 컴포넌트 ─────────────────────────────────────────────

export function SchemaEmptyState({
  mode,
  availability,
  onNavigateDatasource,
  onSwitchToText2sql,
  onSwitchToRobo,
}: SchemaEmptyStateProps) {
  const config = MODE_CONFIG[mode];
  const Icon = config.icon;

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
        <p className="font-[Sora] text-[14px] font-medium text-foreground/60">
          {config.title}
        </p>

        {/* 설명 */}
        <p className="mt-1.5 font-[IBM_Plex_Mono] text-[11px] text-foreground/30">
          {config.description}
        </p>

        {/* 데이터소스 연결 버튼 */}
        {showDatasourceCta && onNavigateDatasource && (
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={onNavigateDatasource}
          >
            데이터소스 연결하기
          </Button>
        )}

        {/* robo 모드에서 text2sql 데이터가 있을 때 전환 링크 */}
        {mode === 'robo' && hasText2sqlData && onSwitchToText2sql && (
          <button
            type="button"
            className="mt-2 cursor-pointer text-[11px] text-blue-500 hover:text-blue-600"
            onClick={onSwitchToText2sql}
          >
            데이터소스 스키마에서 보기 →
          </button>
        )}

        {/* text2sql 모드에서 robo 데이터가 있을 때 전환 링크 */}
        {mode === 'text2sql' && hasRoboData && onSwitchToRobo && (
          <button
            type="button"
            className="mt-2 cursor-pointer text-[11px] text-blue-500 hover:text-blue-600"
            onClick={onSwitchToRobo}
          >
            코드 분석 스키마에서 보기 →
          </button>
        )}
      </div>
    </div>
  );
}
