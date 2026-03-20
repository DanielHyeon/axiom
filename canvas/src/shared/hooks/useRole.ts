import { useAuthStore } from '@/stores/authStore';
import type { UserRole } from '@/types/auth.types';

export const useRole = (roles: UserRole[]): boolean => {
    const role = useAuthStore((s) => s.user?.role);
    return role ? roles.includes(role) : false;
};
