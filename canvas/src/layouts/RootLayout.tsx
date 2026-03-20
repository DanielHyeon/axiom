import React from 'react';
import { Outlet } from 'react-router-dom';

/**
 * 최상위 레이아웃. Auth/보호 구간 라우트가 여기서 분기하며,
 * 실제 화면 레이아웃은 자식 Route에서 MainLayout 등으로 적용한다.
 */
export const RootLayout: React.FC = () => <Outlet />;
