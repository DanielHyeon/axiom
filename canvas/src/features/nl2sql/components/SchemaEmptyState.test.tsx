import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SchemaEmptyState } from './SchemaEmptyState';

// ---------------------------------------------------------------------------
// 테스트 헬퍼 — 가용성 데이터 생성
// ---------------------------------------------------------------------------

/** 테스트용 가용성 데이터를 생성한다 */
function makeAvailability(roboCount: number, text2sqlCount: number) {
  return {
    robo: { table_count: roboCount },
    text2sql: { table_count: text2sqlCount },
  };
}

// ---------------------------------------------------------------------------
// 모드별 안내 메시지 표시
// ---------------------------------------------------------------------------

describe('SchemaEmptyState — 모드별 안내 메시지', () => {
  it('mode=robo — 코드 분석 안내 메시지 표시', () => {
    render(
      <SchemaEmptyState
        mode="robo"
        availability={makeAvailability(0, 0)}
      />,
    );

    // robo 모드의 제목 확인
    expect(screen.getByText('분석된 코드 객체가 아직 없습니다')).toBeTruthy();
    // robo 모드의 설명 확인
    expect(
      screen.getByText('소스 코드를 분석하면 테이블 구조를 자동으로 추출합니다'),
    ).toBeTruthy();
  });

  it('mode=text2sql — 데이터소스 안내 메시지 표시', () => {
    render(
      <SchemaEmptyState
        mode="text2sql"
        availability={makeAvailability(0, 0)}
      />,
    );

    expect(screen.getByText('연결된 데이터소스 스키마가 없습니다')).toBeTruthy();
    expect(
      screen.getByText(
        '데이터소스를 연결하면 테이블과 관계가 자동으로 표시됩니다',
      ),
    ).toBeTruthy();
  });

  it('mode=none — 양쪽 안내 메시지 표시', () => {
    render(
      <SchemaEmptyState
        mode="none"
        availability={makeAvailability(0, 0)}
      />,
    );

    expect(screen.getByText('아직 탐색할 스키마가 없습니다')).toBeTruthy();
    expect(
      screen.getByText(
        '데이터소스를 연결하거나 소스 코드를 분석하여 시작하세요',
      ),
    ).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// 모드 전환 링크 표시/미표시
// ---------------------------------------------------------------------------

describe('SchemaEmptyState — 전환 링크 노출 조건', () => {
  it('mode=robo + text2sql 데이터 있음 → text2sql 전환 링크 표시', () => {
    const onSwitch = vi.fn();
    render(
      <SchemaEmptyState
        mode="robo"
        availability={makeAvailability(0, 5)}
        onSwitchToText2sql={onSwitch}
      />,
    );

    // text2sql 데이터가 있으므로 전환 링크가 보여야 한다
    const link = screen.getByText('데이터소스 스키마에서 보기 →');
    expect(link).toBeTruthy();
  });

  it('mode=robo + text2sql 데이터 없음 → 전환 링크 미표시', () => {
    render(
      <SchemaEmptyState
        mode="robo"
        availability={makeAvailability(3, 0)}
        onSwitchToText2sql={vi.fn()}
      />,
    );

    // text2sql 데이터가 없으므로 전환 링크가 없어야 한다
    expect(screen.queryByText('데이터소스 스키마에서 보기 →')).toBeNull();
  });

  it('mode=text2sql + robo 데이터 있음 → robo 전환 링크 표시', () => {
    const onSwitch = vi.fn();
    render(
      <SchemaEmptyState
        mode="text2sql"
        availability={makeAvailability(3, 0)}
        onSwitchToRobo={onSwitch}
      />,
    );

    const link = screen.getByText('코드 분석 스키마에서 보기 →');
    expect(link).toBeTruthy();
  });

  it('mode=text2sql + robo 데이터 없음 → 전환 링크 미표시', () => {
    render(
      <SchemaEmptyState
        mode="text2sql"
        availability={makeAvailability(0, 5)}
        onSwitchToRobo={vi.fn()}
      />,
    );

    expect(screen.queryByText('코드 분석 스키마에서 보기 →')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 데이터소스 연결 버튼
// ---------------------------------------------------------------------------

describe('SchemaEmptyState — 데이터소스 연결 CTA', () => {
  it('mode=text2sql에서 onNavigateDatasource 전달 시 버튼 표시', () => {
    const onNavigate = vi.fn();
    render(
      <SchemaEmptyState
        mode="text2sql"
        availability={null}
        onNavigateDatasource={onNavigate}
      />,
    );

    expect(screen.getByText('데이터소스 연결하기')).toBeTruthy();
  });

  it('mode=none에서도 데이터소스 연결 버튼 표시', () => {
    render(
      <SchemaEmptyState
        mode="none"
        availability={null}
        onNavigateDatasource={vi.fn()}
      />,
    );

    expect(screen.getByText('데이터소스 연결하기')).toBeTruthy();
  });

  it('mode=robo에서는 데이터소스 연결 버튼 미표시', () => {
    render(
      <SchemaEmptyState
        mode="robo"
        availability={null}
        onNavigateDatasource={vi.fn()}
      />,
    );

    expect(screen.queryByText('데이터소스 연결하기')).toBeNull();
  });

  it('클릭 시 onNavigateDatasource 콜백 호출', async () => {
    const onNavigate = vi.fn();
    const user = userEvent.setup();

    render(
      <SchemaEmptyState
        mode="text2sql"
        availability={null}
        onNavigateDatasource={onNavigate}
      />,
    );

    await user.click(screen.getByText('데이터소스 연결하기'));
    expect(onNavigate).toHaveBeenCalledOnce();
  });
});
