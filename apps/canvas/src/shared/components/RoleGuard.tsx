import type { ReactNode } from 'react';
import type { UserRole } from '@/types/auth.types';
import { useRole } from '@/shared/hooks/useRole';
import { Link } from 'react-router-dom';

const ForbiddenPage = () => (
    <div className="flex flex-col items-center justify-center min-h-screen bg-neutral-950 text-white p-6">
        <h1 className="text-4xl font-bold mb-4">403 Forbidden</h1>
        <p className="text-neutral-400 mb-6">You do not have permission to access this resource.</p>
        <Link to="/" className="text-blue-500 hover:underline">Return to Dashboard</Link>
    </div>
);

export const RoleGuard = ({ roles, children }: { roles: UserRole[]; children: ReactNode }) => {
    const hasRole = useRole(roles);

    if (!hasRole) {
        return <ForbiddenPage />;
    }

    return <>{children}</>;
};
