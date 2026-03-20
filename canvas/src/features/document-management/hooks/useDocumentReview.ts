import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { DocumentReviewAction } from '../api/documentReviewApi';
import { submitDocumentReview } from '../api/documentReviewApi';

export type ReviewState = 'idle' | 'approved' | 'rejected' | 'changes_requested';

interface UseDocumentReviewOptions {
  caseId: string;
  docId: string;
  onSuccess?: (action: DocumentReviewAction) => void;
  onError?: (error: Error) => void;
}

/**
 * 승인/반려/수정요청 API 호출, 낙관적 업데이트, 실패 시 롤백.
 */
export function useDocumentReview({ caseId, docId, onSuccess, onError }: UseDocumentReviewOptions) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async ({
      action,
      comment,
    }: {
      action: DocumentReviewAction;
      comment?: string;
    }) => submitDocumentReview(caseId, docId, { action, comment }),
    onMutate: async ({ action }) => {
      await queryClient.cancelQueries({ queryKey: ['documentReview', caseId, docId] });
      const prev: ReviewState | undefined = queryClient.getQueryData([
        'documentReview',
        caseId,
        docId,
      ]);
      const next: ReviewState =
        action === 'approve' ? 'approved' : action === 'reject' ? 'rejected' : 'changes_requested';
      queryClient.setQueryData(['documentReview', caseId, docId], next);
      return { previousState: prev };
    },
    onError: (err, _variables, context) => {
      if (context?.previousState !== undefined) {
        queryClient.setQueryData(['documentReview', caseId, docId], context.previousState);
      }
      onError?.(err as Error);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['documentReview', caseId, docId] });
    },
    onSuccess: (_data, variables) => {
      onSuccess?.(variables.action);
    },
  });

  return {
    submit: mutation.mutateAsync,
    mutate: mutation.mutate,
    isPending: mutation.isPending,
    isError: mutation.isError,
    error: mutation.error,
  };
}
