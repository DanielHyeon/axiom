import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/authStore';

import { normalizeError } from './errors';

export const createApiClient = (baseURL: string): AxiosInstance => {
    const api = axios.create({
        baseURL,
        timeout: 10000,
        headers: {
            'Content-Type': 'application/json',
        },
    });

    // Request Interceptor: Inject JWT + Tenant ID
    api.interceptors.request.use(
        (config) => {
            const { accessToken, user } = useAuthStore.getState();
            if (accessToken && config.headers) {
                config.headers.Authorization = `Bearer ${accessToken}`;
            }
            if (user?.tenantId && config.headers) {
                config.headers['X-Tenant-Id'] = user.tenantId;
            }
            return config;
        },
        (error) => {
            return Promise.reject(error);
        }
    );

    // Response Interceptor
    api.interceptors.response.use(
        (response) => {
            return response.data;
        },
        async (error: AxiosError) => {
            const original = error.config;

            // Automatic Token Refresh on 401
            if (
                error.response?.status === 401 &&
                original &&
                !(original as InternalAxiosRequestConfig & { _retry?: boolean })._retry &&
                !original.url?.includes('/auth/')
            ) {
                (original as InternalAxiosRequestConfig & { _retry?: boolean })._retry = true;
                try {
                    const newToken = await useAuthStore.getState().refreshAccessToken();
                    if (original.headers) {
                        original.headers.Authorization = `Bearer ${newToken}`;
                    }
                    return api(original); // Retry
                } catch {
                    // Failure handled by store (logout & redirect)
                    return Promise.reject(normalizeError(error));
                }
            }

            return Promise.reject(normalizeError(error));
        }
    );
    return api;
};
