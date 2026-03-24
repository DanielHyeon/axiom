/**
 * useDocuments 훅 테스트 — TanStack Query 무효화 + 낙관적 업데이트 검증.
 *
 * 고위험 플로우:
 * - useDocumentReviewAction: FSM 가드 위반 시 mutation 차단
 * - 낙관적 업데이트: onMutate에서 즉시 UI 반영 → 실패 시 롤백
 * - onSettled: 성공/실패와 무관하게 쿼리 무효화
 * - useAddComment: 성공 시 코멘트 캐시 무효화
 *
 * [발견된 결함] CRITICAL — onMutate-mutationFn 순서 충돌:
 * TanStack Query v5에서 onMutate가 mutationFn보다 먼저 실행된다.
 * useDocumentReviewAction의 mutationFn은 qc.getQueryData()로 현재 상태를 읽어
 * FSM 가드를 수행하는데, onMutate가 이미 캐시를 목표 상태로 변경한 뒤이므로
 * canTransition(targetStatus, targetStatus) → false가 되어 항상 실패한다.
 * 캐시에 문서가 없는 경우에만 정상 동작한다. (FSM 가드가 skip됨)
 * 수정 제안: mutationFn에서 캐시를 읽지 말고 변수로 전달받거나,
 *            onMutate에서 FSM 가드를 수행한 후 context로 전달해야 한다.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';

// ── 외부 의존성 모킹 (vi.hoisted로 호이스팅 보장) ──

const {
  mockFetchDocuments,
  mockFetchDocument,
  mockCreateDocument,
  mockUpdateDocument,
  mockFetchComments,
  mockAddComment,
  mockSubmitReview,
} = vi.hoisted(() => ({
  mockFetchDocuments: vi.fn(),
  mockFetchDocument: vi.fn(),
  mockCreateDocument: vi.fn(),
  mockUpdateDocument: vi.fn(),
  mockFetchComments: vi.fn(),
  mockAddComment: vi.fn(),
  mockSubmitReview: vi.fn(),
}));

// sonner toast 모킹
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('../api/documentApi', () => ({
  fetchDocuments: mockFetchDocuments,
  fetchDocument: mockFetchDocument,
  createDocument: mockCreateDocument,
  updateDocument: mockUpdateDocument,
  fetchComments: mockFetchComments,
  addComment: mockAddComment,
}));

vi.mock('../api/documentReviewApi', () => ({
  submitDocumentReview: mockSubmitReview,
}));

// ── 훅 임포트 (모킹 이후) ──
import {
  useDocumentList,
  useDocumentComments,
  useAddComment,
  useDocumentReviewAction,
} from './useDocuments';
import { toast } from 'sonner';
import type { Document } from '../types/document';

// ── 테스트 유틸 ──

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function createWrapper(qc: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: qc }, children);
  };
}

const CASE_ID = 'case-001';
const DOC_ID = 'doc-001';

function createMockDocument(overrides: Partial<Document> = {}): Document {
  return {
    id: DOC_ID,
    caseId: CASE_ID,
    name: 'Test Document',
    type: 'contract',
    status: 'draft',
    version: '1.0',
    content: 'sample content',
    isAiGenerated: false,
    createdBy: 'user-1',
    createdAt: '2026-03-24T00:00:00Z',
    updatedAt: '2026-03-24T00:00:00Z',
    ...overrides,
  };
}

beforeEach(() => {
  vi.resetAllMocks();
});

// ═══════════════════════════════════════════════════════════════
// 1. useDocumentList — 문서 목록 쿼리
// ═══════════════════════════════════════════════════════════════

describe('useDocumentList', () => {
  it('caseId로 문서 목록을 조회한다', async () => {
    const qc = createTestQueryClient();
    mockFetchDocuments.mockResolvedValueOnce({ items: [createMockDocument()], total: 1 });

    const { result } = renderHook(() => useDocumentList(CASE_ID), {
      wrapper: createWrapper(qc),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchDocuments).toHaveBeenCalledWith(CASE_ID);
    expect(result.current.data?.items).toHaveLength(1);
  });

  it('caseId가 빈 문자열이면 쿼리가 비활성화된다', () => {
    const qc = createTestQueryClient();

    const { result } = renderHook(() => useDocumentList(''), {
      wrapper: createWrapper(qc),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockFetchDocuments).not.toHaveBeenCalled();
  });
});

// ═══════════════════════════════════════════════════════════════
// 2. useAddComment — 코멘트 추가 + 캐시 무효화
// ═══════════════════════════════════════════════════════════════

describe('useAddComment', () => {
  it('성공 시 코멘트 캐시가 무효화된다', async () => {
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    mockAddComment.mockResolvedValueOnce({ id: 'c-1', content: 'nice' });

    const { result } = renderHook(() => useAddComment(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ content: 'nice' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockAddComment).toHaveBeenCalledWith(CASE_ID, DOC_ID, { content: 'nice' });
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ['document-comments', CASE_ID, DOC_ID],
      }),
    );
    expect(toast.success).toHaveBeenCalledWith('코멘트가 추가되었습니다');
  });

  it('실패 시 에러 토스트가 표시된다', async () => {
    const qc = createTestQueryClient();
    mockAddComment.mockRejectedValueOnce(new Error('Server error'));

    const { result } = renderHook(() => useAddComment(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ content: 'fail test' });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(toast.error).toHaveBeenCalledWith('코멘트 추가에 실패했습니다');
  });

  it('lineStart/lineEnd 파라미터가 API에 전달된다', async () => {
    const qc = createTestQueryClient();
    mockAddComment.mockResolvedValueOnce({ id: 'c-2', content: 'line comment' });

    const { result } = renderHook(() => useAddComment(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ content: 'line comment', lineStart: 10, lineEnd: 15 });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockAddComment).toHaveBeenCalledWith(CASE_ID, DOC_ID, {
      content: 'line comment',
      lineStart: 10,
      lineEnd: 15,
    });
  });
});

// ═══════════════════════════════════════════════════════════════
// 3. useDocumentReviewAction — FSM 가드
// ═══════════════════════════════════════════════════════════════

describe('useDocumentReviewAction — FSM 가드', () => {
  it('무효한 전이: draft에서 approve 시도 시 에러 발생', async () => {
    const qc = createTestQueryClient();
    // 캐시에 문서 설정 — onMutate가 approved로 변경하고,
    // mutationFn이 canTransition('approved', 'approved')을 체크하여 실패
    const doc = createMockDocument({ status: 'draft' });
    qc.setQueryData(['documents', CASE_ID, DOC_ID], doc);

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'approve' });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    // FSM 가드에 의해 차단됨
    expect(mockSubmitReview).not.toHaveBeenCalled();
    expect(result.current.error?.message).toContain('허용되지 않습니다');
  });

  it('캐시에 문서가 없으면 FSM 가드를 건너뛰고 API를 직접 호출한다', async () => {
    const qc = createTestQueryClient();
    // 캐시에 문서 없음 — doc이 undefined이므로 FSM 가드 skip → API 직접 호출
    mockSubmitReview.mockResolvedValueOnce({ documentId: DOC_ID, status: 'approved' });

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'approve' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockSubmitReview).toHaveBeenCalledWith(CASE_ID, DOC_ID, {
      action: 'approve',
      comment: undefined,
    });
    expect(toast.success).toHaveBeenCalledWith('승인 완료');
  });

  it('캐시 없이 reject 액션은 submitDocumentReview를 호출한다', async () => {
    const qc = createTestQueryClient();
    mockSubmitReview.mockResolvedValueOnce({ documentId: DOC_ID, status: 'rejected' });

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'reject', comment: '기각 사유' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockSubmitReview).toHaveBeenCalledWith(CASE_ID, DOC_ID, {
      action: 'reject',
      comment: '기각 사유',
    });
    expect(toast.success).toHaveBeenCalledWith('반려됨');
  });

  it('캐시 없이 request_changes 액션은 submitDocumentReview를 호출한다', async () => {
    const qc = createTestQueryClient();
    mockSubmitReview.mockResolvedValueOnce({ documentId: DOC_ID, status: 'changes_requested' });

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'request_changes', comment: '수정 필요' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockSubmitReview).toHaveBeenCalledWith(CASE_ID, DOC_ID, {
      action: 'request_changes',
      comment: '수정 필요',
    });
    expect(toast.success).toHaveBeenCalledWith('수정 요청됨');
  });

  it('캐시 없이 submit_for_review는 updateDocument를 호출한다', async () => {
    const qc = createTestQueryClient();
    mockUpdateDocument.mockResolvedValueOnce({ status: 'in_review' });

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'submit_for_review' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockUpdateDocument).toHaveBeenCalled();
    expect(mockSubmitReview).not.toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith('검토 요청됨');
  });

  it('캐시 없이 resubmit은 updateDocument를 호출한다', async () => {
    const qc = createTestQueryClient();
    mockUpdateDocument.mockResolvedValueOnce({ status: 'in_review' });

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'resubmit' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockUpdateDocument).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith('재검토 요청됨');
  });
});

// ═══════════════════════════════════════════════════════════════
// 4. useDocumentReviewAction — 낙관적 업데이트 + 롤백
//    [주의] 캐시가 있으면 onMutate-mutationFn 충돌 버그 때문에
//    낙관적 업데이트 후 mutationFn이 항상 실패한다.
//    이 섹션은 해당 버그를 특성 테스트(characterization test)로 기록한다.
// ═══════════════════════════════════════════════════════════════

describe('useDocumentReviewAction — onMutate 낙관적 업데이트 (캐시 있는 경우)', () => {
  it('캐시에 문서가 있으면 FSM 가드 통과 후 낙관적 업데이트 + API 호출이 정상 실행된다', async () => {
    // 수정됨: FSM 가드가 onMutate에서 원본 상태로 검증 → 낙관적 업데이트 → mutationFn 호출
    const qc = createTestQueryClient();
    const doc = createMockDocument({ status: 'in_review' });
    qc.setQueryData(['documents', CASE_ID, DOC_ID], doc);
    mockSubmitReview.mockResolvedValueOnce({ documentId: DOC_ID, status: 'approved' });

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'approve' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // API가 정상 호출되었다
    expect(mockSubmitReview).toHaveBeenCalledWith(CASE_ID, DOC_ID, {
      action: 'approve',
      comment: undefined,
    });
  });

  it('API 실패 시에도 롤백 토스트가 표시된다 (캐시 없는 시나리오)', async () => {
    const qc = createTestQueryClient();
    // 캐시 없음 → FSM 가드 skip → API 직접 호출 → API 실패
    mockSubmitReview.mockRejectedValueOnce(new Error('Internal Server Error'));

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'approve' });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toast.error).toHaveBeenCalledWith('리뷰 처리에 실패했습니다. 이전 상태로 복원합니다.');
  });
});

// ═══════════════════════════════════════════════════════════════
// 5. useDocumentReviewAction — onSettled 캐시 무효화
// ═══════════════════════════════════════════════════════════════

describe('useDocumentReviewAction — onSettled 캐시 무효화', () => {
  it('성공 후 detail + list 쿼리가 모두 무효화된다', async () => {
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    // 캐시 없이 테스트 (FSM 가드 skip 경로)
    mockSubmitReview.mockResolvedValueOnce({ documentId: DOC_ID, status: 'rejected' });

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'reject' });
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // onSettled에서 detail + list 모두 무효화
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['documents', CASE_ID, DOC_ID] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['documents', CASE_ID] }),
    );
  });

  it('실패 후에도 쿼리 무효화가 수행된다 (onSettled는 항상 실행)', async () => {
    const qc = createTestQueryClient();
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries');
    // 캐시에 문서 설정 — 의도적으로 FSM 충돌 버그를 트리거
    const doc = createMockDocument({ status: 'in_review' });
    qc.setQueryData(['documents', CASE_ID, DOC_ID], doc);
    mockSubmitReview.mockRejectedValueOnce(new Error('fail'));

    const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await act(async () => {
      result.current.mutate({ action: 'approve' });
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    // onSettled는 에러여도 실행됨
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['documents', CASE_ID, DOC_ID] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['documents', CASE_ID] }),
    );
  });
});

// ═══════════════════════════════════════════════════════════════
// 6. useDocumentComments — 코멘트 목록 쿼리
// ═══════════════════════════════════════════════════════════════

describe('useDocumentComments', () => {
  it('caseId와 docId가 모두 있을 때 코멘트를 조회한다', async () => {
    const qc = createTestQueryClient();
    mockFetchComments.mockResolvedValueOnce([
      { id: 'c-1', content: 'comment 1' },
    ]);

    const { result } = renderHook(() => useDocumentComments(CASE_ID, DOC_ID), {
      wrapper: createWrapper(qc),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(mockFetchComments).toHaveBeenCalledWith(CASE_ID, DOC_ID);
    expect(result.current.data).toHaveLength(1);
  });

  it('docId가 빈 문자열이면 쿼리가 비활성화된다', () => {
    const qc = createTestQueryClient();

    const { result } = renderHook(() => useDocumentComments(CASE_ID, ''), {
      wrapper: createWrapper(qc),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockFetchComments).not.toHaveBeenCalled();
  });

  it('caseId가 빈 문자열이면 쿼리가 비활성화된다', () => {
    const qc = createTestQueryClient();

    const { result } = renderHook(() => useDocumentComments('', DOC_ID), {
      wrapper: createWrapper(qc),
    });

    expect(result.current.fetchStatus).toBe('idle');
    expect(mockFetchComments).not.toHaveBeenCalled();
  });
});

// ═══════════════════════════════════════════════════════════════
// 7. 액션별 toast 메시지 매핑
// ═══════════════════════════════════════════════════════════════

describe('ReviewAction → toast 메시지 매핑', () => {
  const actionToastMap = [
    { action: 'approve', expected: '승인 완료' },
    { action: 'reject', expected: '반려됨' },
    { action: 'request_changes', expected: '수정 요청됨' },
    { action: 'submit_for_review', expected: '검토 요청됨' },
    { action: 'resubmit', expected: '재검토 요청됨' },
  ] as const;

  it.each(actionToastMap)(
    '"$action" 성공 시 "$expected" 토스트가 표시된다',
    async ({ action, expected }) => {
      const qc = createTestQueryClient();
      // 캐시 없이 테스트 — FSM 가드 skip
      const reviewActions = ['approve', 'reject', 'request_changes'];
      if (reviewActions.includes(action)) {
        mockSubmitReview.mockResolvedValueOnce({ documentId: DOC_ID, status: 'ok' });
      } else {
        mockUpdateDocument.mockResolvedValueOnce({ status: 'ok' });
      }

      const { result } = renderHook(() => useDocumentReviewAction(CASE_ID, DOC_ID), {
        wrapper: createWrapper(qc),
      });

      await act(async () => {
        result.current.mutate({ action });
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(toast.success).toHaveBeenCalledWith(expected);
    },
  );
});
