import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { ROUTES } from '@/lib/routes/routes';

export const ProtectedRoute: React.FC = () => {
    const isAuthenticated = Boolean(useAuthStore((state) => state.accessToken));

    if (!isAuthenticated) {
        return <Navigate to={ROUTES.AUTH.LOGIN} replace />;
    }

    return <Outlet />;
};
