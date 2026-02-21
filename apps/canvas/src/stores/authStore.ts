import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User } from '@/types/auth.types';

interface AuthState {
    user: User | null;
    accessToken: string | null;
    refreshToken: string | null;

    // Actions
    setTokens: (access: string, refresh: string) => void;
    setUser: (user: User) => void;
    login: (access: string, refresh: string, user: User) => void;
    logout: () => void;
    refreshAccessToken: () => Promise<string>;
}

export const useAuthStore = create<AuthState>()(
    persist(
        (set, get) => ({
            user: null,
            accessToken: null,
            refreshToken: null,

            setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
            setUser: (user) => set({ user }),

            login: (accessToken, refreshToken, user) => set({ user, accessToken, refreshToken }),

            logout: () => {
                set({ user: null, accessToken: null, refreshToken: null });
                window.location.href = '/login';
            },

            refreshAccessToken: async () => {
                const { refreshToken, logout } = get();
                if (!refreshToken) {
                    logout();
                    return Promise.reject('No refresh token');
                }

                try {
                    // TODO: CAN-S1-004 Call actual endpoint when API is ready
                    // const response = await coreApi.post('/auth/refresh', { refreshToken });
                    // const newAccess = response.data.accessToken;
                    // set({ accessToken: newAccess });
                    // return newAccess;

                    throw new Error('Not implemented yet in actual backend');
                } catch (error) {
                    logout();
                    return Promise.reject(error);
                }
            },
        }),
        {
            name: 'axiom-auth',
            storage: createJSONStorage(() => sessionStorage),
        }
    )
);
