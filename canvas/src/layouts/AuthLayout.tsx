import { Outlet } from 'react-router-dom';

/**
 * 인증 레이아웃 — 로그인/회원가입 페이지를 감싸는 전체 화면 컨테이너
 * 자식 페이지(LoginPage)가 split-panel 레이아웃을 직접 그리므로
 * 여기서는 화면 전체를 채우는 래퍼만 제공한다.
 */
export const AuthLayout = () => {
  return (
    <div className="min-h-screen w-full">
      <Outlet />
    </div>
  );
};
