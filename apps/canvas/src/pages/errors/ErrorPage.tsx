import React from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

interface ErrorPageProps {
  error?: Error;
}

export const ErrorPage: React.FC<ErrorPageProps> = ({ error }) => {
  const message = error?.message ?? '알 수 없는 오류가 발생했습니다.';

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-xl font-semibold">문제가 발생했습니다</h1>
      <p className="max-w-md text-center text-sm text-neutral-500">{message}</p>
      <Link
        to={ROUTES.DASHBOARD}
        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
      >
        대시보드로 이동
      </Link>
    </div>
  );
};
