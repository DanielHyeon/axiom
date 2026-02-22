import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import axios from 'axios';
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

let refreshInFlight: Promise<string> | null = null;

const coreBaseUrl = (import.meta.env.VITE_CORE_URL || 'http://localhost:8000').replace(/\/$/, '');

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

                if (refreshInFlight) {
                    return refreshInFlight;
                }

                refreshInFlight = axios
                    .post(`${coreBaseUrl}/api/v1/auth/refresh`, { refresh_token: refreshToken })
                    .then((response) => {
                        const payload = response.data || {};
                        const newAccess = payload.access_token || payload.accessToken;
                        const newRefresh = payload.refresh_token || payload.refreshToken || refreshToken;
                        if (!newAccess) {
                            throw new Error('Invalid refresh response: access token missing');
                        }
                        set({ accessToken: newAccess, refreshToken: newRefresh });
                        return newAccess as string;
                    })
                    .catch((error) => {
                        logout();
                        throw error;
                    })
                    .finally(() => {
                        refreshInFlight = null;
                    });

                return refreshInFlight;
            },
        }),
        {
            name: 'axiom-auth',
            storage: createJSONStorage(() => sessionStorage),
        }
    )
);
