import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RootCausePanel } from './RootCausePanel';
import type { RootCause } from './RootCausePanel';

// i18n mock -- t() 가 키를 그대로 반환
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, opts?: Record<string, unknown>) => {
      const map: Record<string, string> = {
        'insight.rootCause.title': '근본 원인 분석',
        'insight.rootCause.analyzing': '근본 원인 분석 중...',
        'insight.rootCause.selectDriverHint': 'Driver를 선택하면 근본 원인이 표시됩니다',
        'insight.rootCause.noResults': '분석된 근본 원인이 없습니다',
        'insight.rootCause.count': `${opts?.count ?? 0}건`,
        'insight.rootCause.depthDirect': '직접 원인',
        'insight.rootCause.depthIndirect': '간접 원인',
        'insight.rootCause.depthRoot': '근본 원인',
        'insight.rootCause.category.process': '프로세스',
        'insight.rootCause.category.machine': '설비',
        'insight.rootCause.category.human': '인적 요인',
        'insight.rootCause.category.material': '자재',
      };
      return map[key] ?? (opts?.defaultValue as string) ?? key;
    },
    i18n: { language: 'ko' },
  }),
}));

// ── 테스트 데이터 ──
const MOCK_ROOT_CAUSES: RootCause[] = [
  { id: 'rc-1', name: '공정 온도 편차', contribution: 0.45, category: 'process', depth: 1 },
  { id: 'rc-2', name: '원재료 불량', contribution: 0.3, category: 'material', depth: 2 },
  { id: 'rc-3', name: '설비 마모', contribution: 0.15, category: 'machine', depth: 3 },
  { id: 'rc-4', name: '작업자 피로', contribution: 0.1, category: 'human', depth: 2 },
];

// ---------------------------------------------------------------------------
// 기본 렌더링 테스트
// ---------------------------------------------------------------------------

describe('RootCausePanel -- 렌더링', () => {
  it('드라이버 미선택 시 빈 상태 표시', () => {
    render(
      <RootCausePanel
        driverId={null}
        rootCauses={[]}
        isLoading={false}
      />,
    );
    expect(screen.getByTestId('root-cause-empty')).toBeTruthy();
    expect(screen.getByText('Driver를 선택하면 근본 원인이 표시됩니다')).toBeTruthy();
  });

  it('로딩 중 스켈레톤 표시', () => {
    render(
      <RootCausePanel
        driverId="driver-1"
        rootCauses={[]}
        isLoading={true}
      />,
    );
    expect(screen.getByTestId('root-cause-loading')).toBeTruthy();
    expect(screen.getByText('근본 원인 분석 중...')).toBeTruthy();
  });

  it('결과 없을 때 안내 메시지 표시', () => {
    render(
      <RootCausePanel
        driverId="driver-1"
        rootCauses={[]}
        isLoading={false}
      />,
    );
    expect(screen.getByTestId('root-cause-no-results')).toBeTruthy();
    expect(screen.getByText('분석된 근본 원인이 없습니다')).toBeTruthy();
  });

  it('근본 원인 목록을 카테고리별로 표시', () => {
    render(
      <RootCausePanel
        driverId="driver-1"
        rootCauses={MOCK_ROOT_CAUSES}
        isLoading={false}
      />,
    );
    expect(screen.getByTestId('root-cause-panel')).toBeTruthy();

    // 카테고리 헤더 확인
    expect(screen.getByText('프로세스')).toBeTruthy();
    expect(screen.getByText('자재')).toBeTruthy();
    expect(screen.getByText('설비')).toBeTruthy();
    expect(screen.getByText('인적 요인')).toBeTruthy();

    // 원인 이름 확인
    expect(screen.getByText('공정 온도 편차')).toBeTruthy();
    expect(screen.getByText('원재료 불량')).toBeTruthy();
  });

  it('기여도 퍼센트 표시', () => {
    render(
      <RootCausePanel
        driverId="driver-1"
        rootCauses={MOCK_ROOT_CAUSES}
        isLoading={false}
      />,
    );
    expect(screen.getByText('45.0%')).toBeTruthy();
    expect(screen.getByText('30.0%')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 클릭 인터랙션 테스트
// ---------------------------------------------------------------------------

describe('RootCausePanel -- 인터랙션', () => {
  it('근본 원인 클릭 시 onSelectRootCause 콜백 호출', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();

    render(
      <RootCausePanel
        driverId="driver-1"
        rootCauses={MOCK_ROOT_CAUSES}
        isLoading={false}
        onSelectRootCause={onSelect}
      />,
    );

    await user.click(screen.getByText('공정 온도 편차'));
    expect(onSelect).toHaveBeenCalledWith('rc-1');
  });
});
