import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ROUTES } from '@/lib/routes/routes';

interface ErrorFallbackProps {
  /** 발생한 에러 객체 */
  error: Error | null;
  /** 다시 시도 버튼 클릭 핸들러 */
  onRetry: () => void;
  /** 페이지 레벨 에러인지 여부 (true 이면 전체 화면을 차지하지 않는다) */
  isPageLevel?: boolean;
}

/**
 * 에러 경계에서 공통으로 사용하는 사용자 친화적 에러 폴백 UI.
 * - 한글/영어 i18n 지원
 * - "다시 시도" 버튼 + "대시보드로 이동" 링크
 * - 에러 코드가 있으면 표시
 * - beacon 으로 전송했다는 안내 문구
 */
export const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  onRetry,
  isPageLevel = false,
}) => {
  const { t } = useTranslation();

  // 에러 메시지에서 코드 추출 (예: "ERR_001: ..." 또는 HTTP 상태 코드)
  const errorCode = extractErrorCode(error);
  const message = error?.message ?? t('errors.unknownError');

  // 페이지 레벨이면 min-h-[60vh], 전역이면 min-h-screen
  const containerClass = isPageLevel
    ? 'flex min-h-[60vh] flex-col items-center justify-center gap-3 md:gap-4 p-4 md:p-8 text-center'
    : 'flex min-h-screen flex-col items-center justify-center gap-3 md:gap-4 p-4 md:p-8 text-center';

  return (
    <div className={containerClass} role="alert" aria-live="assertive">
      {/* 에러 아이콘 */}
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-8 w-8"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
      </div>

      {/* 제목 */}
      <h1 className="text-lg md:text-xl font-semibold">
        {isPageLevel ? t('errors.pageErrorTitle') : t('errors.somethingWentWrong')}
      </h1>

      {/* 에러 메시지 */}
      <p className="max-w-sm md:max-w-md text-center text-xs md:text-sm text-muted-foreground">
        {message}
      </p>

      {/* 에러 코드 표시 */}
      {errorCode && (
        <p className="text-xs text-muted-foreground/70 font-mono">
          {t('errors.errorCode', { code: errorCode })}
        </p>
      )}

      {/* 자동 보고 안내 */}
      <p className="text-xs text-muted-foreground/50">
        {t('errors.errorReportSent')}
      </p>

      {/* 액션 버튼 */}
      <div className="flex items-center gap-3 mt-2">
        <button
          type="button"
          onClick={onRetry}
          className="rounded bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {t('errors.retry')}
        </button>
        <Link
          to={ROUTES.DASHBOARD}
          className="rounded border border-border px-4 py-2 text-sm text-foreground hover:bg-accent transition-colors"
        >
          {t('errors.goToDashboard')}
        </Link>
      </div>
    </div>
  );
};

/**
 * 에러 메시지에서 에러 코드를 추출한다.
 * 패턴: "ERR_XXX", "ERROR_XXX", HTTP 상태 코드 (4xx/5xx) 등
 */
function extractErrorCode(error: Error | null): string | null {
  if (!error?.message) return null;

  // "ERR_001: ..." 패턴
  const codeMatch = error.message.match(/^(ERR[_-]\w+)/i);
  if (codeMatch) return codeMatch[1];

  // HTTP 상태 코드 패턴 (예: "Request failed with status code 500")
  const httpMatch = error.message.match(/status\s*(?:code\s*)?(\d{3})/i);
  if (httpMatch) return httpMatch[1];

  // (name: code) 형태의 에러 (예: DOMException)
  if (error.name && error.name !== 'Error') return error.name;

  return null;
}
