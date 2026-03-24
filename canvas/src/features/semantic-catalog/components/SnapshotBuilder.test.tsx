import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SnapshotBuilder } from './SnapshotBuilder';

// i18n mock
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'snapshotBuilder.currentSnapshot': '현재 활성 스냅샷',
        'snapshotBuilder.noActiveSnapshot': '활성 스냅샷이 없습니다. 새 스냅샷을 빌드해 주세요.',
        'snapshotBuilder.buildNew': '새 스냅샷 빌드',
        'snapshotBuilder.buildFailed': '스냅샷 빌드 실패',
        'snapshotBuilder.buildStarted': '빌드가 시작되었습니다',
        'snapshotBuilder.recentSnapshots': '최근 스냅샷',
        'snapshotBuilder.activate': '활성화',
        'snapshotBuilder.invalidate': '무효화',
        'snapshotBuilder.invalidateReasonPlaceholder': '무효화 사유를 입력하세요',
        'common.loading': '로딩 중...',
        'common.confirm': '확인',
        'common.cancel': '취소',
      };
      return map[key] ?? key;
    },
    i18n: { language: 'ko' },
  }),
}));

// sonner mock (toast)
vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// API mock -- useSemanticCatalog 훅 mock
vi.mock('../hooks/useSemanticCatalog', () => ({
  useActiveSnapshot: () => ({
    data: {
      id: 'snap-1',
      snapshot_version: 'v1.0.0',
      release_version: 'r1',
      status: 'ACTIVE',
      content_hash: 'abc123def456',
      built_at: '2026-03-20T10:00:00Z',
      activated_at: '2026-03-20T10:05:00Z',
    },
    isLoading: false,
  }),
  useSnapshots: () => ({
    data: [
      {
        id: 'snap-1',
        snapshot_version: 'v1.0.0',
        release_version: 'r1',
        status: 'ACTIVE',
        content_hash: 'abc123',
        built_at: '2026-03-20T10:00:00Z',
        activated_at: '2026-03-20T10:05:00Z',
      },
      {
        id: 'snap-2',
        snapshot_version: 'v0.9.0',
        release_version: 'r0',
        status: 'INVALIDATED',
        content_hash: 'xyz789',
        built_at: '2026-03-19T08:00:00Z',
        invalidation_reason: '테스트 무효화',
      },
    ],
    isLoading: false,
  }),
  useBuildSnapshot: () => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
  }),
  useActivateSnapshot: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
  useInvalidateSnapshot: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

// 테스트 래퍼 (TanStack Query Provider)
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// 렌더링 테스트
// ---------------------------------------------------------------------------

describe('SnapshotBuilder -- 렌더링', () => {
  it('컴포넌트가 정상 렌더링된다', () => {
    renderWithProviders(<SnapshotBuilder />);
    expect(screen.getByTestId('snapshot-builder')).toBeTruthy();
  });

  it('현재 활성 스냅샷 버전을 표시한다', () => {
    renderWithProviders(<SnapshotBuilder />);
    // v1.0.0은 활성 스냅샷 카드 + 목록에서 모두 표시
    expect(screen.getAllByText('v1.0.0').length).toBeGreaterThanOrEqual(1);
  });

  it('빌드 버튼이 표시된다', () => {
    renderWithProviders(<SnapshotBuilder />);
    expect(screen.getByText('새 스냅샷 빌드')).toBeTruthy();
  });

  it('최근 스냅샷 목록을 표시한다', () => {
    renderWithProviders(<SnapshotBuilder />);
    expect(screen.getByText('최근 스냅샷')).toBeTruthy();
    // 두 스냅샷 모두 표시
    expect(screen.getAllByText('v1.0.0').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('v0.9.0')).toBeTruthy();
  });

  it('props로 전달한 currentVersion을 우선 표시한다', () => {
    renderWithProviders(<SnapshotBuilder currentVersion="v2.0.0-beta" />);
    expect(screen.getByText('v2.0.0-beta')).toBeTruthy();
  });

  it('ACTIVE 스냅샷에 무효화 버튼이 표시된다', () => {
    renderWithProviders(<SnapshotBuilder />);
    expect(screen.getByText('무효화')).toBeTruthy();
  });

  it('INVALIDATED 스냅샷의 무효화 사유가 표시된다', () => {
    renderWithProviders(<SnapshotBuilder />);
    expect(screen.getByText('테스트 무효화')).toBeTruthy();
  });
});
