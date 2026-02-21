import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

export const AuthGuard = ({ children }: { children: React.ReactNode }) => {
    const accessToken = useAuthStore((s) => s.accessToken);
    const location = useLocation();

    if (!accessToken) {
        // Save the intended route logic here if needed, but for now just redirect
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <>{children}</>;
};
