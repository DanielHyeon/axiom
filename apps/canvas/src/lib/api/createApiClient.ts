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

    // Request Interceptor
    api.interceptors.request.use(
        (config) => {
            const accessToken = useAuthStore.getState().accessToken;
            if (accessToken && config.headers) {
                config.headers.Authorization = `Bearer ${accessToken}`;
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
