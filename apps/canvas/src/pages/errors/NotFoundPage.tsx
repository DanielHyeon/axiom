import React from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '@/lib/routes/routes';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-2xl font-semibold">404</h1>
      <p className="text-neutral-500">요청한 페이지를 찾을 수 없습니다.</p>
      <Link
        to={ROUTES.DASHBOARD}
        className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
      >
        대시보드로 이동
      </Link>
    </div>
  );
};
