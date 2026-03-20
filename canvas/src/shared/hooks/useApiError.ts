// 공통 API 에러 처리 훅 — toast 알림으로 사용자에게 에러 표시
import { toast } from 'sonner';

export function useApiError() {
  return {
    /** API 호출 실패 시 toast 에러 표시 */
    handleError: (context: string, err: unknown) => {
      const msg = err instanceof Error ? err.message : '알 수 없는 오류';
      toast.error(context, { description: msg });
    },
  };
}
